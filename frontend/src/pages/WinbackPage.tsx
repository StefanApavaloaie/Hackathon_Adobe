// Owned by feature/delivery. The personalised page a recipient reaches from the email.
// Every value from the API is rendered as plain text (React escapes it). Never use raw HTML here.
import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
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

  async function startCheckout() {
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
        <p style={styles.muted}>Loading…</p>
      </Shell>
    );
  }
  if (state.kind === "invalid") {
    return (
      <Shell>
        <h1 style={styles.headline}>This link is no longer valid.</h1>
      </Shell>
    );
  }
  if (state.kind === "error") {
    return (
      <Shell>
        <p style={styles.error}>{state.message}</p>
      </Shell>
    );
  }

  const { page_content: page, offer, first_name } = state.data;
  const offerLine = offerText(offer);

  return (
    <Shell>
      <p style={styles.greeting}>Hi {first_name},</p>
      <h1 style={styles.headline}>{page.headline}</h1>
      <p style={styles.subheadline}>{page.subheadline}</p>

      {offerLine && <div style={styles.offer}>{offerLine}</div>}

      {page.reasons.length > 0 && (
        <ul style={styles.reasons}>
          {page.reasons.map((reason, index) => (
            <li key={index} style={styles.reason}>
              <span style={styles.check} aria-hidden="true">
                ✓
              </span>
              <div>
                <h2 style={styles.reasonTitle}>{reason.title}</h2>
                <p style={styles.reasonBody}>{reason.body}</p>
              </div>
            </li>
          ))}
        </ul>
      )}

      <p style={styles.objection}>{page.objection_response}</p>

      <button
        type="button"
        onClick={startCheckout}
        disabled={checkingOut}
        style={{ ...styles.button, ...(checkingOut ? styles.buttonBusy : {}) }}
      >
        {checkingOut ? "Taking you to checkout…" : page.cta_label}
      </button>
      {checkoutError && (
        <p role="alert" style={styles.error}>
          {checkoutError}
        </p>
      )}
      <p style={styles.fineprint}>Secure checkout by Stripe. Cancel any time.</p>
    </Shell>
  );
}

function Shell({ children }: { children: ReactNode }) {
  return (
    <main style={styles.page}>
      <div style={styles.card}>{children}</div>
    </main>
  );
}

const styles: Record<string, CSSProperties> = {
  page: {
    minHeight: "100vh",
    margin: 0,
    padding: "48px 16px",
    boxSizing: "border-box",
    background: "linear-gradient(180deg, #eef2ff 0%, #f8fafc 60%)",
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, Arial, sans-serif",
    color: "#1e293b",
  },
  card: {
    maxWidth: 560,
    margin: "0 auto",
    background: "#fff",
    borderRadius: 16,
    padding: "40px 32px",
    boxShadow: "0 10px 30px rgba(15, 23, 42, 0.08)",
  },
  greeting: { margin: "0 0 8px", color: "#64748b", fontSize: 16 },
  headline: { margin: "0 0 12px", fontSize: 32, lineHeight: 1.2, color: "#0f172a" },
  subheadline: { margin: "0 0 24px", fontSize: 18, lineHeight: 1.5, color: "#334155" },
  offer: {
    display: "inline-block",
    margin: "0 0 28px",
    padding: "8px 14px",
    borderRadius: 999,
    background: "#dcfce7",
    color: "#166534",
    fontWeight: 700,
    fontSize: 15,
  },
  reasons: { listStyle: "none", margin: "0 0 24px", padding: 0, display: "grid", gap: 16 },
  reason: { display: "flex", gap: 12, alignItems: "flex-start" },
  check: {
    flex: "0 0 24px",
    height: 24,
    borderRadius: 999,
    background: "#e0e7ff",
    color: "#4338ca",
    fontSize: 13,
    fontWeight: 700,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  reasonTitle: { margin: "0 0 2px", fontSize: 16, color: "#0f172a" },
  reasonBody: { margin: 0, fontSize: 15, lineHeight: 1.5, color: "#475569" },
  objection: {
    margin: "0 0 28px",
    padding: "14px 16px",
    borderLeft: "3px solid #c7d2fe",
    background: "#f8fafc",
    fontSize: 15,
    lineHeight: 1.5,
    color: "#475569",
  },
  button: {
    width: "100%",
    padding: "14px 20px",
    border: "none",
    borderRadius: 10,
    background: "#4f46e5",
    color: "#fff",
    fontSize: 17,
    fontWeight: 700,
    cursor: "pointer",
  },
  buttonBusy: { background: "#818cf8", cursor: "wait" },
  error: { margin: "12px 0 0", color: "#b91c1c", fontSize: 15 },
  muted: { margin: 0, color: "#64748b" },
  fineprint: { margin: "14px 0 0", textAlign: "center", fontSize: 13, color: "#94a3b8" },
};
