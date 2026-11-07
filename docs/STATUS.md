# Status against SYSTEM_DESIGN.md

Checked on `main` at `9c06dc3`, 2026-11-07, after both branches and `frontend/Stefan` were merged, then updated for `final_touch/Stefan` at `4463dd2` (New run button, Groq fixes, LLM cache). The backend tests pass (188), and the frontend builds.

Key: **[x]** done and working locally, **[~]** partly done, **[ ]** not started.

## Functional requirements

| | ID | Requirement | Where it stands |
|---|---|---|---|
| [x] | F1 | Import cancelled subscribers from Stripe | `stripe_import.py`, `scripts/seed_stripe.py` |
| [x] | F2 | LLM cohorts with revenue at stake | `agent/diagnose.py`, falls back to Stripe's feedback value |
| [x] | F3 | Catalog offer plus two variants per cohort, with reasoning | `agent/strategy.py` |
| [x] | F4 | Discount, send-cap and exposure limits in code | `agent/guardrails.py`, `delivery/send.py` |
| [~] | F5 | One approval screen | Dashboard shows cohorts, offers, reasoning and exposure, and Approve/Reject work. **Guardrail limits are hard-coded defaults** (`DEFAULT_LIMITS` in `useDashboardData.ts`) because the campaign API doesn't return the run's limits. No preview of the personalised pages |
| [x] | F6 | Real email only to allow-listed recipients | `delivery/send.py`, `email_client.py`. Not yet confirmed from the deployed backend |
| [x] | F7 | Click tracking via `/r/{token}` | `routers/tracking.py` |
| [x] | F8 | Personalised page per cohort and variant | `agent/pages.py` generates it, `WinbackPage.tsx` renders it |
| [~] | F9 | Stripe test checkout, confirmed by webhook | Code works. Locally it needs `stripe listen --events checkout.session.completed --forward-to 127.0.0.1:8000/webhooks/stripe`. No webhook endpoint registered in the Stripe dashboard for the deployed backend yet |
| [x] | F10 | Attribute conversions to recipient, variant, cohort, campaign | `webhooks.py`, `metrics.py` |
| [x] | F11 | Simulated responses from hidden rates | `simulator.py`, called after sending |
| [x] | F12 | Live and simulated results kept separate | Dashboard `Results` section, polls every 3 s |
| [x] | F13 | Written recommendation, never executed | `agent/report.py`, "Generate recommendation" button |
| [ ] | F14 | One login protecting the dashboard | **Backend check is done** (`auth.py`). **Frontend is still the step-0 placeholder:** `LoginPage.tsx` says "Not implemented yet", `RequireLogin` lets everyone in, `getAccessToken()` returns `null`. `VITE_SUPABASE_URL` is empty in `frontend/.env`. Once deployed without `ALLOW_DEV_AUTH`, every dashboard call will fail with 401 |
| [x] | F15 | Working unsubscribe link | `/u/{token}`, GET and one-click POST |

## Gaps outside the F-list

| | Item | Detail |
|---|---|---|
| [x] | Start a run from the dashboard | New run button and RunBar (`useAgentRun.ts`, `sections.tsx`) start a run, show progress and open the new campaign. Done in `4463dd2` |
| [ ] | Tokens used and $0 cost on the dashboard | `GET /api/usage` exists, but nothing shows it. It's the evidence for the 10-point cost-vs-value bonus |
| [~] | `LLM_MODE` on Render | `render.yaml` sets `LLM_MODE=saved`. `4463dd2` commits 24 cache files from the first live runs, so saved mode replays those, but any prompt not in the cache (a new run with different data) falls back to default copy. Set `LLM_MODE=live` for the demo |
| [ ] | Deployment | `render.yaml` and `vercel.json` exist. No sign it has been deployed and tested from the public URLs |
| [ ] | Keep-awake ping | No pinger set up for `/health` |
| [ ] | `/` route for unknown paths | `/<campaign-id>` renders a blank page. Low priority, but a redirect or 404 page would stop confusion |
| [ ] | Resend webhook | `/webhooks/resend` returns 501. This was first on the design's cut list, so leave it |
| [ ] | Hour-7 checkpoint | The full loop (run → approve → email → click → page → pay → conversion) hasn't been run on deployed URLs |

## Plan for what's left

In order. Each step should be finished before the next, except where marked as parallel.

### 1. Frontend login (F14). Blocker for deploying

- `lib/supabase.ts`: create the client from `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`.
- `lib/auth.ts`: `getAccessToken()` returns `session.access_token`.
- `LoginPage.tsx`: email and password form, then redirect to `/`, keeping `?campaign=`.
- `RequireLogin.tsx`: redirect to `/login` when there's no session.
- Create the one team user in Supabase Auth, and fill `frontend/.env`.
- **Done when:** with `ALLOW_DEV_AUTH` removed locally, the dashboard loads after logging in and returns 401 without it.

### 2. Real guardrail limits (in parallel with step 1)

- Starting a run from the dashboard is done (`4463dd2`).
- Still left: return the run's `limits` from `GET /api/campaigns/{id}` and drop `DEFAULT_LIMITS`.

### 3. Deploy and do the hour-7 checkpoint

- Render: set the secrets, set `LLM_MODE` to real calls, confirm `ALLOW_DEV_AUTH` is absent and `FRONTEND_ORIGIN` is the Vercel URL.
- Vercel: set the three `VITE_` variables.
- Stripe: add a webhook endpoint for `https://<render-url>/webhooks/stripe` with `checkout.session.completed`, and put that endpoint's signing secret in Render (it's different from the `stripe listen` one).
- Supabase Auth: add the Vercel URL to the allowed redirect URLs.
- Run the full loop from the public URLs with a team inbox and card `4242 4242 4242 4242`.
- **Done when:** the conversion appears on the deployed dashboard within about 5 seconds of paying.

### 4. Cost vs value (in parallel with step 3)

- Show tokens used per run and for the day from `GET /api/usage`, with "$0 LLM cost (free tier)" next to live revenue recovered.

### 5. Demo readiness

- Set up the keep-awake ping on `/health` every 10 minutes.
- Check Groq's remaining daily tokens, and keep the 60K reserve.
- Approval screen: link to a preview of each cohort's page (R10).
- Add a catch-all route that redirects to `/`.
- Feature freeze, then record the backup video and rehearse the demo script twice.

### Stretch, only if steps 1–5 are done

- Execute the recommendation as a second round.
