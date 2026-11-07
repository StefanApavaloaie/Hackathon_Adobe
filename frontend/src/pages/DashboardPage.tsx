// Shared by both branches. Frozen after step 0: change it only through a pull request to main.
// The dashboard shows the reference layout with DEMO data until the agent is connected.
// To connect real data, pass API results to these section components in place of DEMO
// (see docs/BRANCH_PLAN.md, "Dashboard display components").
import "../styles/dashboard.css";

import { DEMO } from "../dashboard/demoData";
import { Guardrails, Hero, Navs, NextStep, Reasons, Results } from "../dashboard/sections";
import { useReveal } from "../dashboard/useReveal";
import StatusPanel from "../panels/StatusPanel";

export default function DashboardPage() {
  useReveal();
  const data = DEMO;

  return (
    <div className="dashboard">
      <Navs campaignName={data.campaignName} status={data.status} />
      <main>
        <Hero data={data} />
        <Guardrails data={data} />
        <Reasons cohorts={data.cohorts} />
        <Results results={data.results} />
        <NextStep recommendation={data.recommendation} />
      </main>
      <footer className="footer">
        <div className="footer__inner">
          <p className="footer__note">
            All figures on this page are demo data until the agent is connected. Simulated results come from seeded
            customers with hidden response rates; they are labelled wherever shown and never added to live revenue. The
            agent's recommendation is a suggestion and never runs on its own.
          </p>
          <details className="sysstatus">
            <summary>System status</summary>
            <StatusPanel />
          </details>
        </div>
      </footer>
    </div>
  );
}
