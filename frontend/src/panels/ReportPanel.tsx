// Owned by feature/agent. Keep these props: DashboardPage passes them.
export interface ReportPanelProps {
  campaignId: string | null;
}

export default function ReportPanel({ campaignId }: ReportPanelProps) {
  return (
    <section>
      <h2>Recommendation</h2>
      <p>Not implemented yet.{campaignId && ` Campaign: ${campaignId}`}</p>
    </section>
  );
}
