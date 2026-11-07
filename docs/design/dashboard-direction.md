---
version: 1
slug: "frontend-src-pages-dashboardpage-tsx"
primary_target: "frontend/src/pages/DashboardPage.tsx"
related_targets: ["frontend/src/main.tsx","frontend/index.html"]
---

# Surface brief: dashboard

Scope: the dashboard at `/` rebuilt as the reference layout from `frontend/ref_pictures/`, with labelled demo data, plus the shared styles customer pages inherit. Visitor mode: Operate, presented with product-page staging. Panels are no longer mounted on the dashboard; the feature branches will feed real data into these display components. Backend untouched.

Audience and job: one retention marketer reviews why customers left, checks the guardrails, approves, then reads live and simulated results and the next step. Judges watch on a projector.

Constraints: user-pinned reference look and colours; Manrope; demo figures from PRODUCT.md only, labelled as demo; no kickers or tracked capitals (both skills ban them), so status moves into the campaign bar; navigation points at sections that exist; scroll fade-ins requested by the user, kept visible by default and off under reduced motion.

## Direction contract

THESIS: The dashboard reads as a confident product page for one decision: a giant revenue headline, then the evidence in bold bands, with approval as the one bright action. It refuses the dense admin grid and the three rejected directions.

OWN-WORLD: Warm off-white ground, a wine nav and deep crimson bands, near-black Manrope set very large and tight, white and crimson cohort tiles alternating, amber reserved for the primary action and for figures on crimson.

STORY: The marketer sees what is at stake and why customers left, trusts the limits, approves, and sees live and simulated results kept apart.

FIRST VIEWPORT: Sticky wine global nav (wordmark left, section links right) over a sticky light campaign bar (campaign name, demo and status labels, Approve). Centred: "Win back $4,410 a month." at display scale with the figure in wine, one line of counts, the amber Approve and send pill beside a reject link, and the step track below.

FORM: user-pinned reference pictures beat the roll (candidate 5); signature move: the guardrail exposure bar fills to $3,900 of $5,000 as its band scrolls into view. seed:176ea217ac27045e

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
