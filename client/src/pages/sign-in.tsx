import { useState } from "react";
import { useLocation, useNavigate } from "react-router";
import type { SubmitEvent, SVGProps } from "react";
import logo from "../assets/logo.png";
import { Button } from "../components/button";
import { Text } from "../components/text";
import { TextField } from "../components/text-field";
import { login } from "../lib/api";

function UserIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" aria-hidden="true" className="size-5" {...props}>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21a8 8 0 0 1 16 0" />
    </svg>
  );
}

function LockIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" aria-hidden="true" className="size-5" {...props}>
      <rect x="5" y="10" width="14" height="11" rx="2" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3" />
      <path d="M12 14.5v2.5" />
    </svg>
  );
}

function EyeIcon({ off = false, ...props }: SVGProps<SVGSVGElement> & { off?: boolean }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" aria-hidden="true" className="size-5" {...props}>
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" />
      <circle cx="12" cy="12" r="3" />
      {off && <path d="M3 3l18 18" />}
    </svg>
  );
}

export function SignIn() {
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string>();
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "/dashboard";

  async function handleSubmit(e: SubmitEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    setError(undefined);
    setSubmitting(true);
    try {
      await login(String(data.get("email") ?? ""), String(data.get("password") ?? ""));
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed");
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-start justify-center px-4 py-12 sm:items-center">
      <div className="w-full max-w-md rounded-xl border border-blue-grey-800 bg-canvas px-6 py-10 sm:px-12">
        <img src={logo} alt="Waypoint" className="mx-auto w-44" />

        <Text variant="h3" as="h1" weight="normal" align="center" className="mt-4">
          Sign In
        </Text>

        <form onSubmit={handleSubmit} className="mt-8 space-y-5">
          <TextField
            label="Email"
            name="email"
            type="email"
            autoComplete="username"
            size="lg"
            leading={<UserIcon />}
            required
            fullWidth
          />

          <TextField
            label="Password"
            name="password"
            type={showPassword ? "text" : "password"}
            autoComplete="current-password"
            size="lg"
            leading={<LockIcon />}
            trailing={
              <button
                type="button"
                onClick={() => setShowPassword((s) => !s)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                aria-pressed={showPassword}
                className="flex cursor-pointer rounded text-blue-grey-300 hover:text-blue-grey-050 focus-visible:outline-2 focus-visible:outline-purple-400"
              >
                <EyeIcon off={showPassword} />
              </button>
            }
            error={error}
            required
            fullWidth
          />

          <Button type="submit" size="lg" fullWidth disabled={submitting} className="mt-8 font-semibold">
            {submitting ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      </div>
    </main>
  );
}

export default SignIn;
