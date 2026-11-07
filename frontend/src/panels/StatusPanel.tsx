// Shared by both branches. Frozen after step 0: change it only through a pull request to main.
import { useEffect, useState } from "react";

import { apiGet } from "../lib/api";
import { supabase } from "../lib/supabase";

interface DependencyStatus {
  status: string;
  dependencies: Record<string, string>;
}

export default function StatusPanel() {
  const [data, setData] = useState<DependencyStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<DependencyStatus>("/health/dependencies")
      .then(setData)
      .catch((err: Error) => setError(err.message));
  }, []);

  return (
    <section>
      <h2>Status</h2>
      {error && <p role="alert">Backend not connected: {error}</p>}
      {!error && !data && <p>Checking the backend. A sleeping backend can take about a minute.</p>}
      {data && (
        <p>
          Backend connected ({data.status}).{" "}
          {Object.entries(data.dependencies)
            .map(([name, status]) => `${name}: ${status}`)
            .join(", ")}
        </p>
      )}
      <p>Supabase login: {supabase ? "configured" : "not_configured"}</p>
    </section>
  );
}
