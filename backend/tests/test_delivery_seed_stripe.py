# Owned by feature/delivery. Tests the pure parts of scripts/seed_stripe.py; no Stripe calls.
from collections import Counter
from datetime import UTC, datetime, timedelta

from app.services.email_client import parse_allowlist
from scripts.seed_stripe import (
    CANCELLATION_COMMENTS,
    STRIPE_FEEDBACK_VALUES,
    coupon_id_for,
    coupon_params,
    live_customer_specs,
    new_specs,
    offers_needing_coupons,
    simulated_customer_specs,
)

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)


def test_about_fifty_distinct_comments_across_valid_feedback_values():
    comments = [comment for comment, _ in CANCELLATION_COMMENTS]
    assert 45 <= len(set(comments)) <= 60
    feedback = {value for _, value in CANCELLATION_COMMENTS}
    assert feedback <= STRIPE_FEEDBACK_VALUES
    assert len(feedback) >= 5


def test_simulated_specs_have_numbered_example_emails_and_are_marked_simulated():
    specs = simulated_customer_specs(200, NOW)
    assert len(specs) == 200
    assert specs[0]["email"] == "user001@example.com"
    assert specs[199]["email"] == "user200@example.com"
    assert len({spec["email"] for spec in specs}) == 200
    assert all(spec["simulated"] is True for spec in specs)


def test_simulated_specs_churned_in_the_past_90_days():
    for spec in simulated_customer_specs(200, NOW):
        churned_at = datetime.fromisoformat(spec["churned_at"])
        assert NOW - timedelta(days=90) <= churned_at < NOW


def test_simulated_specs_use_every_comment_and_are_repeatable():
    specs = simulated_customer_specs(200, NOW)
    assert {spec["comment"] for spec in specs} == {comment for comment, _ in CANCELLATION_COMMENTS}
    assert specs == simulated_customer_specs(200, NOW)


def test_simulated_specs_keep_comment_and_feedback_paired():
    pairs = dict(CANCELLATION_COMMENTS)
    for spec in simulated_customer_specs(200, NOW):
        assert pairs[spec["comment"]] == spec["feedback"]


def test_live_specs_one_per_allowlisted_address_and_not_simulated():
    specs = live_customer_specs(["ana@team.dev", "bo@team.dev"], NOW)
    assert [spec["email"] for spec in specs] == ["ana@team.dev", "bo@team.dev"]
    assert all(spec["simulated"] is False for spec in specs)
    assert all(spec["comment"] and spec["feedback"] in STRIPE_FEEDBACK_VALUES for spec in specs)


def test_parse_allowlist_trims_lowercases_and_drops_blanks():
    assert parse_allowlist(" Ana@Team.dev, ,bo@team.dev ,ana@team.dev") == ["ana@team.dev", "bo@team.dev"]
    assert parse_allowlist("") == []


def test_new_specs_skips_existing_emails_case_insensitively():
    specs = [{"email": "user001@example.com"}, {"email": "user002@example.com"}]
    assert new_specs(specs, {"USER001@example.com"}) == [{"email": "user002@example.com"}]


def test_only_discounted_offers_without_a_coupon_need_one():
    offers = [
        {"id": "a", "percent_off": 0, "duration_months": 0, "stripe_coupon_id": None},
        {"id": "b", "percent_off": 10, "duration_months": 3, "stripe_coupon_id": None},
        {"id": "c", "percent_off": 25, "duration_months": 3, "stripe_coupon_id": "winback_25_3m"},
    ]
    assert [offer["id"] for offer in offers_needing_coupons(offers)] == ["b"]


def test_coupon_params_repeat_for_the_offer_duration():
    offer = {"label": "40% off for 2 months", "percent_off": 40, "duration_months": 2}
    assert coupon_id_for(offer) == "winback_40pct_2m"
    assert coupon_params(offer) == {
        "id": "winback_40pct_2m",
        "name": "40% off for 2 months",
        "percent_off": 40,
        "duration": "repeating",
        "duration_in_months": 2,
    }
