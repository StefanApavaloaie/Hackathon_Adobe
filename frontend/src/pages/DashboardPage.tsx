// Shared by both branches. Frozen after step 0: change it only through a pull request to main.
// The dashboard shows real data where the API provides it and labelled DEMO data elsewhere.
// Open it with ?campaign=<id> to connect a campaign.
// See docs/BRANCH_PLAN.md, "Dashboard display components".
import "../styles/dashboard.css";

import { useSearchParams } from "react-router-dom";

import { type DataSource, Guardrails, Hero, Navs, NextStep, Reasons, Results } from "../dashboard/sections";
import { useDashboardData } from "../dashboard/useDashboardData";
import { useReveal } from "../dashboard/useReveal";
import StatusPanel from "../panels/StatusPanel";

export default function DashboardPage() {
  useReveal();
  // The campaign lives in the URL (?campaign=<id>), so a refresh before the demo keeps it.
  const [params] = useSearchParams();
  const campaignId = params.get("campaign");
  const state = useDashboardData(campaignId);
  const { data } = state;
  const connected = state.campaignLive || state.resultsLive;
  const source: DataSource = state.campaignLive && state.resultsLive ? "live" : connected ? "partly" : "demo";

  return (
    <div className="dashboard">
      <Navs campaignName={data.campaignName} status={data.status} source={source} />
      <main>
        <Hero
          data={data}
          connected={connected}
          campaignStatus={state.campaignStatus}
          busy={state.busy}
          message={state.actionMessage ?? state.loadError}
          onApprove={state.approve}
          onReject={state.reject}
        />
        <Guardrails data={data} />
        <Reasons cohorts={data.cohorts} />
        <Results results={data.results} live={state.resultsLive} />
        <NextStep
          recommendation={data.recommendation}
          connected={state.campaignLive}
          busy={state.busy}
          onGenerate={state.generateReport}
        />
      </main>
      <footer className="footer">
        <div className="footer__inner">
          <p className="footer__note">
            {source === "live"
              ? "Everything on this page comes from the campaign, except the guardrail limits, which use the documented defaults."
              : source === "partly"
                ? "Parts of this page are live; the rest is demo data until the agent is connected."
                : "All figures on this page are demo data until a campaign is connected."}{" "}
            Simulated results come from seeded customers with hidden response rates; they are labelled wherever shown and
            never added to live revenue. The agent's recommendation is a suggestion and never runs on its own.
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
