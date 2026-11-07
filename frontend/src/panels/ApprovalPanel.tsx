// Owned by feature/agent. Keep these props: DashboardPage passes them.
// The approve button calls POST /api/campaigns/{id}/approve, which feature/delivery builds.
export interface ApprovalPanelProps {
  campaignId: string | null;
}

export default function ApprovalPanel({ campaignId }: ApprovalPanelProps) {
  return (
    <section>
      <h2>Approval</h2>
      <p>Not implemented yet.{campaignId && ` Campaign: ${campaignId}`}</p>
    </section>
  );
}
