-- Schema from SYSTEM_DESIGN.md, section 6.
-- Run once in the Supabase SQL editor, or with the Supabase CLI.

create table customers (
  id uuid primary key default gen_random_uuid(),
  stripe_customer_id text unique not null,
  email text not null,
  name text,
  plan text,
  mrr_cents int not null default 0,
  churned_at timestamptz,          -- from seeded metadata; see risk R6
  cancel_feedback text,
  cancel_comment text,
  is_simulated boolean not null default true,
  unsubscribed_at timestamptz
);

create table offers (
  id uuid primary key default gen_random_uuid(),
  label text not null,
  percent_off int not null check (percent_off between 0 and 50),
  duration_months int not null,
  stripe_coupon_id text,
  active boolean not null default true
);

create table agent_runs (
  id uuid primary key default gen_random_uuid(),
  status text not null,            -- running, awaiting_approval, failed, complete
  current_step text,
  limits jsonb not null,           -- max percent, send cap, max exposure
  error text,
  started_at timestamptz not null default now(),
  finished_at timestamptz
);

create table cohorts (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references agent_runs(id),
  label text not null,
  summary text,
  customer_count int not null default 0,
  mrr_at_stake_cents int not null default 0
);

create table cohort_members (
  cohort_id uuid references cohorts(id),
  customer_id uuid references customers(id),
  confidence numeric,
  assigned_by text not null,       -- llm or fallback
  primary key (cohort_id, customer_id)
);

create table campaigns (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null unique references agent_runs(id),
  status text not null,            -- draft, approved, rejected, sending, sent
  max_exposure_cents int,
  approved_by uuid,
  approved_at timestamptz
);

create table variants (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references campaigns(id),
  cohort_id uuid not null references cohorts(id),
  label text not null,             -- A or B
  offer_id uuid not null references offers(id),
  subject text not null,
  body_text text not null,
  page_content jsonb not null,
  reasoning text not null,
  is_fallback boolean not null default false
);

create table recipients (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references campaigns(id),
  customer_id uuid not null references customers(id),
  variant_id uuid not null references variants(id),
  token text unique not null,      -- at least 128 random bits
  source text not null,            -- live or simulated
  resend_message_id text,
  sent_at timestamptz,
  unique (campaign_id, customer_id)
);

create table events (
  id bigint generated always as identity primary key,
  recipient_id uuid not null references recipients(id),
  type text not null,              -- sent, delivered, clicked, page_viewed, checkout_started, unsubscribed
  source text not null,            -- live or simulated
  occurred_at timestamptz not null default now()
);

create table conversions (
  id uuid primary key default gen_random_uuid(),
  recipient_id uuid not null unique references recipients(id),
  stripe_session_id text unique,   -- null for simulated
  mrr_cents int not null,
  source text not null,
  occurred_at timestamptz not null default now()
);

create table processed_webhooks (
  provider text not null,
  event_id text not null,
  received_at timestamptz not null default now(),
  primary key (provider, event_id)
);

create table reports (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null unique references campaigns(id),
  metrics jsonb not null,
  recommendation text not null,
  created_at timestamptz not null default now()
);

create table llm_calls (
  id bigint generated always as identity primary key,
  run_id uuid references agent_runs(id),
  step text not null,
  model text not null,
  input_tokens int,
  output_tokens int,
  latency_ms int,
  ok boolean not null,
  created_at timestamptz not null default now()
);

-- Only the backend reads and writes data, using the service key. No public policies.
alter table customers enable row level security;
alter table offers enable row level security;
alter table agent_runs enable row level security;
alter table cohorts enable row level security;
alter table cohort_members enable row level security;
alter table campaigns enable row level security;
alter table variants enable row level security;
alter table recipients enable row level security;
alter table events enable row level security;
alter table conversions enable row level security;
alter table processed_webhooks enable row level security;
alter table reports enable row level security;
alter table llm_calls enable row level security;
