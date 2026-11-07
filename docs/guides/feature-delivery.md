# Guide: `feature/delivery` (act and measure)

**Goal:** a marketer logs in and approves. Real emails reach team inboxes, a click leads to a personalised page and a Stripe test checkout, and every result is attributed and shown, with live and simulated results kept separate.

Read first: [`docs/BRANCH_PLAN.md`](../BRANCH_PLAN.md) for file ownership and frozen files, and sections 5–11 of [`SYSTEM_DESIGN.md`](../../SYSTEM_DESIGN.md).

**Suggested split between the two of you:**

- **Backend 2:** steps 1 (backend), 2–5, 7 and 9
- **Front-end lead:** steps 1 (frontend), 6 (page and checkout screens) and 8 (results screen)

Rough time budget: about 7 hours, aiming to merge by hour 6–7. This branch is the larger one.

---

## Contracts with `feature/agent`

Don't change these without agreeing with the other pair.

| What | Rule |
|---|---|
| `variants.page_content` | Validates as `PageContent` (`app/contracts.py`). Render it as plain text, never as HTML |
| `variants.body_text` | Plain text, with no greeting or links. You add "Hi {first name},", the link and the unsubscribe footer |
| `campaigns.status` | Agent writes `draft` and `rejected`. You write `approved`, `sending` and `sent` |
| `agent_runs.limits.send_cap` | The maximum number of recipients per campaign |
| `simulate_responses(campaign_id)` | Call it after sending. It does nothing until the agent branch is merged |
| `compute_metrics(campaign_id)` | You own it. Keep the `CampaignMetrics` fields, because the agent's report reads them |
| `events.occurred_at` | The simulator writes times up to 60 seconds in the future. Metrics must ignore anything later than now |
| `conversions.mrr_cents` | The discounted monthly amount actually paid |
| `import_customers()` | You own it. The agent calls it at the start of every run |

**Coding pattern for every step:** keep the logic in pure functions that take plain data and return plain data, and test those. Keep Supabase, Stripe and Resend calls in thin wrappers. Tests never call real services.

Database calls use the shared client:

```python
from app.services.supabase_client import get_supabase

recipient = get_supabase().table("recipients").select("*").eq("token", token).limit(1).execute().data
```

---

## Step 0: set up the branch (45 minutes, once)

1. **One person creates the branch, the other checks it out:**
   ```powershell
   git checkout main
   git pull
   git checkout -b feature/delivery
   git push -u origin feature/delivery
   ```
   The other person runs `git fetch origin` and then `git checkout feature/delivery`.
2. **Check `backend/.env`:** it needs `ALLOW_DEV_AUTH=true` and `PUBLIC_API_URL=http://127.0.0.1:8000`, plus Supabase keys, a Stripe **test** key, a Resend key, `EMAIL_FROM`, and `RECIPIENT_ALLOWLIST` with your team's addresses.
3. **Check `frontend/.env`:** set `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`.
4. **Set up Supabase, if the agent pair hasn't yet:** run `supabase/migrations/0001_initial_schema.sql`, then `supabase/seed/offers.sql`.
5. **Create the marketer login:** in Supabase, go to Authentication > Users > Add user and create one email and password. Turn off public sign-ups.
6. **Start the email domain now:** follow the domain fallback order in section 9 of the design. DNS checks can take hours.
7. **Install the Stripe CLI (free) for local webhooks:**
   ```powershell
   stripe login
   stripe listen --forward-to 127.0.0.1:8000/webhooks/stripe
   ```
   Put the `whsec_...` value it prints into `STRIPE_WEBHOOK_SECRET`.

**Done when:** `/health/dependencies` shows Supabase `ok`, with Stripe and Resend `configured`.

---

## Step 1: login, about 60 minutes

**Backend (`app/auth.py`):**

1. Read `Authorization: Bearer <token>` from the request. Add `request: Request` to `require_user`'s parameters, keeping its name and return type.
2. **Keep the development bypass:** if `settings.allow_dev_auth` is true, return the development user as now. That keeps the agent pair working. Render never sets it.
3. **Otherwise:**
   - With no token, return `401`.
   - Call `GET {SUPABASE_URL}/auth/v1/user` with the headers `apikey: <service key>` and `Authorization: Bearer <token>`, with a 5-second timeout.
   - A `200` reply returns `AuthUser(id=..., email=...)`, and anything else returns `401`.
   - This works with every Supabase key type, so you don't need `SUPABASE_JWT_SECRET`.

**Frontend:**

1. **`lib/auth.ts`:** `getAccessToken()` returns `session.access_token` from `supabase.auth.getSession()`, or `null`.
2. **`LoginPage.tsx`:** an email and password form calls `signInWithPassword`, shows errors, and goes to `/` when it succeeds.
3. **`RequireLogin.tsx`:**
   - While the session is loading, show "Checking login…".
   - With no session, redirect to `/login`.
   - If `supabase` is `null` (keys not set), show the children with a visible warning that login isn't configured.

**Tests (`tests/test_delivery_auth.py`):** use `httpx.MockTransport`.

- No token gives `401`.
- A rejected token gives `401`.
- A valid token returns the user.
- The bypass works only when `allow_dev_auth` is on.

Delete the placeholder login test from `test_stubs_delivery.py`.

---

## Step 2: Stripe seed script and coupons (`backend/scripts/seed_stripe.py`), about 75 minutes

Run it with `.\.venv\Scripts\python.exe -m scripts.seed_stripe` from `backend/`. It must be safe to run more than once.

1. **Product and price:** a product "Pro plan" with a monthly price, for example $49. Give it the `lookup_key` `winback_pro_monthly`, so code can find it without a new setting.
2. **About 200 simulated customers:**
   - Emails like `user001@example.com`, with metadata `simulated=true` and `churned_at` set to a random date in the past 90 days.
   - About 50 distinct cancellation comments, spread across the Stripe feedback values.
   - Create each subscription with the test payment method `pm_card_visa`, then cancel it with `cancellation_details` = `{feedback, comment}`.
3. **Live customers:** one per address in `RECIPIENT_ALLOWLIST`, with metadata `simulated=false`, created the same way.
4. **Coupons:** for each offer in `offers` with `percent_off > 0` and no `stripe_coupon_id`, create a coupon (`percent_off`, `duration=repeating`, `duration_in_months`). Save its ID in `offers.stripe_coupon_id`.
5. **Running it again:** skip customers whose email already exists, and coupons that are already set.

Stripe timestamps will all be "today", so `churned_at` comes from metadata (risk R6).

**Done when:** about 200 cancelled subscriptions appear in the Stripe test dashboard, and every discounted offer has a coupon ID.

---

## Step 3: import customers (`app/stripe_import.py`), about 45 minutes

1. **`import_customers() -> int`:**
   - List subscriptions with `status=canceled`, expanding `customer`, and go through every page of results.
   - Upsert into `customers` by `stripe_customer_id`: `email`, `name`, `plan`, `mrr_cents` (the price amount), `churned_at` (from metadata, otherwise `canceled_at`), `cancel_feedback`, `cancel_comment` and `is_simulated` (from metadata).
   - Return the number of customers imported.
2. **Never overwrite `unsubscribed_at`.**
3. **Structure:** keep a pure function, `subscription_to_customer_row(subscription: dict) -> dict`.

**Tests:**

- Mapping uses `churned_at` from metadata.
- Mapping falls back to `canceled_at`.
- Mapping reads `is_simulated`.
- Mapping handles a missing comment.

Delete the import placeholder test.

---

## Step 4: approve and send (`routers/sending.py`, `app/delivery/send.py`, `services/email_client.py`, `app/delivery/email_templates.py`), about 90 minutes

1. **`POST /api/campaigns/{id}/approve`:**
   - `draft` changes to `approved`, recording `approved_by` (from `require_user`) and `approved_at`.
   - If the campaign is already `approved`, `sending` or `sent`, return its current status with no other effect.
   - `rejected` returns `409`, and an unknown campaign returns `404`.
   - Return `202`, then start the sending in `BackgroundTasks`.
2. **Create recipients:**
   - Include customers in the run's cohorts who haven't unsubscribed, up to `limits.send_cap`.
   - Within each cohort, sorted by customer ID, alternate between variants `A` and `B`.
   - Each token is `secrets.token_urlsafe(16)`, which gives 128 bits.
   - `source` is `simulated` when the customer is simulated, and `live` otherwise.
   - Insert with `on conflict do nothing`, which the `unique (campaign_id, customer_id)` constraint allows.
3. **Send:**
   - Set `sending`.
   - **Live recipients:** send only if their email is in `RECIPIENT_ALLOWLIST`, compared in lower case. Check immediately before each send, then save `resend_message_id` and `sent_at`, and record a `sent` event.
   - **Simulated recipients:** set `sent_at` only, and never send email to them.
   - Then call `simulate_responses(campaign_id)` and set `sent`.
4. **Email:**
   - The subject comes from the variant.
   - The body is "Hi {first name}," followed by the escaped `body_text` and a button linking to `{PUBLIC_API_URL}/r/{token}`.
   - The footer has an unsubscribe link to `{PUBLIC_API_URL}/u/{token}`, and the email sets a `List-Unsubscribe` header.
   - Send both HTML and plain-text versions. The sender is `EMAIL_FROM`.

**Tests:**

- Variants alternate within a cohort.
- The send cap is respected.
- Unsubscribed customers are excluded.
- An address not on the allow-list is never sent to.
- Simulated recipients are never sent to.
- Approving twice has no further effect.
- `rejected` returns `409`.
- The email body escapes HTML and includes both links.

**Done when:** approving a test campaign sends a real email to a team inbox, and only there.

---

## Step 5: click tracking and unsubscribe (`routers/tracking.py`), about 30 minutes

1. **`GET /r/{token}`:**
   - An unknown token returns `404`.
   - Otherwise, record a `clicked` event (with the recipient's `source`) and redirect with `302` to `{FRONTEND_ORIGIN}/w/{token}`.
2. **`GET /u/{token}`:** set the customer's `unsubscribed_at`, record an `unsubscribed` event, and return a short HTML page saying they're unsubscribed.

**Tests:** the redirect target, the event's source, and an unknown token (`404`).

---

## Step 6: page API, checkout and screens (`routers/pages.py`, `WinbackPage.tsx`, `ThanksPage.tsx`), about 90 minutes

**Backend:**

1. **`GET /api/pages/{token}`:**
   - Return `{page_content, offer: {label, percent_off, duration_months}, first_name}`, and nothing else about the customer.
   - Record a `page_viewed` event. An unknown token returns `404`.
2. **`POST /api/pages/{token}/checkout`:**
   - Ignore anything sent in the request body.
   - Create a Stripe Checkout Session with `mode=subscription`, `customer` set to the recipient's Stripe customer, and the price found by `lookup_key`.
   - Apply `discounts` with the offer's coupon, if it has one.
   - Set `success_url` to `{FRONTEND_ORIGIN}/thanks` and `cancel_url` to `{FRONTEND_ORIGIN}/w/{token}`.
   - Add the metadata `recipient_id`, `campaign_id` and `variant_id`.
   - Record `checkout_started`, and return `{url}`.

**Frontend:**

1. **`WinbackPage.tsx`:**
   - Load the page content and render every field as text.
   - Add the offer text in code, for example "25% off for 3 months".
   - The call-to-action button posts to checkout, then sets `window.location` to the returned URL.
   - An unknown token shows "This link is no longer valid."
2. **`ThanksPage.tsx`:** a short confirmation that the subscription is back.

**Tests:**

- The page response contains no extra customer data.
- Checkout uses the stored offer even when the request body sends another one.

---

## Step 7: Stripe webhook and attribution (`routers/webhooks.py`), about 45 minutes

1. **`POST /webhooks/stripe`:**
   - Read the raw body, and verify it with `stripe.Webhook.construct_event(payload, stripe_signature_header, STRIPE_WEBHOOK_SECRET)`. An invalid signature returns `400`.
   - Insert into `processed_webhooks` with `provider = 'stripe'` and the event ID. If it's already there, return `200` with no other effect.
   - For `checkout.session.completed`, insert into `conversions` with `recipient_id` from the metadata, `stripe_session_id`, `mrr_cents = amount_total` and `source = 'live'`.
   - Return `200`.
2. **`POST /webhooks/resend`:** optional, and first on the design's cut list. Leave it returning `501` unless you have spare time.

**Tests:**

- A bad signature returns `400`.
- A duplicate event adds nothing.
- A completed checkout creates one conversion.

**Done when:** paying with the test card `4242 4242 4242 4242` creates a conversion while `stripe listen` is running.

---

## Step 8: metrics and results screen (`app/metrics.py`, `routers/sending.py`, `ResultsPanel.tsx`), about 75 minutes

1. **`compute_metrics(campaign_id)`:**
   - Load the campaign's recipients with their variant and cohort, plus its events and conversions.
   - **Ignore anything with `occurred_at` after now.**
   - Per source and per variant, count:
     - **Recipients:** the number of rows
     - **Clicks, page views and checkouts started:** distinct recipients with each event type
     - **Conversions:** the number of conversion rows
     - **Revenue recovered:** the sum of `mrr_cents`
   - Keep the counting in a pure function, `aggregate(recipients, events, conversions, now) -> CampaignMetrics`.
2. **`GET /api/campaigns/{id}/results`:** returns the campaign status plus the metrics.
3. **`ResultsPanel.tsx`:**
   - Poll every 3 seconds.
   - Show **Live** and **Simulated** side by side, with "Simulated" clearly labelled, and a table per cohort and variant.
   - Format revenue as dollars, and never add the two sources together.

**Tests:**

- Future events are ignored.
- Live and simulated are counted separately.
- A recipient who clicks twice counts once.
- Revenue adds up correctly.

Delete the metrics placeholder test.

---

## Step 9: deploy (`render.yaml`, `vercel.json`), about 45 minutes, from hour 9

Do this only after both branches are merged into `main`.

1. **Render:** create a Blueprint from `render.yaml`, then fill in every value. Set `FRONTEND_ORIGIN` to the Vercel URL and `PUBLIC_API_URL` to the Render URL. **Never set `ALLOW_DEV_AUTH`.**
2. **Vercel:** import the repo, set the root directory to `frontend`, and set the `VITE_*` values with `VITE_API_URL` pointing to the Render URL.
3. **Stripe:** add a webhook endpoint for `https://<render-url>/webhooks/stripe` with the `checkout.session.completed` event, then put its signing secret on Render.
4. **Keep-awake:** create a free uptime ping to `https://<render-url>/health` every 10 minutes, during the event only.
5. **Check:** protected routes return `401` without login, and the whole flow works on the deployed URLs.

---

## Before you merge

- [ ] `tests/test_stubs_delivery.py` is deleted, apart from `/webhooks/resend` if you skipped it.
- [ ] `.\.venv\Scripts\python.exe -m pytest` passes, and `npm run build` passes.
- [ ] Locally, you can approve, receive the email, click, see the page, pay, and see the conversion in Results.
- [ ] No file owned by the agent branch, and no frozen file, was changed: check with `git diff --stat main`.
- [ ] Merge `main` into your branch, rerun the tests, then open a pull request into `main`.

**Until the agent branch is merged,** you need a campaign to approve. Insert a test run, cohort, `draft` campaign and two variants by hand in the Supabase SQL editor, with `page_content` matching `PageContent`. Keep that SQL in `supabase/fixtures/delivery_dev.sql`.
