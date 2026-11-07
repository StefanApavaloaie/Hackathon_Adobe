// Owned by feature/delivery. Keep getAccessToken's name and return type: lib/api.ts uses it.
// One marketer login through Supabase Auth. The backend checks the token on every dashboard call.
import { useEffect, useState } from "react";

import { supabase } from "./supabase";

/** Whether the Supabase keys are set in frontend/.env. Without them there is no login at all. */
export const authConfigured = supabase !== null;

/** The logged-in user's Supabase access token, or null. Supabase refreshes it when it expires. */
export async function getAccessToken(): Promise<string | null> {
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

/** Signs in with email and password. Returns null on success, or a message to show. */
export async function signIn(email: string, password: string): Promise<string | null> {
  if (!supabase) return "Login isn't set up: VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY are missing.";
  try {
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (!error) return null;
    if (error.message.toLowerCase().includes("invalid login credentials")) {
      return "That email and password don't match. Check them and try again.";
    }
    if (error.message.toLowerCase().includes("email not confirmed")) {
      return "This account's email isn't confirmed yet. Confirm it in Supabase, then try again.";
    }
    return error.message || "Sign-in failed. Please try again.";
  } catch {
    return "Couldn't reach the login service. Check your connection and try again.";
  }
}

export async function signOut(): Promise<void> {
  await supabase?.auth.signOut();
}

export type SessionState =
  | { status: "loading" }
  | { status: "signed-in"; email: string | null }
  | { status: "signed-out" }
  | { status: "unconfigured" };

/** The current login, kept up to date as the user signs in or out (in this tab or another). */
export function useSession(): SessionState {
  const [state, setState] = useState<SessionState>(supabase ? { status: "loading" } : { status: "unconfigured" });

  useEffect(() => {
    if (!supabase) return;
    let active = true;
    supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      setState(data.session ? { status: "signed-in", email: data.session.user.email ?? null } : { status: "signed-out" });
    });
    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!active) return;
      setState(session ? { status: "signed-in", email: session.user.email ?? null } : { status: "signed-out" });
    });
    return () => {
      active = false;
      data.subscription.unsubscribe();
    };
  }, []);

  return state;
}
