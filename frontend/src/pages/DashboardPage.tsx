// Shared by both branches. Frozen after step 0: change it only through a pull request to main.
// Each panel belongs to one branch. Panels must keep the props passed here.
import { useSearchParams } from "react-router-dom";

import ApprovalPanel from "../panels/ApprovalPanel";
import ReportPanel from "../panels/ReportPanel";
import ResultsPanel from "../panels/ResultsPanel";
import RunPanel from "../panels/RunPanel";
import StatusPanel from "../panels/StatusPanel";

export default function DashboardPage() {
  // The campaign lives in the URL (?campaign=<id>), so a refresh before the demo keeps it.
  const [params, setParams] = useSearchParams();
  const campaignId = params.get("campaign");
  const showCampaign = (id: string) => setParams({ campaign: id });

  return (
    <main>
      <h1>Win-back Agent</h1>
      <StatusPanel />
      <RunPanel onCampaignReady={showCampaign} />
      <ApprovalPanel campaignId={campaignId} />
      <ResultsPanel campaignId={campaignId} />
      <ReportPanel campaignId={campaignId} />
    </main>
  );
}
