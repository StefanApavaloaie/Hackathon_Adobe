import uuid
from unittest.mock import MagicMock

from app.agent import report as report_mod
from app.agent.report import build_messages, build_report_input, template_recommendation
from app.metrics import CampaignMetrics, SourceMetrics, VariantMetrics
from app.routers.usage import DAILY_TOKEN_ALLOWANCE, DEMO_TOKEN_RESERVE, summarize_usage
from app.services.llm_client import LLMUnavailable

CAMPAIGN_ID = uuid.uuid4()
RUN_ID = str(uuid.uuid4())
COHORT = str(uuid.uuid4())
VAR_A, VAR_B = str(uuid.uuid4()), str(uuid.uuid4())

COHORT_LABELS = {COHORT: "Price sensitive"}
VARIANT_OFFERS = {
    VAR_A: {"label": "40% off for 3 months", "percent_off": 40, "duration_months": 3},
    VAR_B: {"label": "What's new tour", "percent_off": 0, "duration_months": 1},
}


def _variant(vid, label, recipients, clicks, conversions, mrr):
    return VariantMetrics(
        cohort_id=COHORT, variant_id=vid, variant_label=label,
        recipients=recipients, clicks=clicks, conversions=conversions, mrr_recovered_cents=mrr,
    )


def _metrics():
    simulated = SourceMetrics(
        recipients=200, clicks=53, conversions=17, mrr_recovered_cents=78400,
        variants=[_variant(VAR_A, "A", 100, 40, 15, 70000), _variant(VAR_B, "B", 100, 13, 2, 8400)],
    )
    live = SourceMetrics(
        recipients=3, clicks=1, conversions=1, mrr_recovered_cents=1200,
        variants=[_variant(VAR_A, "A", 2, 0, 0, 0), _variant(VAR_B, "B", 1, 1, 1, 1200)],
    )
    return CampaignMetrics(campaign_id=CAMPAIGN_ID, live=live, simulated=simulated)


def test_template_mentions_both_sources_separately():
    text = template_recommendation(build_report_input(COHORT_LABELS, VARIANT_OFFERS, _metrics()))
    live_part, sim_part = text.split("Simulated results")[0], text.split("Simulated results")[1]
    assert "Live results: 1 conversion from 3 recipients" in live_part
    assert "variant B (What's new tour) converted best, 1/1" in live_part
    assert "17 conversions from 200 recipients" in sim_part
    assert "variant A (40% off for 3 months) converted best, 15/100, against B 2/100" in sim_part
    # never adds the two sources together (17 + 1 = 18, 200 + 3 = 203)
    assert "18 conversions" not in text and "203" not in text
    assert "not statistically significant" in text


def test_template_handles_no_recipients_and_no_conversions():
    empty = CampaignMetrics(campaign_id=CAMPAIGN_ID, live=SourceMetrics(), simulated=SourceMetrics(
        recipients=10, variants=[_variant(VAR_A, "A", 10, 0, 0, 0)]))
    text = template_recommendation(build_report_input(COHORT_LABELS, VARIANT_OFFERS, empty))
    assert "Live results: no recipients yet." in text
    assert "no conversions yet" in text


def test_llm_input_keeps_sources_apart_and_has_only_labels_offers_metrics():
    data = build_report_input(COHORT_LABELS, VARIANT_OFFERS, _metrics())
    assert set(data) == {"live", "simulated"}
    assert data["simulated"]["totals"]["conversions"] == 17
    assert data["live"]["totals"]["conversions"] == 1
    variant = data["simulated"]["cohorts"][0]["variants"][0]
    assert set(variant) == {"variant", "offer", "percent_off", "duration_months", "recipients", "clicks",
                            "page_views", "checkouts_started", "conversions", "mrr_recovered_cents"}
    system = build_messages(data)[0]["content"]
    assert "never claim statistical significance" in system
    assert "never add them together" in system


def _fake_db():
    db = MagicMock()
    tables = {}

    def table(name):
        if name not in tables:
            t = MagicMock()
            data = {
                "campaigns": [{"id": str(CAMPAIGN_ID), "run_id": RUN_ID}],
                "cohorts": [{"id": COHORT, "label": "Price sensitive"}],
                "variants": [{"id": VAR_A, "offers": VARIANT_OFFERS[VAR_A]}, {"id": VAR_B, "offers": VARIANT_OFFERS[VAR_B]}],
            }.get(name, [])
            t.select.return_value.eq.return_value.execute.return_value.data = data
            t.upsert.side_effect = lambda row, **kw: MagicMock(execute=lambda: MagicMock(data=[{"id": "rep-1", **row}]))
            tables[name] = t
        return tables[name]

    db.table.side_effect = table
    return db, tables


def test_report_route_falls_back_to_template_and_upserts(client, monkeypatch):
    db, tables = _fake_db()
    monkeypatch.setattr(report_mod, "get_supabase", lambda: db)
    monkeypatch.setattr(report_mod, "compute_metrics", lambda cid: _metrics())

    async def unavailable(*a, **kw):
        raise LLMUnavailable("down")
    monkeypatch.setattr(report_mod, "complete_json", unavailable)

    r = client.post(f"/api/campaigns/{CAMPAIGN_ID}/report")
    assert r.status_code == 200
    body = r.json()
    assert body["generated_by"] == "template"
    assert body["campaign_id"] == str(CAMPAIGN_ID)
    assert "Live results" in body["recommendation"]
    kwargs = tables["reports"].upsert.call_args.kwargs
    assert kwargs == {"on_conflict": "campaign_id"}


def test_report_route_uses_llm_when_available(client, monkeypatch):
    db, _ = _fake_db()
    monkeypatch.setattr(report_mod, "get_supabase", lambda: db)
    monkeypatch.setattr(report_mod, "compute_metrics", lambda cid: _metrics())

    async def ok(step, msgs, schema, run_id, **kw):
        assert step == "report" and str(run_id) == RUN_ID
        return schema(recommendation="Use variant A for Price sensitive.")
    monkeypatch.setattr(report_mod, "complete_json", ok)

    body = client.post(f"/api/campaigns/{CAMPAIGN_ID}/report").json()
    assert body["generated_by"] == "llm"
    assert body["recommendation"] == "Use variant A for Price sensitive."


def test_report_route_unknown_campaign_404(client, monkeypatch):
    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    monkeypatch.setattr(report_mod, "get_supabase", lambda: db)
    assert client.post(f"/api/campaigns/{uuid.uuid4()}/report").status_code == 404


def test_usage_totals_add_up():
    today = [{"input_tokens": 1000, "output_tokens": 500}, {"input_tokens": 200, "output_tokens": None}]
    run = [{"input_tokens": 1000, "output_tokens": 500}]
    usage = summarize_usage(today, "run-1", run)
    assert usage["tokens_today"] == 1700
    assert usage["latest_run_tokens"] == 1500
    assert usage["latest_run_id"] == "run-1"
    assert usage["daily_allowance"] == DAILY_TOKEN_ALLOWANCE == 200_000
    assert usage["reserve"] == DEMO_TOKEN_RESERVE == 60_000
    assert usage["remaining_before_reserve"] == 200_000 - 60_000 - 1700


def test_usage_with_no_runs_or_calls():
    usage = summarize_usage([], None, [])
    assert usage["tokens_today"] == 0 and usage["latest_run_tokens"] == 0 and usage["latest_run_id"] is None


def test_usage_for_one_run():
    run = [{"input_tokens": 1000, "output_tokens": 500}, {"input_tokens": None, "output_tokens": 20}]
    usage = summarize_usage([], None, [], "run-7", run)
    assert usage["run_id"] == "run-7"
    assert usage["run_tokens"] == 1520
    assert usage["run_llm_calls"] == 2
    assert usage["llm_cost_usd"] == 0


def test_usage_without_a_run_has_no_run_fields():
    usage = summarize_usage([], None, [])
    assert "run_tokens" not in usage
    assert usage["llm_cost_usd"] == 0
