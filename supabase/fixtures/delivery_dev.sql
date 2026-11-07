-- Owned by feature/delivery. A draft campaign to approve before feature/agent is merged.
-- Run in the Supabase SQL editor after the customers are imported (Step 3).
-- Safe to run again: it deletes its own rows first, so you get a fresh draft every time.
--
-- Two cohorts: "Price" (cancel_feedback = too_expensive) and "Everything else".
-- Every customer, live or simulated, joins one of them.

begin;

-- Reset this fixture's rows, children first.
delete from conversions where recipient_id in (select id from recipients where campaign_id = 'dddddddd-0000-4000-8000-000000000001');
delete from events      where recipient_id in (select id from recipients where campaign_id = 'dddddddd-0000-4000-8000-000000000001');
delete from recipients  where campaign_id = 'dddddddd-0000-4000-8000-000000000001';
delete from reports     where campaign_id = 'dddddddd-0000-4000-8000-000000000001';
delete from variants    where campaign_id = 'dddddddd-0000-4000-8000-000000000001';
delete from campaigns   where id = 'dddddddd-0000-4000-8000-000000000001';
delete from cohort_members where cohort_id in ('cccccccc-0000-4000-8000-000000000001', 'cccccccc-0000-4000-8000-000000000002');
delete from cohorts     where run_id = 'aaaaaaaa-0000-4000-8000-000000000001';
delete from agent_runs  where id = 'aaaaaaaa-0000-4000-8000-000000000001';

insert into agent_runs (id, status, current_step, limits)
values (
  'aaaaaaaa-0000-4000-8000-000000000001', 'awaiting_approval', 'approval',
  '{"max_percent_off": 40, "send_cap": 250, "max_exposure_cents": 500000}'
);

insert into cohorts (id, run_id, label, summary) values
  ('cccccccc-0000-4000-8000-000000000001', 'aaaaaaaa-0000-4000-8000-000000000001',
   'Price', 'Left because the plan cost too much for them.'),
  ('cccccccc-0000-4000-8000-000000000002', 'aaaaaaaa-0000-4000-8000-000000000001',
   'Everything else', 'Missing features, switched tools, or stopped using it.');

insert into cohort_members (cohort_id, customer_id, confidence, assigned_by)
select
  case when cancel_feedback = 'too_expensive'
       then 'cccccccc-0000-4000-8000-000000000001'::uuid
       else 'cccccccc-0000-4000-8000-000000000002'::uuid end,
  id, 1, 'fallback'
from customers;

update cohorts c
set customer_count = s.n, mrr_at_stake_cents = s.mrr
from (
  select m.cohort_id, count(*) as n, coalesce(sum(cu.mrr_cents), 0) as mrr
  from cohort_members m join customers cu on cu.id = m.customer_id
  where m.cohort_id in ('cccccccc-0000-4000-8000-000000000001', 'cccccccc-0000-4000-8000-000000000002')
  group by m.cohort_id
) s
where c.id = s.cohort_id;

insert into campaigns (id, run_id, status, max_exposure_cents)
values ('dddddddd-0000-4000-8000-000000000001', 'aaaaaaaa-0000-4000-8000-000000000001', 'draft', 500000);

insert into variants (campaign_id, cohort_id, label, offer_id, subject, body_text, page_content, reasoning)
values
  ('dddddddd-0000-4000-8000-000000000001', 'cccccccc-0000-4000-8000-000000000001', 'A',
   (select id from offers where label = '25% off for 3 months'),
   'Your Pro plan, 25% cheaper for 3 months',
   E'You told us the price was hard to justify, and that''s fair.\n\nFor the next 3 months, Pro is 25% off. Same features, smaller bill, and you can cancel any time.',
   '{"headline": "Pro, for less", "subheadline": "25% off for your first 3 months back.", "reasons": [{"title": "Everything you had", "body": "Your workflows are ready to pick up again."}, {"title": "Cancel any time", "body": "No contract, no catch."}], "objection_response": "If budget is still tight in 3 months, you can cancel with one click.", "cta_label": "Come back for less"}',
   'Fixture: price-sensitive cohort gets the bigger discount.'),
  ('dddddddd-0000-4000-8000-000000000001', 'cccccccc-0000-4000-8000-000000000001', 'B',
   (select id from offers where label = '10% off for 3 months'),
   'A smaller bill if you come back',
   E'We know the cost added up. We''ve taken 10% off Pro for your first 3 months back.\n\nEverything you set up is still here.',
   '{"headline": "Welcome back, for less", "subheadline": "10% off for 3 months.", "reasons": [{"title": "Nothing to set up", "body": "Your account is exactly as you left it."}], "objection_response": "Try it for a month. If it is not worth it, cancel in one click.", "cta_label": "Restart Pro"}',
   'Fixture: smaller discount to compare against A.'),
  ('dddddddd-0000-4000-8000-000000000001', 'cccccccc-0000-4000-8000-000000000002', 'A',
   (select id from offers where label = 'No discount: show what''s new'),
   'Here''s what''s new in Pro',
   E'A lot has changed since you left: new integrations, faster reports, and a simpler setup.\n\nTake another look and see if it fits now.',
   '{"headline": "Pro has changed", "subheadline": "New integrations, faster reports, simpler setup.", "reasons": [{"title": "New integrations", "body": "Connect the tools your team already uses."}, {"title": "Faster reports", "body": "Dashboards load in seconds."}], "objection_response": "If something is still missing, reply and tell us what.", "cta_label": "See what is new"}',
   'Fixture: no discount, lead with product changes.'),
  ('dddddddd-0000-4000-8000-000000000001', 'cccccccc-0000-4000-8000-000000000002', 'B',
   (select id from offers where label = '10% off for 3 months'),
   'Give Pro another try, 10% off',
   E'Pro has new integrations and a simpler setup since you left.\n\nCome back this month and get 10% off for 3 months.',
   '{"headline": "Another look, 10% off", "subheadline": "New features and a small discount for 3 months.", "reasons": [{"title": "Simpler setup", "body": "Get going in minutes."}], "objection_response": "Cancel any time with one click.", "cta_label": "Try Pro again"}',
   'Fixture: same story as A plus a small discount.');

commit;

-- The campaign to approve:
--   POST /api/campaigns/dddddddd-0000-4000-8000-000000000001/approve
