// Owned by frontend/Stefan. DEMO DATA: synthetic figures shown until the agent is connected.
// The section components take these shapes as props, so real API data can replace DEMO
// without changing the components. See docs/BRANCH_PLAN.md.

export interface Cohort {
  name: string;
  offer: string;
  atStakeMonthly: number;
  reasoning: string;
  variants: [string, string];
}

export interface ResultSide {
  recoveredMonthly: number;
  sent: number;
  wonBack: number;
}

export interface DashboardData {
  campaignName: string;
  status: string;
  atStakeMonthly: number;
  recipients: number;
  steps: string[];
  currentStep: number;
  guardrails: {
    maxDiscountPercent: number;
    sendCap: number;
    exposure: number;
    exposureLimit: number;
  };
  cohorts: Cohort[];
  results: { live: ResultSide; simulated: ResultSide };
  recommendation: string;
}

export const DEMO: DashboardData = {
  campaignName: "Demo campaign",
  status: "Awaiting approval",
  atStakeMonthly: 4410,
  recipients: 205,
  steps: ["Import", "Diagnose", "Propose", "Approve", "Act", "Measure", "Recommend"],
  currentStep: 3,
  guardrails: { maxDiscountPercent: 40, sendCap: 250, exposure: 3900, exposureLimit: 5000 },
  cohorts: [
    {
      name: "Price-sensitive",
      offer: "25% off for 3 months",
      atStakeMonthly: 2940,
      reasoning:
        "Their comments mention budget, not value. A time-limited discount bridges them to renewal without cutting the price for good.",
      variants: ["Keep your workspace, 25% off for 3 months", "We'd rather lower the price than lose you"],
    },
    {
      name: "Missing features",
      offer: "No discount, show what's new",
      atStakeMonthly: 1470,
      reasoning: "They left over capability, not cost. Show what changed instead of offering a discount.",
      variants: ["The features you asked for are here", "You asked, we built it"],
    },
  ],
  results: {
    live: { recoveredMonthly: 147, sent: 5, wonBack: 3 },
    simulated: { recoveredMonthly: 2312, sent: 200, wonBack: 41 },
  },
  recommendation:
    "Price-sensitive customers hold two-thirds of the revenue at stake, so keep their 25% offer. Missing features customers need no discount: lead with what has changed.",
};

export const money = (value: number) => `$${value.toLocaleString("en-US")}`;
