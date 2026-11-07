// Owned by feature/delivery. Keep the name and props: main.tsx wraps the dashboard in it.
import type { ReactNode } from "react";

/** PLACEHOLDER. Send logged-out users to /login. Shows the page to everyone until implemented. */
export default function RequireLogin({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
