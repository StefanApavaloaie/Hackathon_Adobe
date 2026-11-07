import { useEffect, useState } from "react";

import { apiGet } from "../lib/api";
import { supabase } from "../lib/supabase";

interface DependencyStatus {
  status: string;
  dependencies: Record<string, string>;
}

// Placeholder that proves the frontend can reach the backend. Replace with the dashboard.
export default function Home() {
  const [data, setData] = useState<DependencyStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<DependencyStatus>("/health/dependencies")
      .then(setData)
      .catch((err: Error) => setError(err.message));
  }, []);

  return (
    <main>
      <h1>Win-back Agent</h1>
      <p>Project skeleton: no product features yet.</p>

      <h2>Backend</h2>
      {error && <p role="alert">Not connected: {error}</p>}
      {!error && !data && <p>Checking the connection. A sleeping backend can take about a minute.</p>}
      {data && (
        <>
          <p>Connected. Overall status: {data.status}</p>
          <ul>
            {Object.entries(data.dependencies).map(([name, status]) => (
              <li key={name}>
                {name}: {status}
              </li>
            ))}
          </ul>
        </>
      )}

      <h2>Frontend</h2>
      <p>Supabase login: {supabase ? "configured" : "not_configured"}</p>
    </main>
  );
}
