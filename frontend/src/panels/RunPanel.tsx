// Owned by feature/agent. Keep these props: DashboardPage passes them.
import { useEffect, useRef, useState } from "react";

import { apiGet, apiPost } from "../lib/api";

export interface RunPanelProps {
  /** Call this when a run has produced a campaign, so the other panels show it. */
  onCampaignReady: (campaignId: string) => void;
}

type RunStatus = "running" | "awaiting_approval" | "failed" | "complete";

interface RunCohort {
  label: string;
  customer_count: number;
  mrr_at_stake_cents: number;
}

interface RunState {
  status: RunStatus;
  current_step: string | null;
  error: string | null;
  campaign_id: string | null;
  cohorts: RunCohort[];
}

const STEPS = ["import", "diagnose", "strategy", "propose"];
const POLL_MS = 2000;
const RUN_KEY = "winback.runId";

const formatCents = (cents: number) =>
  `$${(cents / 100).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default function RunPanel({ onCampaignReady }: RunPanelProps) {
  // Keep the run id across a page refresh, so polling picks up where it left off.
  const [runId, setRunId] = useState<string | null>(() => localStorage.getItem(RUN_KEY));
  const [run, setRun] = useState<RunState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pollKey, setPollKey] = useState(0);
  const reported = useRef<string | null>(null);
  const onReady = useRef(onCampaignReady);
  onReady.current = onCampaignReady;

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const poll = async () => {
      try {
        const state = await apiGet<RunState>(`/api/runs/${runId}`);
        if (cancelled) return;
        setRun(state);
        setError(null);
        if (state.status === "awaiting_approval" && state.campaign_id && reported.current !== state.campaign_id) {
          reported.current = state.campaign_id;
          onReady.current(state.campaign_id);
        }
        if (state.status === "running") timer = setTimeout(poll, POLL_MS);
      } catch (err) {
        if (cancelled) return;
        setError((err as Error).message);
        timer = setTimeout(poll, POLL_MS);
      }
    };

    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [runId, pollKey]);

  const startRun = async () => {
    setBusy(true);
    setError(null);
    try {
      const { run_id } = await apiPost<{ run_id: string }>("/api/runs");
      localStorage.setItem(RUN_KEY, run_id);
      reported.current = null;
      setRun(null);
      setRunId(run_id);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const resumeRun = async () => {
    if (!runId) return;
    setBusy(true);
    setError(null);
    try {
      await apiPost(`/api/runs/${runId}/resume`);
      setRun((r) => (r ? { ...r, status: "running", error: null } : r));
      setPollKey((k) => k + 1);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const running = run?.status === "running";

  return (
    <section>
      <h2>Agent run</h2>
      <p>
        <button onClick={startRun} disabled={busy || running}>
          {running ? "Run in progress…" : "Start run"}
        </button>{" "}
        {run?.status === "failed" && (
          <button onClick={resumeRun} disabled={busy}>
            Resume
          </button>
        )}
      </p>

      {error && <p role="alert">Error: {error}</p>}
      {runId && !run && !error && <p>Loading run…</p>}

      {run && (
        <>
          <p>
            Status: <strong>{run.status.replace("_", " ")}</strong>
            {run.current_step && (
              <>
                {" "}
                · Step {Math.max(STEPS.indexOf(run.current_step), 0) + 1} of {STEPS.length}:{" "}
                <strong>{run.current_step}</strong>
              </>
            )}
          </p>
          <ol>
            {STEPS.map((step) => {
              const at = STEPS.indexOf(run.current_step ?? "");
              const i = STEPS.indexOf(step);
              const done = run.status === "awaiting_approval" || run.status === "complete" || i < at;
              const mark = done ? "✓" : i === at ? (run.status === "failed" ? "✗" : "…") : "";
              return (
                <li key={step}>
                  {step} {mark}
                </li>
              );
            })}
          </ol>
          {run.status === "failed" && run.error && <p role="alert">Run failed: {run.error}</p>}

          {run.cohorts.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th align="left">Cohort</th>
                  <th align="right">Customers</th>
                  <th align="right">Revenue at stake (monthly)</th>
                </tr>
              </thead>
              <tbody>
                {run.cohorts.map((c) => (
                  <tr key={c.label}>
                    <td>{c.label}</td>
                    <td align="right">{c.customer_count}</td>
                    <td align="right">{formatCents(c.mrr_at_stake_cents)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </section>
  );
}
