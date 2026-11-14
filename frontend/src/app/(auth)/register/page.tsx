"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Check, Eye, EyeOff, Loader2, X } from "lucide-react";
import { Suspense, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { InlineError } from "@/components/ui/states";
import { useAction } from "@/hooks/use-async";
import { ApiError, api, errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Mirrors the server-side policy so the user sees requirements as they type. */
const RULES = [
  { id: "length", label: "At least 10 characters", test: (v: string) => v.length >= 10 },
  { id: "lower", label: "A lowercase letter", test: (v: string) => /[a-z]/.test(v) },
  { id: "upper", label: "An uppercase letter", test: (v: string) => /[A-Z]/.test(v) },
  { id: "digit", label: "A number", test: (v: string) => /\d/.test(v) },
];

function safeRedirect(value: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return "/dashboard";
  return value;
}

export default function RegisterPage() {
  return (
    <Suspense fallback={<Loader2 className="size-5 animate-spin text-muted-foreground" />}>
      <RegisterForm />
    </Suspense>
  );
}

function RegisterForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectTo = safeRedirect(searchParams.get("redirect"));

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [company, setCompany] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [touchedPassword, setTouchedPassword] = useState(false);

  const ruleResults = useMemo(
    () => RULES.map((rule) => ({ ...rule, passed: rule.test(password) })),
    [password],
  );
  const passwordValid = ruleResults.every((rule) => rule.passed);
  const passwordsMatch = password.length > 0 && password === confirm;

  const { run: submit, isPending } = useAction(async () => {
    setError(null);
    if (!passwordValid) {
      setTouchedPassword(true);
      setError("Please meet all the password requirements.");
      return;
    }
    if (!passwordsMatch) {
      setError("The passwords do not match.");
      return;
    }

    try {
      await api.register({
        email: email.trim(),
        password,
        full_name: fullName.trim() || undefined,
        company: company.trim() || undefined,
      });
      router.replace(
        `/login?registered=1&redirect=${encodeURIComponent(redirectTo)}`,
      );
    } catch (err) {
      setError(
        err instanceof ApiError && err.fieldErrors.length > 0
          ? err.fieldErrors[0].message
          : errorMessage(err, "Could not create your account."),
      );
    }
  });

  return (
    <div className="w-full max-w-sm">
      <div className="rounded-xl border bg-card p-6 shadow-sm">
        <div className="space-y-1 text-center">
          <h1 className="text-lg font-semibold tracking-tight">Create an account</h1>
          <p className="text-sm text-muted-foreground">
            You get a personal workspace to start with.
          </p>
        </div>

        <form
          className="mt-5 space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
          noValidate
        >
          <div className="space-y-1.5">
            <label htmlFor="full-name" className="block text-sm font-medium">
              Full name
            </label>
            <input
              id="full-name"
              autoComplete="name"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              placeholder="Alex Morgan"
              className="h-10 w-full rounded-lg border bg-background px-3 text-sm outline-none transition-colors focus-visible:border-ring"
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="email" className="block text-sm font-medium">
              Work email
            </label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@company.com"
              className="h-10 w-full rounded-lg border bg-background px-3 text-sm outline-none transition-colors focus-visible:border-ring"
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="company" className="block text-sm font-medium">
              Company <span className="font-normal text-muted-foreground">(optional)</span>
            </label>
            <input
              id="company"
              autoComplete="organization"
              value={company}
              onChange={(event) => setCompany(event.target.value)}
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
                autoComplete="new-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                onBlur={() => setTouchedPassword(true)}
                aria-describedby="password-rules"
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

            {(touchedPassword || password.length > 0) && (
              <ul id="password-rules" className="space-y-1 pt-1">
                {ruleResults.map((rule) => (
                  <li
                    key={rule.id}
                    className={cn(
                      "flex items-center gap-1.5 text-xs",
                      rule.passed ? "text-ok" : "text-muted-foreground",
                    )}
                  >
                    {rule.passed ? (
                      <Check className="size-3.5 shrink-0" aria-hidden />
                    ) : (
                      <X className="size-3.5 shrink-0" aria-hidden />
                    )}
                    {rule.label}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="space-y-1.5">
            <label htmlFor="confirm" className="block text-sm font-medium">
              Confirm password
            </label>
            <input
              id="confirm"
              type={showPassword ? "text" : "password"}
              required
              autoComplete="new-password"
              value={confirm}
              onChange={(event) => setConfirm(event.target.value)}
              aria-invalid={confirm.length > 0 && !passwordsMatch}
              className="h-10 w-full rounded-lg border bg-background px-3 text-sm outline-none transition-colors focus-visible:border-ring"
            />
            {confirm.length > 0 && !passwordsMatch && (
              <p className="text-xs text-danger">The passwords do not match.</p>
            )}
          </div>

          {error && <InlineError message={error} />}

          <Button
            type="submit"
            size="lg"
            className="w-full"
            disabled={isPending || !email.trim() || !passwordValid || !passwordsMatch}
          >
            {isPending && <Loader2 className="size-4 animate-spin" />}
            {isPending ? "Creating account…" : "Create account"}
          </Button>
        </form>
      </div>

      <p className="mt-4 text-center text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link
          href={`/login?redirect=${encodeURIComponent(redirectTo)}`}
          className="font-medium text-primary hover:underline"
        >
          Sign in
        </Link>
      </p>
    </div>
  );
}
