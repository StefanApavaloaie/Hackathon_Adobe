// Owned by frontend/Stefan. Starts an agent run and follows it until it produces a campaign.
//
//   POST /api/runs                -> { run_id }
//   GET  /api/runs/{id}           -> { status, current_step, error, campaign_id, cohorts }
//   POST /api/runs/{id}/resume    -> restarts a failed run from its saved step
//
// The run's ID lives in the URL (?run=<id>), so a refresh keeps following it. When the run
// reaches awaiting_approval, the page switches to ?campaign=<id>.
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { apiGet, apiPost } from "../lib/api";

interface RunResponse {
  status: "running" | "awaiting_approval" | "failed" | string;
  current_step: string | null;
  error: string | null;
  campaign_id: string | null;
}

export const RUN_STEPS = [
  { id: "import", label: "Import", detail: "Importing cancelled customers" },
  { id: "diagnose", label: "Diagnose", detail: "Working out why customers left" },
  { id: "strategy", label: "Strategy", detail: "Choosing offers and writing variants" },
  { id: "propose", label: "Propose", detail: "Preparing the proposal" },
];

const POLL_MS = 2000;

export interface AgentRunState {
  runId: string | null;
  run: RunResponse | null;
  /** Index into RUN_STEPS of the step in progress. */
  stepIndex: number;
  starting: boolean;
  error: string | null;
  start: () => Promise<void>;
  resume: () => Promise<void>;
  dismiss: () => void;
}

export function useAgentRun(): AgentRunState {
  const [params, setParams] = useSearchParams();
  const runId = params.get("run");
  const [run, setRun] = useState<RunResponse | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setRun(null);
    setError(null);
    if (!runId) return;
    let active = true;

    const poll = async () => {
      try {
        const response = await apiGet<RunResponse>(`/api/runs/${encodeURIComponent(runId)}`);
        if (!active) return;
        setRun(response);
        setError(null);
        if (response.status === "awaiting_approval" && response.campaign_id) {
          setParams({ campaign: response.campaign_id });
        }
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "Couldn't check the run.");
      }
    };

    void poll();
    const timer = window.setInterval(() => void poll(), POLL_MS);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [runId, setParams]);

  const start = useCallback(async () => {
    if (starting || runId) return;
    setStarting(true);
    setError(null);
    try {
      const { run_id } = await apiPost<{ run_id: string }>("/api/runs", {});
      setParams({ run: run_id });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't start a run.");
    } finally {
      setStarting(false);
    }
  }, [runId, setParams, starting]);

  const resume = useCallback(async () => {
    if (!runId) return;
    setError(null);
    try {
      await apiPost(`/api/runs/${encodeURIComponent(runId)}/resume`);
      setRun((current) => (current ? { ...current, status: "running", error: null } : current));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't resume the run.");
    }
  }, [runId]);

  const dismiss = useCallback(() => setParams({}), [setParams]);

  const found = RUN_STEPS.findIndex((s) => s.id === run?.current_step);
  return { runId, run, stepIndex: found < 0 ? 0 : found, starting, error, start, resume, dismiss };
}
