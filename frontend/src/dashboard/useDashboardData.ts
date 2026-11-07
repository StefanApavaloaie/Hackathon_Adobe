// Owned by frontend/Stefan. Feeds the dashboard from the API, and keeps labelled DEMO data
// for anything an endpoint can't provide (see docs/BRANCH_PLAN.md).
//
//   GET  /api/campaigns/{id}          -> cohorts, offers, variants, exposure, report  (feature/agent)
//   GET  /api/campaigns/{id}/results  -> status + live/simulated results             (feature/delivery)
//   POST /api/campaigns/{id}/approve  -> approve and start sending                   (feature/delivery)
//   POST /api/campaigns/{id}/reject   -> reject a draft                              (feature/agent)
//   POST /api/campaigns/{id}/report   -> generate the recommendation                 (feature/agent)
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, apiGet, apiPost } from "../lib/api";
import { type Cohort, DEMO, type DashboardData, type ResultSide } from "./demoData";

// --- API shapes --------------------------------------------------------------

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

interface ApiOffer {
  label: string | null;
  percent_off: number;
  duration_months: number;
}
interface ApiVariant {
  label: string;
  subject: string;
  offer: ApiOffer | null;
}
interface ApiCohort {
  label: string;
  summary: string | null;
  customer_count: number;
  mrr_at_stake_cents: number;
  variants: ApiVariant[];
}
interface CampaignResponse {
  campaign: { id: string; status: string; max_exposure_cents: number | null; run_id: string };
  cohorts: ApiCohort[];
  report: { recommendation?: string } | null;
}

export type CampaignStatus = "draft" | "approved" | "sending" | "sent" | "rejected";

const STATUS_LABEL: Record<string, string> = {
  draft: "Awaiting approval",
  approved: "Approved",
  sending: "Sending",
  sent: "Sent",
  rejected: "Rejected",
};

// Steps: Import, Diagnose, Propose, Approve, Act, Measure, Recommend.
const STEP_FOR_STATUS: Record<string, number> = { draft: 3, rejected: 3, approved: 4, sending: 4, sent: 5 };

// The run's limits aren't returned by the API yet, so these are the documented defaults
// (docs/guides/feature-agent.md, step 2).
const DEFAULT_LIMITS = { maxDiscountPercent: 40, sendCap: 250, exposureLimit: 5000 };

const POLL_MS = 3000;

// --- mapping -----------------------------------------------------------------

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

function offerText(variants: ApiVariant[]): string {
  const labels = [...new Set(variants.map((v) => v.offer?.label).filter((l): l is string => Boolean(l)))];
  if (labels.length === 0) return "No offer chosen";
  return labels.length === 1 ? labels[0] : `Testing ${labels.join(" vs ")}`;
}

function toCohort(cohort: ApiCohort): Cohort {
  const variants = [...cohort.variants].sort((a, b) => a.label.localeCompare(b.label));
  return {
    name: cohort.label,
    offer: offerText(variants),
    atStakeMonthly: Math.round(cohort.mrr_at_stake_cents / 100),
    reasoning: cohort.summary ?? "",
    variants: variants.map((v) => v.subject),
  };
}

function fromCampaign(view: CampaignResponse) {
  const cohorts = view.cohorts.map(toCohort);
  return {
    status: view.campaign.status,
    atStakeMonthly: cohorts.reduce((sum, c) => sum + c.atStakeMonthly, 0),
    recipients: view.cohorts.reduce((sum, c) => sum + c.customer_count, 0),
    cohorts,
    guardrails: {
      maxDiscountPercent: DEFAULT_LIMITS.maxDiscountPercent,
      sendCap: DEFAULT_LIMITS.sendCap,
      exposure: Math.round((view.campaign.max_exposure_cents ?? 0) / 100),
      exposureLimit: DEFAULT_LIMITS.exposureLimit,
    },
    recommendation: view.report?.recommendation ?? null,
  };
}

// --- hook ----------------------------------------------------------------------

export interface DashboardState {
  data: DashboardData;
  /** True when the campaign view (cohorts, offers, figures) comes from the API. */
  campaignLive: boolean;
  /** True when the results come from the API. */
  resultsLive: boolean;
  campaignStatus: CampaignStatus | null;
  loadError: string | null;
  busy: boolean;
  actionMessage: string | null;
  approve: () => Promise<void>;
  reject: () => Promise<void>;
  generateReport: () => Promise<void>;
}

function errorText(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

export function useDashboardData(campaignId: string | null): DashboardState {
  const [view, setView] = useState<CampaignResponse | null>(null);
  const [results, setResults] = useState<ResultsResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const active = useRef(true);

  const load = useCallback(async () => {
    if (!campaignId) return;
    const id = encodeURIComponent(campaignId);
    const [viewResult, resultsResult] = await Promise.allSettled([
      apiGet<CampaignResponse>(`/api/campaigns/${id}`),
      apiGet<ResultsResponse>(`/api/campaigns/${id}/results`),
    ]);
    if (!active.current) return;

    if (viewResult.status === "fulfilled") setView(viewResult.value);
    if (resultsResult.status === "fulfilled") setResults(resultsResult.value);

    const failure = [viewResult, resultsResult].find((r) => r.status === "rejected") as PromiseRejectedResult | undefined;
    if (!failure) setLoadError(null);
    else if (failure.reason instanceof ApiError && failure.reason.status === 404)
      setLoadError("That campaign wasn't found. Showing demo data.");
    else if (failure.reason instanceof ApiError && failure.reason.status === 501) setLoadError(null);
    else setLoadError(errorText(failure.reason, "Couldn't load the campaign."));
  }, [campaignId]);

  useEffect(() => {
    active.current = true;
    setView(null);
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

  const act = useCallback(
    async (path: string, success: string, describe: (error: unknown) => string) => {
      if (!campaignId || busy) return;
      setBusy(true);
      setActionMessage(null);
      try {
        await apiPost(`/api/campaigns/${encodeURIComponent(campaignId)}/${path}`);
        setActionMessage(success);
        await load();
      } catch (error) {
        setActionMessage(describe(error));
      } finally {
        setBusy(false);
      }
    },
    [busy, campaignId, load],
  );

  const approve = useCallback(
    () =>
      act("approve", "Approved. Emails are going out to the allow-listed inboxes.", (e) =>
        e instanceof ApiError && e.status === 409 ? "This campaign was rejected, so it can't be approved." : errorText(e, "Approval failed. Please try again."),
      ),
    [act],
  );

  const reject = useCallback(
    () =>
      act("reject", "Proposal rejected. Nothing was sent.", (e) =>
        e instanceof ApiError && e.status === 409 ? "Only a draft can be rejected." : errorText(e, "Couldn't reject the proposal."),
      ),
    [act],
  );

  const generateReport = useCallback(
    () => act("report", "Recommendation generated.", (e) => errorText(e, "Couldn't generate the recommendation.")),
    [act],
  );

  const fromView = view ? fromCampaign(view) : null;
  const status = results?.status ?? fromView?.status ?? null;

  const data: DashboardData = {
    ...DEMO,
    ...(fromView
      ? {
          campaignName: "Win-back campaign",
          atStakeMonthly: fromView.atStakeMonthly,
          recipients: fromView.recipients,
          cohorts: fromView.cohorts,
          guardrails: fromView.guardrails,
          recommendation: fromView.recommendation,
        }
      : {}),
    ...(status ? { status: STATUS_LABEL[status] ?? status, currentStep: STEP_FOR_STATUS[status] ?? DEMO.currentStep } : {}),
    ...(results ? { results: { live: toSide(results.metrics.live), simulated: toSide(results.metrics.simulated) } } : {}),
  };
  if (fromView?.recommendation) data.currentStep = 6;

  return {
    data,
    campaignLive: view !== null,
    resultsLive: results !== null,
    campaignStatus: (status as CampaignStatus | null) ?? null,
    loadError,
    busy,
    actionMessage,
    approve,
    reject,
    generateReport,
  };
}
