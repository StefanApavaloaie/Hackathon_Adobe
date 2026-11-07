// Owned by feature/agent. Keep these props: DashboardPage passes them.
export interface RunPanelProps {
  /** Call this when a run has produced a campaign, so the other panels show it. */
  onCampaignReady: (campaignId: string) => void;
}

export default function RunPanel(_props: RunPanelProps) {
  return (
    <section>
      <h2>Agent run</h2>
      <p>Not implemented yet.</p>
    </section>
  );
}
