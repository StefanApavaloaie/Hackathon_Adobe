// Owned by frontend/Stefan. Feeds the dashboard from the API where endpoints exist,
// and keeps DEMO data everywhere else (see docs/BRANCH_PLAN.md).
//
// Connected now (feature/delivery):
//   GET  /api/campaigns/{id}/results  -> status + live/simulated results
//   POST /api/campaigns/{id}/approve  -> approve and start sending
// Still demo (feature/agent): hero figures, guardrails, cohorts and the recommendation,
// which will come from GET /api/campaigns/{id} and its report.
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, apiGet, apiPost } from "../lib/api";
import { DEMO, type DashboardData, type ResultSide } from "./demoData";

// Shape of delivery's GET /api/campaigns/{id}/results (backend/app/routers/sending.py, app/metrics.py).
interface Counts {
  recipients: number;
  clicks: number;
  page_views: number;
  checkouts_started: number;
  conversions: number;
  mrr_recovered_cents: number;
}
interface ResultsResponse {
  campaign_id: string;
  status: string;
  metrics: { live: Counts; simulated: Counts };
}

export type CampaignStatus = "draft" | "approved" | "sending" | "sent" | "rejected";

const STATUS_LABEL: Record<string, string> = {
  draft: "Awaiting approval",
  approved: "Approved",
  sending: "Sending",
  sent: "Sent",
  rejected: "Rejected",
};

const POLL_MS = 3000;

function toSide(counts: Counts): ResultSide {
  return {
    recoveredMonthly: Math.round(counts.mrr_recovered_cents / 100),
    sent: counts.recipients,
    wonBack: counts.conversions,
    clicked: counts.clicks,
    pageViewed: counts.page_views,
    startedCheckout: counts.checkouts_started,
  };
}

export interface DashboardState {
  data: DashboardData;
  /** True when the results come from the API rather than demo data. */
  resultsLive: boolean;
  campaignStatus: CampaignStatus | null;
  /** A problem loading the campaign, in words a person can act on. */
  loadError: string | null;
  busy: boolean;
  actionMessage: string | null;
  approve: () => Promise<void>;
  reject: () => Promise<void>;
}

export function useDashboardData(campaignId: string | null): DashboardState {
  const [results, setResults] = useState<ResultsResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const active = useRef(true);

  const load = useCallback(async () => {
    if (!campaignId) return;
    try {
      const response = await apiGet<ResultsResponse>(`/api/campaigns/${encodeURIComponent(campaignId)}/results`);
      if (!active.current) return;
      setResults(response);
      setLoadError(null);
    } catch (error) {
      if (!active.current) return;
      if (error instanceof ApiError && error.status === 404) setLoadError("That campaign wasn't found. Showing demo data.");
      else if (error instanceof ApiError && error.status === 501) setLoadError(null);
      else setLoadError(error instanceof Error ? error.message : "Couldn't load the campaign.");
    }
  }, [campaignId]);

  useEffect(() => {
    active.current = true;
    setResults(null);
    setLoadError(null);
    setActionMessage(null);
    if (!campaignId) return;
    void load();
    const timer = window.setInterval(() => void load(), POLL_MS);
    return () => {
      active.current = false;
      window.clearInterval(timer);
    };
  }, [campaignId, load]);

  const approve = useCallback(async () => {
    if (!campaignId || busy) return;
    setBusy(true);
    setActionMessage(null);
    try {
      await apiPost(`/api/campaigns/${encodeURIComponent(campaignId)}/approve`);
      setActionMessage("Approved. Emails are going out to the allow-listed inboxes.");
      await load();
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) setActionMessage("This campaign was rejected, so it can't be approved.");
      else setActionMessage(error instanceof Error ? error.message : "Approval failed. Please try again.");
    } finally {
      setBusy(false);
    }
  }, [busy, campaignId, load]);

  const reject = useCallback(async () => {
    if (!campaignId || busy) return;
    setBusy(true);
    setActionMessage(null);
    try {
      await apiPost(`/api/campaigns/${encodeURIComponent(campaignId)}/reject`);
      setActionMessage("Proposal rejected.");
      await load();
    } catch (error) {
      if (error instanceof ApiError && error.status === 501) setActionMessage("Rejecting isn't available yet: it arrives with the agent's update.");
      else setActionMessage(error instanceof Error ? error.message : "Couldn't reject the proposal.");
    } finally {
      setBusy(false);
    }
  }, [busy, campaignId, load]);

  const data: DashboardData = results
    ? {
        ...DEMO,
        status: STATUS_LABEL[results.status] ?? results.status,
        results: { live: toSide(results.metrics.live), simulated: toSide(results.metrics.simulated) },
      }
    : DEMO;

  return {
    data,
    resultsLive: results !== null,
    campaignStatus: results ? (results.status as CampaignStatus) : null,
    loadError,
    busy,
    actionMessage,
    approve,
    reject,
  };
}
