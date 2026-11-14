import Link from "next/link";
import { Network } from "lucide-react";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col bg-surface">
      <header className="p-5">
        <Link href="/" className="inline-flex items-center gap-2.5">
          <span
            className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground"
            aria-hidden
          >
            <Network className="size-4.5" />
          </span>
          <span className="text-[15px] font-semibold tracking-tight">NeuroFab AI</span>
        </Link>
      </header>

      <main className="flex flex-1 items-center justify-center px-4 pb-16">{children}</main>

      <footer className="p-5 text-center text-xs text-muted-foreground">
        Industrial GraphRAG for documents you already have.
      </footer>
    </div>
  );
}
