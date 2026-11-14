"use client";

/**
 * Application shell: sidebar, mobile drawer, and top bar.
 *
 * The previous shell was a fixed `w-64` sidebar with no mobile handling at all,
 * so the app was unusable below roughly 900px. Here the sidebar is a drawer
 * under `lg`, a persistent rail above it, and the top bar carries the page
 * title, search, theme toggle and account menu.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  FileText,
  LayoutDashboard,
  LogOut,
  Menu,
  Network,
  Search,
  Settings,
  Sparkles,
  User as UserIcon,
  X,
} from "lucide-react";
import { useEffect, useRef, useState, type ComponentType } from "react";

import { CommandPalette } from "@/components/command-palette";
import { useResetOnChange } from "@/hooks/use-reset-on-change";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { WorkspaceSwitcher } from "@/components/layout/workspace-switcher";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { cn } from "@/lib/utils";

interface NavItem {
  name: string;
  href: string;
  icon: ComponentType<{ className?: string }>;
  description: string;
}

const NAVIGATION: NavItem[] = [
  {
    name: "Overview",
    href: "/dashboard",
    icon: LayoutDashboard,
    description: "Workspace health and recent activity",
  },
  {
    name: "Copilot",
    href: "/copilot",
    icon: Sparkles,
    description: "Ask questions about your documents",
  },
  {
    name: "Documents",
    href: "/hub",
    icon: FileText,
    description: "Upload and manage source documents",
  },
  {
    name: "Knowledge graph",
    href: "/graph",
    icon: Network,
    description: "Explore extracted entities and relationships",
  },
  {
    name: "Analytics",
    href: "/analytics",
    icon: BarChart3,
    description: "Ingestion and extraction metrics",
  },
];

export function pageTitle(pathname: string): string {
  if (pathname.startsWith("/settings")) return "Settings";
  return NAVIGATION.find((item) => pathname.startsWith(item.href))?.name ?? "Overview";
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [isPaletteOpen, setIsPaletteOpen] = useState(false);

  // Close the drawer on navigation; leaving it open over the new page is
  // disorienting on mobile.
  useResetOnChange(pathname, () => setIsDrawerOpen(false));

  // Lock body scroll behind the drawer so the page underneath does not move.
  useEffect(() => {
    if (!isDrawerOpen) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [isDrawerOpen]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setIsPaletteOpen(true);
      }
      if (event.key === "Escape") setIsDrawerOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <div className="flex min-h-dvh bg-surface">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[200] focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground"
      >
        Skip to content
      </a>

      {/* Persistent sidebar (large screens) */}
      <aside className="hidden w-64 shrink-0 flex-col border-r bg-sidebar lg:flex">
        <SidebarContent pathname={pathname} />
      </aside>

      {/* Drawer (small screens) */}
      {isDrawerOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-foreground/40 backdrop-blur-[2px] animate-in fade-in-0"
            onClick={() => setIsDrawerOpen(false)}
            aria-hidden
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Navigation"
            className="absolute inset-y-0 left-0 flex w-[17rem] max-w-[85vw] flex-col border-r bg-sidebar shadow-md animate-in slide-in-from-left"
          >
            <div className="flex items-center justify-between px-4 pt-4">
              <Brand />
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={() => setIsDrawerOpen(false)}
                aria-label="Close navigation"
              >
                <X className="size-4" />
              </Button>
            </div>
            <SidebarContent pathname={pathname} hideBrand />
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-2 border-b bg-background/85 px-3 backdrop-blur-md sm:px-5">
          <Button
            variant="ghost"
            size="icon-sm"
            className="lg:hidden"
            onClick={() => setIsDrawerOpen(true)}
            aria-label="Open navigation"
          >
            <Menu className="size-4.5" />
          </Button>

          <h1 className="truncate text-sm font-semibold sm:text-base">{pageTitle(pathname)}</h1>

          <div className="ml-auto flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => setIsPaletteOpen(true)}
              className="hidden items-center gap-2 rounded-lg border bg-card px-2.5 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-accent md:flex"
            >
              <Search className="size-3.5" aria-hidden />
              <span>Search…</span>
              <kbd className="ml-3 rounded border bg-muted px-1.5 py-0.5 font-mono text-[10px] font-medium">
                ⌘K
              </kbd>
            </button>
            <Button
              variant="ghost"
              size="icon-sm"
              className="md:hidden"
              onClick={() => setIsPaletteOpen(true)}
              aria-label="Search"
            >
              <Search className="size-4" />
            </Button>

            <ThemeToggle />
            <AccountMenu />
          </div>
        </header>

        <main id="main-content" className="min-w-0 flex-1">
          {children}
        </main>
      </div>

      <CommandPalette open={isPaletteOpen} onOpenChange={setIsPaletteOpen} navigation={NAVIGATION} />
    </div>
  );
}

function Brand() {
  return (
    <Link href="/dashboard" className="flex items-center gap-2.5 rounded-md">
      <span
        className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground"
        aria-hidden
      >
        <Network className="size-4.5" />
      </span>
      <span className="text-[15px] font-semibold tracking-tight">NeuroFab AI</span>
    </Link>
  );
}

function SidebarContent({ pathname, hideBrand }: { pathname: string; hideBrand?: boolean }) {
  return (
    <>
      {!hideBrand && (
        <div className="px-4 pt-5">
          <Brand />
        </div>
      )}

      <div className="px-3 pt-4">
        <WorkspaceSwitcher />
      </div>

      <nav aria-label="Main" className="flex-1 space-y-0.5 overflow-y-auto scrollbar-thin p-3">
        {NAVIGATION.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={isActive ? "page" : undefined}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground",
              )}
            >
              <item.icon className="size-4.5 shrink-0" aria-hidden />
              {item.name}
            </Link>
          );
        })}
      </nav>

      <div className="border-t p-3">
        <Link
          href="/settings"
          aria-current={pathname.startsWith("/settings") ? "page" : undefined}
          className={cn(
            "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
            pathname.startsWith("/settings")
              ? "bg-sidebar-accent text-sidebar-accent-foreground"
              : "text-muted-foreground hover:bg-accent hover:text-foreground",
          )}
        >
          <Settings className="size-4.5 shrink-0" aria-hidden />
          Settings
        </Link>
      </div>
    </>
  );
}

function AccountMenu() {
  const { user, signOut } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setIsOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setIsOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [isOpen]);

  const initials = (user?.full_name ?? user?.email ?? "?")
    .split(/[\s@.]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        aria-haspopup="menu"
        aria-expanded={isOpen}
        aria-label="Account menu"
        className="flex size-8 items-center justify-center rounded-full bg-primary/12 text-xs font-semibold text-primary transition-colors hover:bg-primary/20"
      >
        {initials || <UserIcon className="size-4" />}
      </button>

      {isOpen && (
        <div
          role="menu"
          className="absolute right-0 top-full z-50 mt-1.5 w-60 overflow-hidden rounded-lg border bg-popover shadow-md"
        >
          <div className="border-b px-3 py-2.5">
            <p className="truncate text-sm font-medium">{user?.full_name ?? "Signed in"}</p>
            <p className="truncate text-xs text-muted-foreground">{user?.email}</p>
          </div>
          <div className="p-1">
            <Link
              href="/settings"
              role="menuitem"
              onClick={() => setIsOpen(false)}
              className="flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors hover:bg-accent"
            >
              <Settings className="size-4" aria-hidden />
              Settings
            </Link>
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setIsOpen(false);
                void signOut();
              }}
              className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-sm text-danger transition-colors hover:bg-danger-soft"
            >
              <LogOut className="size-4" aria-hidden />
              Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
