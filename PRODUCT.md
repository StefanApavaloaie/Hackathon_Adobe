# Product

<!-- impeccable:product-schema 1 -->

> Users, purpose and context are inferred from `SYSTEM_DESIGN.md` and were not confirmed by the user. Items marked "user decision" were confirmed.

## Platform

web

## Users

- **Marketer (primary, inferred):** one person at a small SaaS company who owns retention. They start an agent run, review the proposed campaign, approve it with one click, and watch the results.
- **Lapsed subscriber (secondary, inferred):** a customer who cancelled and opens a personalised win-back page from an email.
- **Hackathon judges (evaluating audience):** watch a live demo on a projector, often from a Windows laptop.

## Product Purpose

The Win-back Agent (working name) reads why subscribers cancelled, groups them into churn-reason cohorts, and proposes a campaign tailored to each. After one human approval it sends the emails, serves each cohort a personalised page, and traces recovered revenue through Stripe. It then writes a recommendation it does not execute.

## Positioning

Not a chatbot giving marketing advice: an agent that diagnoses churn, decides within guardrails, acts after one approval, and measures attributed revenue.

## Capabilities and Constraints

- Agent loop: import, diagnose, propose, approve, act, measure, recommend.
- Guardrail defaults from the team's guides: 40% maximum discount, 250 send cap, $5,000 maximum discount exposure.
- Panels and customer pages are owned by two feature branches (`docs/BRANCH_PLAN.md`). Backend must not be changed by frontend work.
- One human approval per campaign; the agent does not learn automatically.

## Brand Commitments

- **Visual reference (user decision):** the pictures in `frontend/ref_pictures/` set the look and colours: a wine/burgundy nav, warm off-white grounds, deep crimson section bands, amber/gold primary actions, near-black type, very large bold headlines and figures. Use them as a design reference only.
- **Typeface (user decision):** Manrope.
- **Content (user decision):** the dashboard shows the reference layout with labelled demo data, using the team's earlier demo figures, until real data is connected.
- Rejected directions: a forest/sand card dashboard, a ruled "seed packet" dashboard, and an Apple-style forest/sand dashboard.

## Evidence on Hand

- Demo figures (synthetic, must be labelled): 2 cohorts; $4,410/mo at stake (Price-sensitive $2,940, 25% off for 3 months; Missing features $1,470, no discount); $3,900 maximum exposure; live 3 of 5 won back, $147/mo; simulated 41 of 200 won back, $2,312/mo.
- No logo, photography, testimonials, customers or real metrics exist. Do not invent them.

## Product Principles

1. Show the agent's reasoning, so a person can approve with confidence.
2. Code owns the facts: prices, discounts, recipients and metrics never come from model output.
3. Live and simulated results stay separate and labelled, and are never added together.
4. Honest claims: "proposes and measures", never "fully autonomous" or "learns".

## Accessibility & Inclusion

WCAG AA contrast; keyboard-usable controls with visible focus; motion respects reduced-motion settings; readable on a projector.
