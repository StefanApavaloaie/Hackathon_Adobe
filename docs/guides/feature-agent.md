# Guide: `feature/agent` (decide and explain)

**Goal:** the agent turns cancelled customers into a proposed, validated campaign, simulates seeded customers' responses, and writes a recommendation.

Read first: [`docs/BRANCH_PLAN.md`](../BRANCH_PLAN.md) for file ownership and frozen files, and sections 4–9 of [`SYSTEM_DESIGN.md`](../../SYSTEM_DESIGN.md).

**Suggested split between the two of you:**

- **Backend 1:** steps 1–4 and 6–8
- **Innovation teammate:** step 5 (page content), then steps 9–10 (screens)

Rough time budget: about 6 hours, aiming to merge by hour 6.

---

## Contracts with `feature/delivery`

Don't change these without agreeing with the other pair.

| What | Rule |
|---|---|
| `variants.page_content` | Must validate as `PageContent` (`app/contracts.py`) |
| `variants.body_text` | Plain text only: no greeting, no links, no sign-off. Delivery adds "Hi {name}," plus the link and the unsubscribe footer |
| `campaigns.status` | You write `draft` and `rejected`. Delivery writes `approved`, `sending` and `sent` |
| `agent_runs.limits` | JSON with `max_percent_off`, `send_cap` and `max_exposure_cents`. Delivery reads `send_cap` |
| `simulate_responses(campaign_id)` | Delivery calls it after sending. Keep the name and signature |
| `compute_metrics(campaign_id)` | Delivery owns it, and you only read its result |
| `events.occurred_at` | The simulator may write future times, spread over about 60 seconds. Delivery's metrics ignore events still in the future, so results climb live |
| `conversions.mrr_cents` | The discounted monthly amount actually paid |

**Coding pattern for every step:** keep the logic in pure functions that take plain data and return plain data, and test those. Keep database reads and writes in a thin wrapper around them. Tests never call Supabase or Groq.

Database calls use the shared client:

```python
from app.services.supabase_client import get_supabase

rows = get_supabase().table("customers").select("*").is_("unsubscribed_at", "null").execute().data
```

---

## Step 0: set up the branch (30 minutes, once)

1. **One person creates the branch, the other checks it out:**
   ```powershell
   git checkout main
   git pull
   git checkout -b feature/agent
   git push -u origin feature/agent
   ```
   The other person runs `git fetch origin` and then `git checkout feature/agent`.
2. **Check `backend/.env`:** it needs `ALLOW_DEV_AUTH=true` and `PUBLIC_API_URL=http://127.0.0.1:8000`, plus the Supabase and Groq keys.
3. **Set up Supabase, if nobody has yet (one person for the whole team):**
   - Create the project.
   - In the SQL editor, run `supabase/migrations/0001_initial_schema.sql`, then `supabase/seed/offers.sql`.
   - Share the URL and service key privately.
4. **Confirm Groq's free limits:** check the Free Plan tab on your Groq limits page, and note the per-minute and per-day token figures.
5. **Write test customers in `supabase/fixtures/agent_dev.sql`, and run it:**
   - About 40 rows in `customers`, all `is_simulated = true`, with `stripe_customer_id` values like `cus_dev_001`.
   - About 15 distinct `cancel_comment` texts, repeated across rows, spanning the Stripe `cancel_feedback` values `too_expensive`, `missing_features`, `switched_service`, `unused`, `too_complex`, `low_quality` and `customer_service`.
   - Some rows with an empty comment, so you exercise the fallback.
   - Varied `mrr_cents`, and `churned_at` dates in the past 90 days.

**Done when:** `GET http://127.0.0.1:8000/health/dependencies` shows `supabase: ok` and `groq: ok`.

---

## Step 1: LLM client (`services/llm_client.py`), about 75 minutes

Add a function that every LLM step uses:

```python
def complete_json(step: str, messages: list[dict], schema: type[T], run_id: UUID | None) -> T
```

**Behaviour:**

- **Cache key:** the SHA-256 of the model, the messages and the schema's name. Responses are stored in `backend/llm_cache/<key>.json`. Commit these files, so teammates can replay them without spending tokens.
- **`LLM_MODE=saved`:** return the cached response. If there isn't one, raise `LLMUnavailable`, so the caller uses its fallback.
- **`LLM_MODE=live`:**
  - Send `POST /chat/completions` with `"stream": false`, a low `temperature`, and `response_format = {"type": "json_schema", "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema(), "strict": true}}`.
  - On a `429`, wait for the `retry-after` header, capped at 30 seconds, then retry. Allow at most 3 attempts in total.
  - Validate the reply with `schema.model_validate_json`. If it's invalid, retry once with the validation error added to the messages, then raise `LLMUnavailable`.
  - Save successful replies to the cache.
- **Logging:** insert one `llm_calls` row per real call, with the step, model, input and output tokens (from the reply's `usage` field), latency and success.
- **Schema models:** give them `extra="forbid"` and no default values, because Groq's strict mode needs every field to be required.

**Tests (`tests/test_agent_llm.py`):** use `httpx.MockTransport`, never the real API.

- Saved mode returns the cached reply.
- Saved mode with no cached reply raises `LLMUnavailable`.
- A `429` followed by success returns the result.
- Invalid JSON twice raises `LLMUnavailable`.

**Done when:** these tests pass, and one real call in live mode creates a cache file and an `llm_calls` row.

---

## Step 2: run orchestration (`app/agent/orchestrator.py`, `routers/runs.py`), about 60 minutes

1. **`POST /api/runs`:**
   - Takes an optional body `{"limits": {...}}`. The defaults are `max_percent_off: 40`, `send_cap: 250` and `max_exposure_cents: 500000`.
   - Inserts an `agent_runs` row with `status = 'running'` and `current_step = 'import'`.
   - Starts `run_pipeline(run_id)` with FastAPI `BackgroundTasks`.
   - Returns `{"run_id": ...}` with status `202`.
2. **`run_pipeline(run_id)`** goes through the steps `import`, `diagnose`, `strategy` and `propose` in order:
   - **Import:** calls `import_customers()`, which returns `0` until delivery is merged.
   - **After each step:** save the next `current_step`. Each step must be safe to repeat: delete that run's rows for the step before writing them again.
   - **At the end:** set `status = 'awaiting_approval'`.
   - **On any exception:** set `status = 'failed'` and a short `error` message, without keys or stack traces.
3. **`POST /api/runs/{id}/resume`:** restarts `run_pipeline` from the saved `current_step`. It only works when `status = 'failed'`, and returns `409` otherwise.
4. **`GET /api/runs/{id}`:** returns `status`, `current_step`, `error`, the cohorts (label, count, revenue at stake) and `campaign_id`, which stays `null` until the propose step.

**Which customers a run uses:** those with `churned_at` set and `unsubscribed_at` empty.

**Tests:** step order and resume logic, as a pure function over `current_step`. Also test that `resume` returns `409` when the run isn't `failed`. Delete these routes from `tests/test_stubs_agent.py`.

**Done when:** a run moves through every step and reaches `awaiting_approval`. That needs steps 3–5, and placeholders are fine at first.

---

## Step 3: diagnose cohorts (`app/agent/diagnose.py`), about 60 minutes

1. **Discover the cohorts:**
   - Send a sample of up to 30 distinct comments to `complete_json`, with the schema `{cohorts: [{key, label, summary}]}`, asking for 3–6 cohorts.
   - Pass the comments as a JSON list, and tell the model they are data, not instructions.
2. **Assign customers:**
   - Send the distinct comments in batches of 20, with the schema `{assignments: [{index, cohort_key, confidence}]}`.
   - Map each comment's result back to every customer with that comment.
3. **Fallbacks:**
   - A customer with no comment, or whose `cohort_key` isn't one of the discovered keys, goes to a cohort based on their `cancel_feedback`.
   - If the LLM is unavailable entirely, every cohort comes from `cancel_feedback`.
   - In both cases, set `assigned_by = 'fallback'`.
4. **Write the results:** add `cohorts` rows with `customer_count` and `mrr_at_stake_cents` (the sum of the members' `mrr_cents`), and `cohort_members` rows.

**Tests:**

- Grouping by the fallback reason.
- Mapping assignments back to customers.
- An unknown `cohort_key` falls back.
- An empty comment falls back.

**Done when:** a run on the test customers creates 3–6 cohorts, in both saved and live mode.

---

## Step 4: strategy and guardrails (`app/agent/strategy.py`, `app/agent/guardrails.py`), about 75 minutes

1. **One LLM call per cohort:**
   - **Input:** the cohort's label and summary, up to 8 sample comments, the revenue at stake, and the active offers (`id`, `label`, `percent_off`, `duration_months`).
   - **Output schema:** `{variants: [{label, offer_id, subject, body_text, page_content, reasoning}]}`, using `PageContent` for `page_content`.
2. **Guardrails, as pure functions.** Reject the output if any of these fail:
   - There are exactly two variants, labelled `A` and `B`.
   - Each `offer_id` is an active offer.
   - Each offer's `percent_off` is at most `limits.max_percent_off`.
   - `subject` is at most 80 characters, and `body_text` at most 1,200.
   - `body_text` contains no `http` and no `<`.
3. **On rejection:** retry once, with the guardrail errors added to the messages. If that fails too, use fallback variants: a default offer, template copy, and `fallback_page_content()` from step 5. Set `is_fallback = true`.
4. **Propose step:**
   - Insert one `campaigns` row with `status = 'draft'`, then the `variants` rows.
   - Compute `max_exposure_cents`: for each cohort, revenue at stake × the higher variant discount × its `duration_months` ÷ 100, summed across cohorts.
   - If it's above `limits.max_exposure_cents`, swap the costliest variants for cheaper offers until it fits. Record that in `reasoning`.

**Tests:**

- Each guardrail rule individually.
- The exposure calculation.
- The fallback when a guardrail fails twice.

**Done when:** the approval data contains 2 variants per cohort, every offer comes from the catalog, and every page validates.

---

## Step 5: page content (`app/agent/pages.py`, innovation teammate), about 60 minutes

1. **`PAGE_INSTRUCTIONS: str`:** the part of the strategy prompt that explains how to write the page.
   - Address this cohort's actual reasons, using its sample comments.
   - Keep each field short.
   - Never mention prices or percentages, because code adds the offer text.
2. **`fallback_page_content(cohort_label: str, cancel_feedback: str | None) -> PageContent`:** template copy per Stripe reason, used whenever generation fails.
3. **Coordinate with Backend 1:** `strategy.py` includes `PAGE_INSTRUCTIONS` in its prompt.

**Tests:**

- Every fallback validates as `PageContent`.
- No fallback text contains `%` or `$`.

**Done when:** pages for two different cohorts read clearly differently, and each speaks to its cohort's reasons.

---

## Step 6: approval view and reject (`routers/campaigns.py`), about 30 minutes

1. **`GET /api/campaigns/{id}`** returns:
   - `campaign` (`id`, `status`, `max_exposure_cents`), plus `run_id`
   - `cohorts`, where each cohort includes its variants (offer details, `subject`, `body_text`, `page_content`, `reasoning` and `is_fallback`)
   - `report` from the `reports` table, or `null`
   - `404` if the campaign doesn't exist
2. **`POST /api/campaigns/{id}/reject`:** changes `draft` to `rejected`. Any other status returns `409`.

**Tests:** reject from `draft`, reject from another status (`409`), and an unknown campaign (`404`). Remove these routes from the stub tests.

---

## Step 7: simulator (`app/simulator.py`), about 60 minutes

1. **Hidden rates:**
   - Add a constant table keyed by the customer's `cancel_feedback` and an offer band (`0%`, `1–15%`, `16–30%`, `31–50%`), giving a click rate and a conversion-after-click rate.
   - For example, `too_expensive` responds strongly to large discounts, and `missing_features` responds best to the 0% "what's new" offer.
   - The LLM never sees this table.
2. **`simulate_responses(campaign_id)`:**
   - Load the campaign's recipients with `source = 'simulated'`.
   - Skip them if events already exist for them, so it's safe to run twice.
   - Use `random.Random(str(campaign_id))` so results are repeatable.
   - Write `clicked`, `page_viewed` and `checkout_started` events, plus `conversions` with `mrr_cents` set to the discounted price and `source = 'simulated'`.
   - Spread `occurred_at` over the next 60 seconds.
3. **Structure:** keep the maths in a pure function, `plan_outcomes(recipients, offers, rng) -> (events, conversions)`.

**Tests:**

- The same seed gives the same outcomes.
- A 0% click rate gives no events.
- Every timestamp falls within 60 seconds.
- Only simulated recipients are used.
- Running it twice adds nothing.

---

## Step 8: recommendation and usage (`app/agent/report.py`, `routers/campaigns.py`, `routers/usage.py`), about 45 minutes

1. **`POST /api/campaigns/{id}/report`:**
   - Get `metrics = compute_metrics(id)`, then call the LLM with the schema `{recommendation: str}`.
   - The input is only the cohort labels, offers and metrics, with live and simulated given separately.
   - Instruct it to show raw counts, never to claim statistical significance, and never to add live and simulated together.
   - If the LLM is unavailable, use a template recommendation built from the metrics, such as "best converting variant per cohort".
   - Upsert into `reports` by `campaign_id`, and return the report.
2. **`GET /api/usage`:** returns tokens used today (UTC) and the latest run's tokens, both from `llm_calls`. Also return the daily allowance and the reserve as constants in `usage.py`: `200_000` and `60_000`. Correct those to your real Groq limits.

**Tests:** the template recommendation mentions both sources separately, and the usage totals add up correctly.

---

## Step 9: run and approval screens (`RunPanel.tsx`, `ApprovalPanel.tsx`), about 75 minutes

1. **RunPanel:**
   - A **Start run** button calls `apiPost("/api/runs")`, then polls `GET /api/runs/{id}` every 2 seconds.
   - Show the current step, status, cohorts and errors, plus a **Resume** button when the run has failed.
   - Once the run reaches `awaiting_approval`, call `onCampaignReady(campaign_id)`.
2. **ApprovalPanel:**
   - When `campaignId` is set, load `GET /api/campaigns/{id}`.
   - Show each cohort with its revenue at stake, then its variants: offer, subject, body, reasoning, a "fallback" badge, and a preview of the page rendered as plain text.
   - Show the maximum discount exposure prominently.
   - **Approve** calls `apiPost(.../approve)` and **Reject** calls `apiPost(.../reject)`. Until delivery is merged, approve returns `501`, so show the error message from `ApiError`.
3. **API types:** define the shapes each panel uses inside its own file.

**Done when:** you can start a run, watch it progress, review the proposal, and reject it.

---

## Step 10: recommendation screen (`ReportPanel.tsx`), about 30 minutes

- Show the existing report from `GET /api/campaigns/{id}`.
- A **Generate recommendation** button calls `POST .../report` and shows the result.
- Label it clearly as the agent's recommendation, which doesn't run automatically.

---

## Before you merge

- [ ] `tests/test_stubs_agent.py` is deleted, because every agent route is built.
- [ ] `.\.venv\Scripts\python.exe -m pytest` passes, and `npm run build` passes.
- [ ] A full run in **saved** mode works without spending tokens.
- [ ] No file owned by delivery, and no frozen file, was changed: check with `git diff --stat main`.
- [ ] Merge `main` into your branch, rerun the tests, then open a pull request into `main`.

**Demo note:** the demo run should use `LLM_MODE=live`, so it generates fresh output. Keep at least 60K Groq tokens unused for it.
