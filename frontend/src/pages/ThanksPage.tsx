// Owned by feature/delivery. Stripe Checkout returns here after a successful payment.
// The conversion itself is recorded by the Stripe webhook, not by this page.
import type { CSSProperties } from "react";

export default function ThanksPage() {
  return (
    <main style={styles.page}>
      <div style={styles.card}>
        <div style={styles.icon} aria-hidden="true">
          ✓
        </div>
        <h1 style={styles.headline}>Welcome back!</h1>
        <p style={styles.body}>
          Your subscription is active again. A receipt is on its way to your inbox, and everything you set up
          is right where you left it.
        </p>
        <p style={styles.fineprint}>You can close this page.</p>
      </div>
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
    maxWidth: 480,
    margin: "0 auto",
    background: "#fff",
    borderRadius: 16,
    padding: "40px 32px",
    textAlign: "center",
    boxShadow: "0 10px 30px rgba(15, 23, 42, 0.08)",
  },
  icon: {
    width: 56,
    height: 56,
    margin: "0 auto 20px",
    borderRadius: 999,
    background: "#dcfce7",
    color: "#166534",
    fontSize: 28,
    fontWeight: 700,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  headline: { margin: "0 0 12px", fontSize: 28, color: "#0f172a" },
  body: { margin: "0 0 16px", fontSize: 16, lineHeight: 1.6, color: "#475569" },
  fineprint: { margin: 0, fontSize: 13, color: "#94a3b8" },
};
