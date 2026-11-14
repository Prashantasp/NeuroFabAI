"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { useAuth } from "@/contexts/AuthContext";

/**
 * Authenticated area.
 *
 * This is the authoritative client-side gate. `proxy.ts` can short-circuit the
 * redirect when it can see the session cookie, but the real enforcement is here
 * and — crucially — on the API, which authorises every request independently.
 */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isLoading || isAuthenticated) return;
    const { pathname, search } = window.location;
    router.replace(`/login?redirect=${encodeURIComponent(pathname + search)}`);
  }, [isAuthenticated, isLoading, router]);

  if (isLoading) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-surface">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <Loader2 className="size-6 animate-spin" aria-hidden />
          <p className="text-sm">Restoring your session…</p>
        </div>
      </div>
    );
  }

  // Render nothing rather than the shell while the redirect is in flight, so
  // protected content never flashes on screen.
  if (!isAuthenticated) return null;

  return <AppShell>{children}</AppShell>;
}
