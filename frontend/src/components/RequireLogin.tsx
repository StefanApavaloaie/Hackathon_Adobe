// Owned by feature/delivery. Keep the name and props: main.tsx wraps the dashboard in it.
import "../styles/winback.css";

import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useSession } from "../lib/auth";

/** Sends logged-out users to /login, and brings them back to the same page (with ?campaign=) after. */
export default function RequireLogin({ children }: { children: ReactNode }) {
  const session = useSession();
  const location = useLocation();

  if (session.status === "loading") {
    return (
      <div className="wb">
        <main className="wb-main">
          <section className="wb-state" aria-busy="true">
            <span className="wb-loading" aria-hidden="true" />
            <p className="wb-note">Checking login…</p>
          </section>
        </main>
      </div>
    );
  }

  if (session.status === "signed-out") {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  }

  if (session.status === "unconfigured") {
    // Local development without Supabase keys. The backend still decides: without
    // ALLOW_DEV_AUTH=true every dashboard call will return 401.
    return (
      <>
        <p className="auth-warning" role="status">
          Login is off: VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY aren't set in frontend/.env. Anyone can open this
          page, and the API only answers if the backend has ALLOW_DEV_AUTH=true.
        </p>
        {children}
      </>
    );
  }

  return <>{children}</>;
}
