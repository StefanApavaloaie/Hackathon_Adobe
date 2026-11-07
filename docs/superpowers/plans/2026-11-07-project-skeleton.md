# Project Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a minimal, working foundation for the Win-back Agent, with no product logic.

**Architecture:** Independently runnable React (Vite) and FastAPI apps. The backend owns all secrets and every call to third parties. Section 7 endpoints exist as `501` stubs so the API contract and file ownership are fixed from the start.

**Tech Stack:** React, Vite, TypeScript, Python 3.12, FastAPI, Pydantic, httpx, Supabase, Groq, Stripe, Resend.

**Spec:** `SYSTEM_DESIGN.md`

## Global Constraints

- Total cost is $0. Do not add paid services.
- The LLM is Groq only, using `GROQ_API_KEY`, `GROQ_MODEL` and `LLM_MODE`.
- No product logic: no agent steps, simulator, seed script, login checks or dashboard screens.
- Never commit credentials. Secrets stay on the backend.
- The backend refuses to start unless a provided Stripe key begins `sk_test_`.
- CORS allows only the configured frontend origin.
- Every table has row-level security enabled, with no public policies.

## Review Focus

- A Stripe live key is provided: startup fails with a clear error.
- An unhandled backend error reaches the browser: the response is JSON and still has CORS headers.
- A service has no keys: the app still starts, and health reports `not_configured`.
- The backend is down or the API URL is missing: the frontend shows an error instead of a blank page.
- A request comes from another origin: it receives no CORS permission.

---

### Task 1: Backend foundation

**Files:** `backend/app/{main,config,errors}.py`, `backend/app/routers/*`, `backend/app/services/*`, `backend/tests/*`, `backend/requirements*.txt`, `backend/.env.example`, `backend/.python-version`

- [ ] Write failing tests for health, dependency status, settings validation, CORS, error handling and all section 7 stubs
- [ ] Run them and confirm they fail
- [ ] Implement settings, app setup, health, service clients and route stubs
- [ ] Run them and confirm they pass

### Task 2: Frontend foundation

**Files:** `frontend/` (Vite config, `src/lib/{api,supabase}.ts`, `src/pages/{Home,WinbackPage}.tsx`, `vercel.json`, `.env.example`)

- [ ] Create the app, routes and clients
- [ ] Confirm `npm run build` passes

### Task 3: Database and deployment configuration

**Files:** `supabase/migrations/0001_initial_schema.sql`, `render.yaml`

- [ ] Copy the section 6 schema exactly and enable row-level security on all tables
- [ ] Add the Render configuration

### Task 4: Documentation and verification

**Files:** `README.md`, `.gitignore`

- [ ] Write the setup guide and code ownership map
- [ ] Verify installs, FastAPI start, health, React start, frontend-to-backend communication and environment handling
- [ ] Report anything unverified, including real Supabase and Groq connections
