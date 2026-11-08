import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";
import { fetchCurrentUser } from "../lib/api";
import { useAsync } from "../lib/use-async";

/** Renders children only for a signed-in user; otherwise redirects to /sign-in. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const location = useLocation();
  const { data: user, error, loading } = useAsync(fetchCurrentUser, []);

  if (loading) return null;
  if (error) {
    return (
      <main className="flex min-h-screen items-center justify-center px-4 text-blue-grey-300">
        {error.message}
      </main>
    );
  }
  if (!user) return <Navigate to="/sign-in" replace state={{ from: location.pathname }} />;
  return children;
}
