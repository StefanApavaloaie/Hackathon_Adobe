// Owned by feature/delivery. The one marketer login. There is no sign-up: the user is created in Supabase.
import "../styles/winback.css";

import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { authConfigured, signIn, useSession } from "../lib/auth";

// Only return to a page inside this app, never to an outside URL.
function returnPath(state: unknown): string {
  const from = (state as { from?: unknown } | null)?.from;
  return typeof from === "string" && from.startsWith("/") && !from.startsWith("//") && !from.startsWith("/login")
    ? from
    : "/";
}

export default function LoginPage() {
  const session = useSession();
  const location = useLocation();
  const navigate = useNavigate();
  const destination = returnPath(location.state);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (session.status === "signed-in") return <Navigate to={destination} replace />;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    const message = await signIn(email.trim(), password);
    if (message) {
      setError(message);
      setBusy(false);
      return;
    }
    navigate(destination, { replace: true });
  }

  return (
    <div className="wb">
      <header className="wb-nav">
        <div className="wb-nav__inner">
          <span className="wb-nav__brand">Win-back</span>
        </div>
      </header>
      <main className="wb-main">
        <section className="auth">
          <p className="wb-eyebrow">Marketer login</p>
          <h1>Welcome back.</h1>
          <p className="wb-lead">Sign in to review the agent's proposal and approve the campaign.</p>

          <form className="auth-card" onSubmit={onSubmit} noValidate>
            {!authConfigured && (
              <p role="alert">
                Login isn't set up: add VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY to frontend/.env, then restart
                the dev server.
              </p>
            )}
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={busy}
            />
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={busy}
            />
            {error && (
              <p role="alert" className="auth-error">
                {error}
              </p>
            )}
            <button type="submit" disabled={busy || !authConfigured || !email.trim() || !password}>
              {busy ? "Signing in…" : "Sign in"}
            </button>
          </form>
          <p className="wb-note">There's no sign-up. The marketer's account is created in Supabase.</p>
        </section>
      </main>
    </div>
  );
}
