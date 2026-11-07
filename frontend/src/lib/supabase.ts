import { createClient } from "@supabase/supabase-js";

const rawUrl = import.meta.env.VITE_SUPABASE_URL as string | undefined;

// Only the project's origin, https://<ref>.supabase.co. The dashboard also shows the REST address
// (…/rest/v1/), and with that path every login fails with "Invalid path specified in request URL".
function projectOrigin(value: string | undefined): string | undefined {
  if (!value) return undefined;
  try {
    return new URL(value).origin;
  } catch {
    return undefined;
  }
}

const url = projectOrigin(rawUrl);
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

// Used for login only. All data goes through the backend. Null until keys are set,
// so the app still runs without them.
export const supabase = url && anonKey ? createClient(url, anonKey) : null;
