// Owned by feature/delivery. Stripe Checkout returns here after a successful payment.
// The conversion itself is recorded by the Stripe webhook, not by this page.
import "../styles/winback.css";

export default function ThanksPage() {
  return (
    <div className="wb">
      <header className="wb-nav">
        <div className="wb-nav__inner">
          <span className="wb-nav__brand">Pro plan</span>
        </div>
      </header>
      <main className="wb-main">
        <section className="wb-state">
          <span className="wb-tick" aria-hidden="true">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.2">
              <path d="M3 8.5 6.5 12 13 4.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
          <p className="wb-eyebrow">You're all set</p>
          <h1>Welcome back.</h1>
          <p className="wb-lead">
            Your subscription is active again. A receipt is on its way to your inbox, and everything you set up is
            right where you left it.
          </p>
          <p className="wb-note">You can close this page.</p>
        </section>
      </main>
    </div>
  );
}
