-- The offer catalog. The agent may only choose offers from this table.
-- Run after 0001_initial_schema.sql. Safe to run more than once.
-- feature/delivery fills stripe_coupon_id when it creates the Stripe coupons.

insert into offers (label, percent_off, duration_months)
select v.label, v.percent_off, v.duration_months
from (values
  ('No discount: show what''s new', 0, 0),
  ('10% off for 3 months', 10, 3),
  ('25% off for 3 months', 25, 3),
  ('40% off for 2 months', 40, 2)
) as v(label, percent_off, duration_months)
where not exists (select 1 from offers o where o.label = v.label);
