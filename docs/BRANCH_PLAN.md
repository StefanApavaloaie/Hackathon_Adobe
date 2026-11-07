# Two-branch plan

Splits every feature in [`SYSTEM_DESIGN.md`](../SYSTEM_DESIGN.md) into two branches that never edit the same file.

**Branch A, `feature/agent`: decide and explain.** It goes from imported customers to a proposed campaign, then simulates the seeded customers' responses and writes the recommendation.

**Branch B, `feature/delivery`: act and measure.** It handles login, approval and sending, then the click, page, checkout and webhook trail, and results.

B is larger than A. A's work is mainly LLM work, while B has more integrations and screens.

**The core rule: every file belongs to exactly one branch.** The branches share data only through the database tables and the connection points below, which step 0 created on `main`.

## Step 0: done on `main`

| Change | Why |
|---|---|
| Approve and results moved into `routers/sending.py`, and every router registered in `main.py` | Neither branch needs to edit `main.py` |
| Four connection points created as placeholders (below) | Each branch can call the other's code before it exists |
| `PageContent` model in `app/contracts.py` | Both branches use the same page shape |
| Settings `PUBLIC_API_URL`, `EMAIL_FROM` and `ALLOW_DEV_AUTH` | Neither branch needs to edit `config.py` |
| Offer catalog in `supabase/seed/offers.sql` | A chooses offers and B creates their Stripe coupons |
| Stub tests split into `test_stubs_agent.py` and `test_stubs_delivery.py`, with shared fixtures in `conftest.py` | Each branch deletes only its own stub tests |
| Dashboard layout, panel files, and routes for `/login`, `/w/:token` and `/thanks` | Neither branch needs to edit `main.tsx` or the layout |
| `apiGet` and `apiPost` in `lib/api.ts`, which add the login token from `lib/auth.ts` | API requests will carry the token once B implements login |

**Offer catalog:** no discount (show what's new), 10% for 3 months, 25% for 3 months, and 40% for 2 months. The database caps discounts at 50%.

## Connection points

Each one exists on `main` as a placeholder that returns a safe value. The owning branch writes the real version **without changing its name, inputs or return type**, and the other branch can call it from the start.

| Function (file) | Owner | Called by | Placeholder behaviour |
|---|---|---|---|
| `import_customers() -> int` (`app/stripe_import.py`) | B | A, when starting a run | Returns `0`, so A uses its own test customers |
| `simulate_responses(campaign_id: UUID) -> None` (`app/simulator.py`) | A | B, after sending | Does nothing |
| `compute_metrics(campaign_id: UUID) -> CampaignMetrics` (`app/metrics.py`) | B | A's report | Returns all counts as zero |
| `require_user() -> AuthUser` (`app/auth.py`) | B | Every protected route, at router level | Allows requests only when `ALLOW_DEV_AUTH=true` |
| `getAccessToken()` (`frontend/src/lib/auth.ts`) | B | `lib/api.ts` | Returns `null` |
| `<RequireLogin>` (`frontend/src/components/RequireLogin.tsx`) | B | `main.tsx`, around the dashboard | Shows the page to everyone |

**`ALLOW_DEV_AUTH` is a safeguard.** Local `.env` files set it to `true`, but Render never has it, so deploying before B's real login check is merged blocks protected routes with a `503` instead of leaving them open.

**Dashboard panel props are fixed too.** `RunPanel` receives `onCampaignReady(campaignId)`, and the other panels receive `campaignId`. The campaign is stored in the URL as `?campaign=<id>`, so refreshing the page keeps it.

## Shared database tables

`0001_initial_schema.sql` is fixed. Each table has one writer.

| Table | Written by | Read by |
|---|---|---|
| `customers` | B (import and unsubscribe) | A |
| `offers` | Step 0 (catalog), then B (Stripe coupon IDs) | Both |
| `agent_runs`, `cohorts`, `cohort_members`, `variants`, `llm_calls`, `reports` | A | Both |
| `campaigns` | A writes `draft` and `rejected`; B writes `approved`, `sending` and `sent` | Both |
| `recipients`, `processed_webhooks` | B | A's simulator reads `recipients` |
| `events`, `conversions` | B for live recipients, A's simulator for simulated ones | B's metrics |

`variants.page_content` must always validate as `PageContent`.

## Branch A, `feature/agent`: decide and explain

| Feature | Design ref | Files A owns |
|---|---|---|
| LLM client: pacing, 429 handling, `LLM_MODE=saved`, token logging | NFR, R4, R13 | `services/llm_client.py` |
| Run orchestration, with resumable steps | F2, reliability | `app/agent/orchestrator.py`, `routers/runs.py` |
| Diagnose cohorts, with fallback to Stripe's cancellation reason | F2 | `app/agent/diagnose.py` |
| Strategy and two variants per cohort | F3 | `app/agent/strategy.py` |
| Guardrails: catalog-only offers, discount cap, maximum discount exposure | F4 | `app/agent/guardrails.py` |
| Page content generation | F8 (generation) | `app/agent/pages.py` |
| Approval view and reject | F5 | `routers/campaigns.py` |
| Recommendation, with a template fallback | F13 | `app/agent/report.py`, `routers/campaigns.py` |
| Simulator with hidden response rates | F11 | `app/simulator.py` |
| Usage endpoint | Section 7 | `routers/usage.py` |
| Run, approval and recommendation screens | F5, F13 | `frontend/src/panels/RunPanel.tsx`, `ApprovalPanel.tsx`, `ReportPanel.tsx` |
| Test customers for development | Not in the design | `supabase/fixtures/agent_dev.sql` |
| Tests | | `tests/test_stubs_agent.py`, `tests/test_agent_*.py` |

## Branch B, `feature/delivery`: act and measure

| Feature | Design ref | Files B owns |
|---|---|---|
| Login: backend check and login page | F14 | `app/auth.py`, `frontend/src/lib/auth.ts`, `frontend/src/lib/supabase.ts`, `frontend/src/components/RequireLogin.tsx`, `frontend/src/pages/LoginPage.tsx` |
| Stripe seed script, customer import, coupons | F1, R6, R7 | `backend/scripts/seed_stripe.py`, `app/stripe_import.py`, `services/stripe_client.py` |
| Approve: create recipients, enforce the send cap, send live email | F4 (send cap), F6 | `routers/sending.py`, `app/delivery/send.py` |
| Email with allow-list and unsubscribe link | F6, F15 | `services/email_client.py`, `app/delivery/email_templates.py` |
| Click tracking and unsubscribe | F7, F15 | `routers/tracking.py` |
| Public page API and checkout | F8 (data), F9 | `routers/pages.py` |
| Stripe and Resend webhooks, attribution | F9, F10 | `routers/webhooks.py` |
| Metrics and results endpoint | F10, F12 | `app/metrics.py`, `routers/sending.py` |
| Win-back page template and thank-you page | F8 (rendering) | `frontend/src/pages/WinbackPage.tsx`, `ThanksPage.tsx` |
| Results screen, with live and simulated figures kept separate | F12 | `frontend/src/panels/ResultsPanel.tsx` |
| Deployment and keep-awake ping | Section 10 | `render.yaml`, `frontend/vercel.json` |
| Tests | | `tests/test_stubs_delivery.py`, `tests/test_delivery_*.py` |

## Frozen files

Neither branch edits these. Change them only through a small pull request to `main`, then update both branches from `main`.

- **Backend:** `app/main.py`, `app/config.py`, `app/errors.py`, `app/contracts.py`, `routers/health.py`, `services/supabase_client.py`, `tests/conftest.py`, `tests/test_foundation.py`, `tests/test_contracts.py`
- **Frontend:** `src/main.tsx`, `src/lib/api.ts`, `src/pages/DashboardPage.tsx`, `src/panels/StatusPanel.tsx`
- **Shared:** `requirements.txt`, `requirements-dev.txt`, `package.json`, `package-lock.json`, `.env.example` files, `supabase/migrations/0001_initial_schema.sql`, `supabase/seed/offers.sql`, `SYSTEM_DESIGN.md`, `docs/BRANCH_PLAN.md`

## Rules for both branches

1. **Don't edit a file the other branch owns, or a frozen file.** If you must, make the smallest possible change in its own pull request to `main`.
2. **Add no new dependencies on a branch.** The design needs nothing beyond what's installed.
3. **Schema changes go in new migrations:** A uses `0100`–`0199` and B uses `0200`–`0299`.
4. **Define the API shapes a panel uses inside that panel's file.** There's no shared types file.
5. **Keep tests in your own files.** Delete each stub test as you build its route.
6. **Within a branch, the two people should also split files** between themselves.

## Merge order and timing

- **About hour 6:** merge whichever branch is ready first into `main`.
- **Before merging the second branch:** merge `main` into it, run the backend tests and the frontend build, then merge.
- **Hour 7 checkpoint:** with both merged, test the whole flow: start a run, approve, receive the email, click, open the page, pay, and see the conversion.

**Expected conflicts:** none in files, since every file has one owner. Integration problems are still possible, because the branches can disagree about data, such as what `variants.page_content` contains or which campaign statuses are used. Stick to the connection points and the tables above to keep them aligned.

## After both are merged (on `main`)

1. Test the whole flow end to end.
2. Confirm `ALLOW_DEV_AUTH` is unset on Render, and that the real login check is in place before deploying.
3. **Stretch:** execute the recommendation as a second round.

## Dashboard display components (added on `frontend/Stefan`)

The dashboard at `/` now shows the reference design with **demo data**. It no longer mounts `RunPanel`, `ApprovalPanel`, `ResultsPanel` or `ReportPanel`.

- **Where:** `frontend/src/dashboard/sections.tsx` holds `Hero`, `Guardrails`, `Reasons`, `Results` and `NextStep`. Each takes its data as props, and the types are in `frontend/src/dashboard/demoData.ts`.
- **To connect real data:** load it from the API, map it to the `DashboardData` shape, and pass it in place of `DEMO` in `DashboardPage.tsx`. Remove the "Demo data" label once nothing on the page is demo.
- **Panels:** the panel files still exist. Logic built there (loading, approve, reject, polling) can move into a hook that feeds these components. Approve and reject are display-only buttons until wired up.
- **Ownership:** `frontend/src/dashboard/` and `frontend/src/styles/` belong to the front-end lead. Change them through a pull request to `main`.

## Suggested people per branch

- **Branch A:** Backend 1 plus the innovation teammate, who builds page generation and the approval screen that previews the pages.
- **Branch B:** Backend 2 plus the front-end lead, who builds login, the results screen and the win-back page.

## Changes from `SYSTEM_DESIGN.md`

- **Simulator:** assigned to A, which matches the design's owner, Backend 1.
- **Recommendation's metrics:** these come from B through `compute_metrics`, so the numbers have one source.
- **Customer import:** moved from "starting a run" to B, joined by a connection point.
- **Screens:** split between the branches, rather than all belonging to the front-end lead.
