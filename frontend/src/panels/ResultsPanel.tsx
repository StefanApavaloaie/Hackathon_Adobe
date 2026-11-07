// Owned by feature/delivery. Keep these props: DashboardPage passes them.
// Show live and simulated results separately, and label simulated ones clearly.
export interface ResultsPanelProps {
  campaignId: string | null;
}

export default function ResultsPanel({ campaignId }: ResultsPanelProps) {
  return (
    <section>
      <h2>Results</h2>
      <p>Not implemented yet.{campaignId && ` Campaign: ${campaignId}`}</p>
    </section>
  );
}
