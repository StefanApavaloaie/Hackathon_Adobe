# Guide: Discord alerts

## What it does

The backend posts short messages to a Discord channel at the two moments that matter:

1. **"Campaign ready for approval"**, when the agent finishes a run, with the number of cohorts, the revenue at stake and the maximum discount exposure.
2. **"Recovered $36.75/month"**, when a live customer completes a Stripe checkout, with the cohort and variant that won them back.

Discord's phone app turns each message into a notification, so the team, and the judges, see the agent at work without opening the dashboard.

**It needs no front-end changes.** Everything happens on the backend, so it doesn't touch the React app or either branch's screens.

## What it helps with

| Judging criterion | How it helps |
|---|---|
| Third-party integrations (15) | Adds a fifth integration that does real work, alongside Stripe, Resend, Groq and Supabase |
| Product experience and demo (10) | A phone buzzing on stage the moment a judge's test payment lands is a memorable moment |
| Problem solving (25) | It fits how marketers actually work: they get told when a decision is needed, instead of watching a dashboard |
| Cost vs value bonus (10) | It's free, with no account or plan needed beyond a Discord server |

## When to build it

**After both `feature/agent` and `feature/delivery` are merged into `main`**, as about a 45-minute addition on `main`. Building it then interrupts nobody, and both call sites already exist.

If you build it earlier, do step 2 as a pull request to `main`, then have each pair add its one line (step 3) on its own branch.

---

## Step 1: create the Discord webhook (5 minutes)

1. In Discord, create a server for the team, or use an existing one, with a channel such as `#winback-agent`.
2. Open the channel's **Edit Channel > Integrations > Webhooks > New Webhook**, name it "Win-back Agent", and click **Copy Webhook URL**.
3. Put it in `backend/.env`:
   ```
   DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
   ```
4. Share it privately with whoever runs the backend, and add it to Render's environment settings later.

**The webhook URL is a secret.** Anyone who has it can post in your channel, so keep it in `.env` and on Render. Never commit it, and never put it in the frontend.

**For phone alerts:** install the Discord app, then set the channel's notifications to **All Messages**.

---

## Step 2: the notify function and setting (20 minutes, in a pull request to `main`)

These touch frozen files, so they go in one small pull request to `main`.

1. **`app/config.py`:** add `discord_webhook_url: str = ""` to `Settings`.
2. **`backend/.env.example`:** add a `DISCORD_WEBHOOK_URL=` line with a comment explaining that it's optional and secret.
3. **New file `app/services/notify.py`:**

   ```python
   import logging

   import httpx

   from app.config import get_settings

   logger = logging.getLogger(__name__)


   def notify(text: str) -> None:
       """Post a message to Discord. Never raises, and does nothing when unconfigured."""
       url = get_settings().discord_webhook_url
       if not url:
           return
       try:
           response = httpx.post(
               url,
               json={"content": text[:2000], "allowed_mentions": {"parse": []}},
               timeout=3,
           )
           response.raise_for_status()
       except httpx.HTTPError as exc:
           logger.warning("Discord alert failed: %s", type(exc).__name__)
   ```

**Why it's written this way:**

- **It never raises an exception**, so a Discord outage can't stop a run or lose a payment.
- **It has a 3-second timeout**, so a slow Discord can't hold anything up for long.
- **`allowed_mentions: {"parse": []}`** stops text such as "@everyone", which could come from an LLM-written cohort label, from pinging the whole server.
- **Messages are cut to 2,000 characters**, which is Discord's limit.
- **The log shows the error type only**, never the URL, because the URL is a secret.

**Tests (`tests/test_notify.py`):** use `monkeypatch` to replace `httpx.post`.

- No webhook URL means `httpx.post` is never called.
- A configured URL sends the text, with `allowed_mentions` empty.
- Text longer than 2,000 characters is cut to 2,000.
- An `httpx.HTTPError` doesn't raise.

**Done when:** the tests pass and the pull request is merged into `main`.

---

## Step 3: send the two alerts (15 minutes)

Each line goes in a file its branch owns.

### "Campaign ready for approval" (`feature/agent`, in `app/agent/orchestrator.py`)

Right after the run's status is set to `awaiting_approval`:

```python
notify(
    f"🧠 Campaign ready for approval: {cohort_count} cohorts, "
    f"${mrr_at_stake / 100:,.2f}/month at stake, "
    f"max discount exposure ${max_exposure / 100:,.2f}."
)
```

The orchestrator already runs in the background, so calling `notify` directly is fine.

### "Recovered revenue" (`feature/delivery`, in `routers/webhooks.py`)

Right after a **live** conversion is inserted, and never for a duplicate event:

```python
background_tasks.add_task(
    notify,
    f"💰 Recovered ${mrr_cents / 100:,.2f}/month from the "
    f"\"{cohort_label}\" cohort (variant {variant_label}).",
)
```

**Use `BackgroundTasks` here** so Stripe gets its `200` response immediately, rather than waiting for Discord. Load `cohort_label` and `variant_label` through the recipient's variant.

**Don't alert for simulated conversions.** The simulator can create dozens at once, which would flood the channel and blur the difference between live and simulated.

---

## Step 4 (optional): show it in the Status panel (10 minutes)

In `routers/health.py`, which is frozen, so this goes through `main`, add `"discord": "configured" if settings.discord_webhook_url else "not_configured"` to the dependencies.

The Status panel lists whatever the backend returns, so it appears there with no front-end change. Don't call Discord from the health check, so the keep-awake ping never posts anything.

---

## Step 5: check it end to end (10 minutes)

1. Start a run. When it reaches the approval screen, the "ready for approval" message should appear in the channel.
2. Approve the campaign, open the email in a team inbox, and pay with `4242 4242 4242 4242`. The "recovered" message should appear within a few seconds.
3. Remove `DISCORD_WEBHOOK_URL` and repeat. Everything should still work, with no messages.
4. Before the demo, add `DISCORD_WEBHOOK_URL` to Render, and send a test message to confirm the phone gets notified.

## Demo tips

- Keep your phone visible or on the projector, with sound on, when the judge pays.
- Mute any other Discord servers during the demo, so only this channel's alerts come through.
- If Discord fails on stage, nothing else breaks, so carry on with the dashboard.
