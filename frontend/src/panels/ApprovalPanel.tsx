// Owned by feature/agent. Keep these props: DashboardPage passes them.
// The approve button calls POST /api/campaigns/{id}/approve, which feature/delivery builds.
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, apiGet, apiPost } from "../lib/api";

export interface ApprovalPanelProps {
  campaignId: string | null;
}

interface Offer {
  id: string;
  label: string;
  percent_off: number;
  duration_months: number;
}

interface PageContent {
  headline: string;
  subheadline: string;
  reasons: { title: string; body: string }[];
  objection_response: string;
  cta_label: string;
}

interface Variant {
  id: string;
  label: string;
  subject: string;
  body_text: string;
  page_content: PageContent;
  reasoning: string;
  is_fallback: boolean;
  offer: Offer | null;
}

interface Cohort {
  id: string;
  label: string;
  summary: string | null;
  customer_count: number;
  mrr_at_stake_cents: number;
  variants: Variant[];
}

interface CampaignView {
  campaign: { id: string; status: string; max_exposure_cents: number | null; run_id: string };
  cohorts: Cohort[];
  report: unknown;
}

const formatCents = (cents: number) =>
  `$${(cents / 100).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

// Offer labels usually state the discount already; add the terms only when they don't.
const offerText = (o: Offer | null) => {
  if (!o) return "Unknown offer";
  const label = o.label.toLowerCase();
  if (o.percent_off === 0) return label.includes("discount") ? o.label : `${o.label} (no discount)`;
  if (label.includes(`${o.percent_off}%`)) return o.label;
  return `${o.label} (${o.percent_off}% off for ${o.duration_months} month${o.duration_months === 1 ? "" : "s"})`;
};

function PagePreview({ page }: { page: PageContent }) {
  return (
    <details>
      <summary>Page preview</summary>
      <div style={{ borderLeft: "3px solid #ccc", paddingLeft: "0.75rem" }}>
        <p>
          <strong>{page.headline}</strong>
          <br />
          {page.subheadline}
        </p>
        <ul>
          {page.reasons.map((r) => (
            <li key={r.title}>
              <strong>{r.title}:</strong> {r.body}
            </li>
          ))}
        </ul>
        <p>{page.objection_response}</p>
        <p>[{page.cta_label}]</p>
      </div>
    </details>
  );
}

export default function ApprovalPanel({ campaignId }: ApprovalPanelProps) {
  const [data, setData] = useState<CampaignView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Ignore responses for a campaign that is no longer selected, so a slow
  // request for the previous campaign can't overwrite the current one.
  const current = useRef(campaignId);
  current.current = campaignId;

  const load = useCallback(async () => {
    if (!campaignId) return;
    try {
      const view = await apiGet<CampaignView>(`/api/campaigns/${campaignId}`);
      if (current.current !== campaignId) return;
      setData(view);
      setError(null);
    } catch (err) {
      if (current.current !== campaignId) return;
      setError((err as Error).message);
    }
  }, [campaignId]);

  useEffect(() => {
    setData(null);
    setError(null);
    setActionError(null);
    load();
  }, [load]);

  const act = async (action: "approve" | "reject") => {
    if (!campaignId) return;
    if (action === "reject" && !confirm("Reject this campaign? It can't be approved afterwards.")) return;
    setBusy(true);
    setActionError(null);
    try {
      await apiPost(`/api/campaigns/${campaignId}/${action}`);
      await load();
    } catch (err) {
      const message = (err as Error).message;
      setActionError(
        err instanceof ApiError && err.status === 501
          ? `${message} (approve is built on the delivery branch)`
          : message,
      );
    } finally {
      setBusy(false);
    }
  };

  if (!campaignId) {
    return (
      <section>
        <h2>Approval</h2>
        <p>Start a run to get a proposed campaign.</p>
      </section>
    );
  }

  return (
    <section>
      <h2>Approval</h2>
      {error && <p role="alert">Could not load the campaign: {error}</p>}
      {!data && !error && <p>Loading campaign…</p>}

      {data && (
        <>
          <p>
            Campaign status: <strong>{data.campaign.status}</strong>
          </p>
          <p style={{ fontSize: "1.25rem" }}>
            Maximum discount exposure:{" "}
            <strong>
              {data.campaign.max_exposure_cents == null ? "not computed" : formatCents(data.campaign.max_exposure_cents)}
            </strong>
          </p>

          {data.campaign.status === "draft" && (
            <p>
              <button onClick={() => act("approve")} disabled={busy}>
                Approve and send
              </button>{" "}
              <button onClick={() => act("reject")} disabled={busy}>
                Reject
              </button>
            </p>
          )}
          {actionError && <p role="alert">Error: {actionError}</p>}

          {data.cohorts.map((cohort) => (
            <article key={cohort.id}>
              <h3>
                {cohort.label} · {cohort.customer_count} customers · {formatCents(cohort.mrr_at_stake_cents)} a month
                at stake
              </h3>
              {cohort.summary && <p>{cohort.summary}</p>}
              {cohort.variants.length === 0 && <p>No variants for this cohort.</p>}
              {[...cohort.variants]
                .sort((a, b) => a.label.localeCompare(b.label))
                .map((v) => (
                  <div key={v.id} style={{ marginBottom: "1rem" }}>
                    <h4>
                      Variant {v.label}
                      {v.is_fallback && (
                        <span title="The agent's output failed checks, so template copy was used">
                          {" "}
                          [fallback]
                        </span>
                      )}
                    </h4>
                    <p>
                      <strong>Offer:</strong> {offerText(v.offer)}
                    </p>
                    <p>
                      <strong>Subject:</strong> {v.subject}
                    </p>
                    <p style={{ whiteSpace: "pre-wrap" }}>
                      <strong>Body:</strong> {v.body_text}
                    </p>
                    <p>
                      <strong>Why:</strong> {v.reasoning}
                    </p>
                    <PagePreview page={v.page_content} />
                  </div>
                ))}
            </article>
          ))}
        </>
      )}
    </section>
  );
}
