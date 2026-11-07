// Owned by frontend/Stefan. Display components for the dashboard. Each takes its data as props,
// so the feature branches can pass real API data in place of DEMO.
import type { CSSProperties } from "react";

import { type Cohort, type DashboardData, type ResultSide, money } from "./demoData";
import { IconCheck, IconFlask, IconLive, IconReturn, IconShield, IconSpark } from "./icons";

const LINKS = [
  { href: "#top", label: "Overview" },
  { href: "#guardrails", label: "Guardrails" },
  { href: "#reasons", label: "Reasons" },
  { href: "#results", label: "Results" },
  { href: "#next", label: "Next step" },
];

export type DataSource = "demo" | "partly" | "live";

export function Navs({
  campaignName,
  status,
  source = "demo",
}: Pick<DashboardData, "campaignName" | "status"> & { source?: DataSource }) {
  return (
    <div className="navs">
      <header className="globalnav">
        <div className="globalnav__inner">
          <a className="brand" href="#top">
            <IconReturn className="brand__icon" />
            Win-back
          </a>
          <nav aria-label="Sections">
            <ul className="globalnav__links">
              {LINKS.map((link) => (
                <li key={link.href}>
                  <a href={link.href}>{link.label}</a>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      </header>
      <div className="campaignbar">
        <div className="campaignbar__inner">
          <p className="campaignbar__name">{campaignName}</p>
          <span className={`tag ${source === "live" ? "tag--live" : "tag--demo"}`}>
            {source === "live" ? "Live data" : source === "partly" ? "Partly demo" : "Demo data"}
          </span>
          <span className="tag tag--status">{status}</span>
          <a className="btn btn--primary btn--sm campaignbar__cta" href="#decision">
            Approve
          </a>
        </div>
      </div>
    </div>
  );
}

interface HeroProps {
  data: DashboardData;
  /** True when a real campaign is loaded, so the actions call the API. */
  connected?: boolean;
  campaignStatus?: string | null;
  busy?: boolean;
  message?: string | null;
  onApprove?: () => void;
  onReject?: () => void;
}

export function Hero({ data, connected = false, campaignStatus = null, busy = false, message, onApprove, onReject }: HeroProps) {
  const canAct = connected && campaignStatus === "draft" && !busy;
  const approved = campaignStatus === "approved" || campaignStatus === "sending" || campaignStatus === "sent";
  const note = message ?? (connected ? null : "Demo: approving connects once a campaign is loaded.");
  return (
    <section className="hero" id="top" aria-labelledby="hero-title">
      <h1 id="hero-title">
        Win back <span className="hero__figure">{money(data.atStakeMonthly)}</span> a month.
      </h1>
      <p className="hero__lead">
        {data.recipients} cancellations. {data.cohorts.length} reasons. One decision.
      </p>
      <div className="hero__actions" id="decision">
        <button
          type="button"
          className="btn--primary btn--lg"
          aria-disabled={!canAct}
          aria-describedby={note ? "decision-note" : undefined}
          onClick={canAct ? onApprove : undefined}
        >
          <IconCheck />
          {busy ? "Working…" : approved ? "Approved" : "Approve & send"}
        </button>
        {!approved && (
          <button
            type="button"
            className="btn--link"
            aria-disabled={!canAct}
            aria-describedby={note ? "decision-note" : undefined}
            onClick={canAct ? onReject : undefined}
          >
            Reject proposal
          </button>
        )}
      </div>
      {note && (
        <p className="hero__note" id="decision-note" role="status">
          {note}
        </p>
      )}
      <ol className="steps" aria-label="Agent progress">
        {data.steps.map((step, index) => {
          const state = index < data.currentStep ? "done" : index === data.currentStep ? "current" : "todo";
          return (
            <li key={step} className={`steps__item steps__item--${state}`} aria-current={state === "current" ? "step" : undefined}>
              {state === "done" && <IconCheck />}
              {step}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

export function Guardrails({ data }: { data: DashboardData }) {
  const g = data.guardrails;
  const share = Math.min(1, g.exposure / g.exposureLimit);
  const stats = [
    { value: String(data.cohorts.length), label: "Reasons found" },
    { value: String(data.recipients), label: "Recipients" },
    { value: `${g.maxDiscountPercent}%`, label: "Max discount" },
    { value: String(g.sendCap), label: "Send cap" },
  ];
  return (
    <section className="band" id="guardrails" aria-labelledby="guardrails-title">
      <div className="band__inner" data-reveal>
        <IconShield className="band__icon" />
        <h2 id="guardrails-title">Every limit, enforced in code.</h2>
        <p className="band__lead">The agent suggests. Prices, recipients and caps are checked before a single email goes out.</p>
        <dl className="stats">
          {stats.map((stat) => (
            <div key={stat.label}>
              <dt>{stat.label}</dt>
              <dd className="num">{stat.value}</dd>
            </div>
          ))}
        </dl>
        <div className="meter">
          <div className="meter__head">
            <span>Maximum discount exposure</span>
            <span className="num">
              <strong>{money(g.exposure)}</strong> of {money(g.exposureLimit)}
            </span>
          </div>
          <div
            className="meter__track"
            role="meter"
            aria-label="Maximum discount exposure"
            aria-valuemin={0}
            aria-valuemax={g.exposureLimit}
            aria-valuenow={g.exposure}
          >
            <div className="meter__fill" style={{ "--share": share } as CSSProperties} />
          </div>
        </div>
      </div>
    </section>
  );
}

function CohortCard({ cohort, tone, index }: { cohort: Cohort; tone: "crimson" | "light"; index: number }) {
  return (
    <article className={`cohort cohort--${tone}`} data-reveal style={{ "--i": index } as CSSProperties}>
      <h3>{cohort.name}</h3>
      <p className="cohort__offer">{cohort.offer}</p>
      <p className="cohort__figure num">{money(cohort.atStakeMonthly)}</p>
      <p className="cohort__caption">monthly revenue at stake</p>
      <p className="cohort__reasoning">{cohort.reasoning}</p>
      <ul className="variants" aria-label={`${cohort.name} message variants`}>
        {cohort.variants.map((line, i) => (
          <li key={line}>
            <span className="variants__key">{i === 0 ? "A" : "B"}</span>
            {line}
          </li>
        ))}
      </ul>
    </article>
  );
}

export function Reasons({ cohorts }: { cohorts: Cohort[] }) {
  return (
    <section className="section" id="reasons" aria-labelledby="reasons-title">
      <h2 id="reasons-title" className="section__title" data-reveal>
        Why they left. <span className="section__title-2">What we'll offer.</span>
      </h2>
      <div className="cohorts">
        {cohorts.map((cohort, i) => (
          <CohortCard key={cohort.name} cohort={cohort} index={i} tone={i % 4 === 0 || i % 4 === 3 ? "crimson" : "light"} />
        ))}
      </div>
    </section>
  );
}

function ResultCard({ kind, side }: { kind: "live" | "simulated"; side: ResultSide }) {
  const live = kind === "live";
  return (
    <article className={`result result--${kind}`} data-reveal style={{ "--i": live ? 0 : 1 } as CSSProperties}>
      <span className="result__icon">{live ? <IconLive /> : <IconFlask />}</span>
      <h3>{live ? "Live" : "Simulated"}</h3>
      <p className="result__note">{live ? "Real Stripe test checkouts" : "Seeded customers, not real revenue"}</p>
      <p className="result__figure num">
        {money(side.recoveredMonthly)}
        <span>/mo</span>
      </p>
      <p className="result__caption">monthly revenue recovered</p>
      <dl className="rows">
        <div>
          <dt>Sent</dt>
          <dd className="num">{side.sent}</dd>
        </div>
        {side.clicked !== undefined && (
          <div>
            <dt>Clicked</dt>
            <dd className="num">{side.clicked}</dd>
          </div>
        )}
        {side.pageViewed !== undefined && (
          <div>
            <dt>Page viewed</dt>
            <dd className="num">{side.pageViewed}</dd>
          </div>
        )}
        {side.startedCheckout !== undefined && (
          <div>
            <dt>Started checkout</dt>
            <dd className="num">{side.startedCheckout}</dd>
          </div>
        )}
        <div>
          <dt>Won back</dt>
          <dd className="num rows__win">{side.wonBack}</dd>
        </div>
      </dl>
    </article>
  );
}

export function Results({ results, live = false }: { results: DashboardData["results"]; live?: boolean }) {
  return (
    <section className="section section--tinted" id="results" aria-labelledby="results-title">
      <div data-reveal>
        <h2 id="results-title" className="section__title">
          Results, kept honest.
        </h2>
        <p className="section__lead">Live and simulated numbers sit side by side. They are never added together.</p>
        <p className="section__source">
          <span className={`tag ${live ? "tag--live" : "tag--demo"}`}>{live ? "From the campaign" : "Demo data"}</span>
        </p>
      </div>
      <div className="results">
        <ResultCard kind="live" side={results.live} />
        <ResultCard kind="simulated" side={results.simulated} />
      </div>
    </section>
  );
}

interface NextStepProps {
  recommendation: string | null;
  /** True when a real campaign is loaded, so the agent can be asked for a recommendation. */
  connected?: boolean;
  busy?: boolean;
  onGenerate?: () => void;
}

export function NextStep({ recommendation, connected = false, busy = false, onGenerate }: NextStepProps) {
  return (
    <section className="section next" id="next" aria-labelledby="next-title">
      <div className="next__inner" data-reveal>
        <IconSpark className="next__icon" />
        <h2 id="next-title" className="next__title">
          What to do next.
        </h2>
        {recommendation ? (
          <p className="next__text">{recommendation}</p>
        ) : (
          <p className="next__empty">No recommendation yet. Ask the agent once results start coming in.</p>
        )}
        {connected && (
          <button type="button" className="btn next__action" aria-disabled={busy} onClick={busy ? undefined : onGenerate}>
            {busy ? "Working…" : recommendation ? "Refresh recommendation" : "Generate recommendation"}
          </button>
        )}
        <p className="next__note">The agent suggests this. It never runs on its own.</p>
      </div>
    </section>
  );
}
