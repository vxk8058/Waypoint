import { useState } from "react";
import type { SubmitEvent, SVGProps } from "react";
import logo from "../assets/logo.png";
import { Button } from "../components/button";
import { Text } from "../components/text";
import { TextField } from "../components/text-field";

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

  function handleSubmit(e: SubmitEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    // TODO: hook up authentication
    console.log("sign in", {
      username: data.get("username"),
      remember: data.get("remember") === "on",
    });
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
            label="Username"
            name="username"
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
            required
            fullWidth
          />

          <label className="flex w-fit cursor-pointer items-center gap-3 text-blue-grey-100">
            <input
              type="checkbox"
              name="remember"
              className="size-5 cursor-pointer rounded accent-purple-500"
            />
            Remember Me
          </label>

          <Button type="submit" size="lg" fullWidth className="mt-3 font-semibold">
            Sign in
          </Button>
        </form>
      </div>
    </main>
  );
}

export default SignIn;
