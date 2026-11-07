// Owned by feature/delivery. The personalised page a recipient reaches from the email.
// Every value from the API is rendered as plain text (React escapes it). Never use raw HTML here.
import "../styles/winback.css";

import { useEffect, useState, type ReactNode } from "react";
import { useParams } from "react-router-dom";

import { ApiError, apiGet, apiPost } from "../lib/api";

// Shapes of GET /api/pages/{token} and POST /api/pages/{token}/checkout (backend/app/routers/pages.py).
type PageReason = { title: string; body: string };
type PageContent = {
  headline: string;
  subheadline: string;
  reasons: PageReason[];
  objection_response: string;
  cta_label: string;
};
type Offer = { label: string | null; percent_off: number; duration_months: number };
type PageData = { page_content: PageContent; offer: Offer; first_name: string };
type CheckoutResponse = { url: string };

type LoadState =
  | { kind: "loading" }
  | { kind: "ready"; data: PageData }
  | { kind: "invalid" }
  | { kind: "error"; message: string };

const API_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "");

// Offer wording comes from code and the offer's numbers, never from generated copy.
function offerText(offer: Offer): string | null {
  if (offer.percent_off <= 0) return null;
  const months = offer.duration_months === 1 ? "1 month" : `${offer.duration_months} months`;
  return `${offer.percent_off}% off for ${months}`;
}

export default function WinbackPage() {
  const { token = "" } = useParams();
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [checkingOut, setCheckingOut] = useState(false);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  // Which of the two buttons was used, so the error shows next to it.
  const [checkoutFrom, setCheckoutFrom] = useState<"top" | "bottom">("top");

  useEffect(() => {
    let active = true;
    apiGet<PageData>(`/api/pages/${encodeURIComponent(token)}`)
      .then((data) => active && setState({ kind: "ready", data }))
      .catch((error: unknown) => {
        if (!active) return;
        if (error instanceof ApiError && error.status === 404) setState({ kind: "invalid" });
        else setState({ kind: "error", message: "We couldn't load this page. Please try again in a moment." });
      });
    return () => {
      active = false;
    };
  }, [token]);

  async function startCheckout(from: "top" | "bottom") {
    setCheckoutFrom(from);
    setCheckingOut(true);
    setCheckoutError(null);
    try {
      const { url } = await apiPost<CheckoutResponse>(`/api/pages/${encodeURIComponent(token)}/checkout`);
      window.location.href = url;
    } catch {
      setCheckoutError("Checkout couldn't start. Please try again.");
      setCheckingOut(false);
    }
  }

  if (state.kind === "loading") {
    return (
      <Shell>
        <section className="wb-state" aria-busy="true">
          <span className="wb-loading" aria-hidden="true" />
          <p className="visually-hidden">Loading…</p>
        </section>
      </Shell>
    );
  }
  if (state.kind === "invalid") {
    return (
      <Shell>
        <section className="wb-state">
          <h1>This link is no longer valid.</h1>
          <p className="wb-lead">It may have expired. Check your inbox for a newer email from us.</p>
        </section>
      </Shell>
    );
  }
  if (state.kind === "error") {
    return (
      <Shell>
        <section className="wb-state">
          <h1>Something went wrong.</h1>
          <p className="wb-lead">{state.message}</p>
        </section>
      </Shell>
    );
  }

  const { page_content: page, offer, first_name } = state.data;
  const offerLine = offerText(offer);
  const label = checkingOut ? "Taking you to checkout…" : page.cta_label;
  const error = (from: "top" | "bottom") =>
    checkoutError && checkoutFrom === from ? <p role="alert">{checkoutError}</p> : null;

  return (
    <Shell token={token}>
      <section className="wb-hero">
        <p className="wb-eyebrow">Made for you, {first_name}</p>
        <h1>{page.headline}</h1>
        <p className="wb-lead">{page.subheadline}</p>
        {offerLine && <p className="wb-offer">{offerLine}</p>}
        <div className="wb-actions">
          <button type="button" className="btn--primary" onClick={() => startCheckout("top")} disabled={checkingOut}>
            {label}
          </button>
          {page.reasons.length > 0 && (
            <a className="btn btn--link" href="#reasons">
              See what's waiting
            </a>
          )}
        </div>
        {error("top")}
        <p className="wb-note">Secure checkout by Stripe. Cancel any time.</p>
      </section>

      {page.reasons.length > 0 && (
        <section className="wb-band" id="reasons" aria-labelledby="reasons-title">
          <div className="wb-band__inner">
            <h2 id="reasons-title">Why it's worth another look.</h2>
            <ol className="wb-tiles">
              {page.reasons.map((reason, index) => (
                <li key={index} className="wb-tile">
                  <span className="wb-tile__num" aria-hidden="true">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <h3>{reason.title}</h3>
                  <p>{reason.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>
      )}

      <section className="wb-assure" aria-label="Before you decide">
        <p className="wb-assure__quote">{page.objection_response}</p>
        <ul className="wb-checks">
          {offerLine && (
            <li>
              <Check />
              {offerLine}
            </li>
          )}
          <li>
            <Check />
            Secure checkout by Stripe
          </li>
          <li>
            <Check />
            Cancel any time
          </li>
        </ul>
        <div className="wb-actions">
          <button type="button" className="btn--wine" onClick={() => startCheckout("bottom")} disabled={checkingOut}>
            {label}
          </button>
        </div>
        {error("bottom")}
      </section>
    </Shell>
  );
}

function Check() {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true">
      <path d="M3 8.5 6.5 12 13 4.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// The token is only passed once the page has loaded, so the unsubscribe link is never shown for a bad link.
function Shell({ children, token }: { children: ReactNode; token?: string }) {
  return (
    <div className="wb">
      <header className="wb-nav">
        <div className="wb-nav__inner">
          <span className="wb-nav__brand">Pro plan</span>
        </div>
      </header>
      <main className="wb-main">{children}</main>
      {token && API_URL && (
        <footer className="wb-footer">
          You're receiving this because you used to subscribe to Pro.{" "}
          <a href={`${API_URL}/u/${encodeURIComponent(token)}`}>Unsubscribe</a>
        </footer>
      )}
    </div>
  );
}
