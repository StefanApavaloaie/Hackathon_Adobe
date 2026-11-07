# Win-back Agent

An AI agent that works out why subscribers cancelled, proposes a tailored win-back campaign for a marketer to approve, and measures the revenue it recovers.

This is the project skeleton, so **no product features exist yet**. [`SYSTEM_DESIGN.md`](SYSTEM_DESIGN.md) is the source of truth.

## Requirements

- Python 3.12
- Node.js 22

## Run the backend

From `backend/`, in Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

On macOS or Linux, use `.venv/bin/python` and `cp .env.example .env`.

The backend runs at http://localhost:8000, with API docs at http://localhost:8000/docs. It starts without any keys, and missing services show as `not_configured`.

Run the tests with `.\.venv\Scripts\python.exe -m pytest`.

## Run the frontend

From `frontend/`, in a second terminal:

```powershell
npm install
Copy-Item .env.example .env
npm run dev
```

Open http://localhost:5173. The page shows whether the frontend can reach the backend, and the status of each service.

## Configure services

Add keys to `backend/.env` and `frontend/.env`. Each `.env.example` explains its values. Never commit a `.env` file.

| Service | What to do |
|---|---|
| Supabase | Create a project and run `supabase/migrations/0001_initial_schema.sql` in the SQL editor |
| Groq | Create a key, then check your account's actual free limits |
| Stripe | Use a test-mode key. The backend refuses to start with any other type |
| Resend | Create a key and verify a domain (see section 9 of the design) |

**Groq tokens are shared across the team.** Keep `LLM_MODE=saved` unless you are testing prompts.

## Where code goes

Routes in section 7 of the design already exist and return `501`. Replace each stub as you build it.

| Owner | Work | Location |
|---|---|---|
| Front end and pitch | Login, dashboard, approval, results | `frontend/src/pages/`, `frontend/src/lib/` |
| Backend 1 | Agent steps, guardrails, simulator, report | New `backend/app/agent/`; `routers/runs.py`, `routers/campaigns.py`, `routers/usage.py`; `services/llm_client.py` |
| Backend 2 | Stripe, email, tracking, auth, deployment | `routers/tracking.py`, `routers/webhooks.py`, `routers/pages.py`; `services/stripe_client.py`, `services/email_client.py` |
| Innovation | Page generation and template | `frontend/src/pages/WinbackPage.tsx`; new `backend/app/agent/pages.py` |

## Rules to keep

These come from the design, and the skeleton can't enforce all of them yet:

- Protected routes need login checks before anything real is deployed.
- The LLM never decides prices, recipients or metrics. Code owns those.
- Check `RECIPIENT_ALLOWLIST` immediately before every send.
- Completions must honour `LLM_MODE`.
- Keep simulated results labelled, and never add them to live figures.

## Deploy

- **Frontend:** import the repo into Vercel and set the root directory to `frontend`. Add the `VITE_*` variables.
- **Backend:** create a Render Blueprint from `render.yaml`, then fill in the requested values. Set `FRONTEND_ORIGIN` to the Vercel URL.
- Both deploy from `main`.
