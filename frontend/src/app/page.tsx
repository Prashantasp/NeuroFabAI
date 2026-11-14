"use client";

/**
 * Landing page.
 *
 * Trimmed to what is actually true about the product. The previous version
 * advertised "100% Audit", "LangGraph Coordination" and a five-stage pipeline
 * diagram, some of which did not match the implementation.
 */

import Link from "next/link";
import {
  ArrowRight,
  FileText,
  Loader2,
  MessagesSquare,
  Network,
  Quote,
  ShieldCheck,
} from "lucide-react";

import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";

const STEPS = [
  {
    icon: FileText,
    title: "Upload your PDFs",
    body: "Manuals, SOPs, inspection reports. Text is extracted, split into passages, and indexed for semantic search.",
  },
  {
    icon: Network,
    title: "Get a knowledge graph",
    body: "Equipment, components, failure modes and the relationships between them are extracted and linked back to the page they came from.",
  },
  {
    icon: MessagesSquare,
    title: "Ask questions",
    body: "The Copilot retrieves relevant passages and graph paths, then answers from that evidence — with the sources attached.",
  },
];

export default function LandingPage() {
  const { isAuthenticated, isLoading, user } = useAuth();

  return (
    <div className="flex min-h-dvh flex-col bg-surface">
      <header className="sticky top-0 z-30 border-b bg-background/85 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Link href="/" className="flex items-center gap-2.5">
            <span
              className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground"
              aria-hidden
            >
              <Network className="size-4.5" />
            </span>
            <span className="text-[15px] font-semibold tracking-tight">NeuroFab AI</span>
          </Link>

          <div className="flex items-center gap-2">
            <ThemeToggle />
            {isLoading ? (
              <Loader2 className="size-4 animate-spin text-muted-foreground" aria-label="Loading" />
            ) : isAuthenticated ? (
              <Button render={<Link href="/dashboard" />} size="sm">
                  Open workspace
                  <ArrowRight className="size-3.5" />
            </Button>
            ) : (
              <>
                <Button render={<Link href="/login" />} variant="ghost" size="sm">Sign in
            </Button>
                <Button render={<Link href="/register" />} size="sm">Get started
            </Button>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="flex-1">
        <section className="mx-auto max-w-3xl px-4 py-16 text-center sm:px-6 sm:py-24">
          <h1 className="text-3xl font-semibold tracking-tight text-balance sm:text-5xl">
            Ask your industrial documents a question.
            <span className="block text-muted-foreground">Get an answer that cites them.</span>
          </h1>

          <p className="mx-auto mt-5 max-w-xl text-base text-muted-foreground text-pretty sm:text-lg">
            NeuroFab turns manuals, SOPs and maintenance reports into a searchable knowledge
            graph, then answers operational questions from what your documents actually say.
          </p>

          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Button render={<Link href={isAuthenticated ? "/dashboard" : "/register"} />} size="lg">
                {isAuthenticated ? `Continue as ${user?.full_name ?? "you"}` : "Create an account"}
                <ArrowRight className="size-4" />
            </Button>
            {!isAuthenticated && (
              <Button render={<Link href="/login" />} size="lg" variant="outline">Sign in
            </Button>
            )}
          </div>
        </section>

        <section className="border-y bg-background">
          <div className="mx-auto grid max-w-5xl gap-8 px-4 py-14 sm:px-6 md:grid-cols-3">
            {STEPS.map((step, index) => (
              <div key={step.title} className="space-y-2.5">
                <div className="flex items-center gap-2.5">
                  <span
                    className="flex size-9 items-center justify-center rounded-lg bg-primary/12 text-primary"
                    aria-hidden
                  >
                    <step.icon className="size-4.5" />
                  </span>
                  <span className="text-xs font-medium tabular text-muted-foreground">
                    Step {index + 1}
                  </span>
                </div>
                <h2 className="text-base font-semibold">{step.title}</h2>
                <p className="text-sm leading-relaxed text-muted-foreground">{step.body}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-5xl px-4 py-14 sm:px-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <Feature
              icon={Quote}
              title="Grounded, not guessed"
              body="Answers are built only from retrieved passages and graph relationships. When the documents do not support an answer, the Copilot says so and lowers its confidence rather than inventing one."
            />
            <Feature
              icon={ShieldCheck}
              title="Isolated per workspace"
              body="Documents, indexed passages and graph entities are scoped to a workspace, and every request is authorised server-side against your membership."
            />
          </div>
        </section>
      </main>

      <footer className="border-t bg-background">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 px-4 py-6 text-sm text-muted-foreground sm:flex-row sm:px-6">
          <p>NeuroFab AI</p>
          <div className="flex gap-4">
            <Link href="/login" className="hover:text-foreground">
              Sign in
            </Link>
            <Link href="/register" className="hover:text-foreground">
              Create account
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}

function Feature({
  icon: Icon,
  title,
  body,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  body: string;
}) {
  return (
    <div className="rounded-xl border bg-card p-5">
      <span
        className="flex size-9 items-center justify-center rounded-lg bg-primary/12 text-primary"
        aria-hidden
      >
        <Icon className="size-4.5" />
      </span>
      <h2 className="mt-3 text-base font-semibold">{title}</h2>
      <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{body}</p>
    </div>
  );
}
