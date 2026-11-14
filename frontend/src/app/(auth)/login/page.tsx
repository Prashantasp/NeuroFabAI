"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { CheckCircle2, Eye, EyeOff, Loader2 } from "lucide-react";
import { Suspense, useState } from "react";

import { Button } from "@/components/ui/button";
import { InlineError } from "@/components/ui/states";
import { useAuth } from "@/contexts/AuthContext";
import { useAction } from "@/hooks/use-async";
import { ApiError, errorMessage } from "@/lib/api";

/**
 * Only same-origin paths are accepted as a redirect target. Without this check
 * `?redirect=https://evil.example` would turn the login page into an open
 * redirect that phishes a freshly-authenticated user.
 */
function safeRedirect(value: string | null): string {
  if (!value) return "/dashboard";
  if (!value.startsWith("/") || value.startsWith("//")) return "/dashboard";
  return value;
}

export default function LoginPage() {
  return (
    <Suspense fallback={<Loader2 className="size-5 animate-spin text-muted-foreground" />}>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { signIn } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const justRegistered = searchParams.get("registered") === "1";
  const redirectTo = safeRedirect(searchParams.get("redirect"));

  const { run: submit, isPending } = useAction(async () => {
    setError(null);
    try {
      await signIn(email.trim(), password);
      router.replace(redirectTo);
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 429
          ? err.message
          : errorMessage(err, "Could not sign in. Please try again."),
      );
    }
  });

  return (
    <div className="w-full max-w-sm">
      <div className="rounded-xl border bg-card p-6 shadow-sm">
        <div className="space-y-1 text-center">
          <h1 className="text-lg font-semibold tracking-tight">Sign in</h1>
          <p className="text-sm text-muted-foreground">Access your NeuroFab workspace.</p>
        </div>

        {justRegistered && (
          <p className="mt-4 flex items-start gap-2 rounded-lg border border-ok/25 bg-ok-soft p-3 text-sm text-ok">
            <CheckCircle2 className="mt-0.5 size-4 shrink-0" aria-hidden />
            Account created. Sign in to continue.
          </p>
        )}

        <form
          className="mt-5 space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
          noValidate
        >
          <div className="space-y-1.5">
            <label htmlFor="email" className="block text-sm font-medium">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              autoFocus
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@company.com"
              aria-invalid={Boolean(error)}
              className="h-10 w-full rounded-lg border bg-background px-3 text-sm outline-none transition-colors focus-visible:border-ring"
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="password" className="block text-sm font-medium">
              Password
            </label>
            <div className="relative">
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                required
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                aria-invalid={Boolean(error)}
                className="h-10 w-full rounded-lg border bg-background px-3 pr-10 text-sm outline-none transition-colors focus-visible:border-ring"
              />
              <button
                type="button"
                onClick={() => setShowPassword((visible) => !visible)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1.5 text-muted-foreground transition-colors hover:text-foreground"
              >
                {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
              </button>
            </div>
          </div>

          {error && <InlineError message={error} />}

          <Button type="submit" size="lg" className="w-full" disabled={isPending}>
            {isPending && <Loader2 className="size-4 animate-spin" />}
            {isPending ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      </div>

      <p className="mt-4 text-center text-sm text-muted-foreground">
        No account?{" "}
        <Link
          href={`/register?redirect=${encodeURIComponent(redirectTo)}`}
          className="font-medium text-primary hover:underline"
        >
          Create one
        </Link>
      </p>
    </div>
  );
}
