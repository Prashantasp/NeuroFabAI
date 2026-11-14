"use client";

/**
 * Command palette (⌘K).
 *
 * The previous header rendered a non-interactive div styled to look like a
 * search box with a "⌘K" badge that did nothing. This runs a real hybrid search
 * against the active workspace and also navigates.
 */

import { useRouter } from "next/navigation";
import { FileText, Loader2, Network, Search, Sparkles, CornerDownLeft } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ComponentType } from "react";

import { EmptyState } from "@/components/ui/states";
import { useAsync, useDebounced } from "@/hooks/use-async";
import { useResetOnChange } from "@/hooks/use-reset-on-change";
import { api, type SearchResult } from "@/lib/api";
import { cn } from "@/lib/utils";

interface NavItem {
  name: string;
  href: string;
  icon: ComponentType<{ className?: string }>;
  description: string;
}

interface Command {
  id: string;
  label: string;
  hint: string;
  icon: ComponentType<{ className?: string }>;
  run: () => void;
}

export function CommandPalette({
  open,
  onOpenChange,
  navigation,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  navigation: NavItem[];
}) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [highlight, setHighlight] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const debouncedQuery = useDebounced(query.trim(), 250);
  const shouldSearch = open && debouncedQuery.length >= 2;

  const { data: results, isLoading } = useAsync<SearchResult[]>(
    (signal) => api.search({ query: debouncedQuery, strategy: "hybrid", limit: 8, signal }),
    [debouncedQuery],
    { enabled: shouldSearch },
  );

  // Reset during render rather than in an effect, so the previous query is
  // never briefly visible when the palette reopens.
  useResetOnChange(open, () => {
    setQuery("");
    setHighlight(0);
  });

  useEffect(() => {
    if (!open) return;
    // Focus after paint so the browser does not scroll the page behind.
    const frame = requestAnimationFrame(() => inputRef.current?.focus());
    return () => cancelAnimationFrame(frame);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [open]);

  const commands = useMemo<Command[]>(() => {
    const navCommands: Command[] = navigation.map((item) => ({
      id: `nav:${item.href}`,
      label: item.name,
      hint: item.description,
      icon: item.icon,
      run: () => router.push(item.href),
    }));

    const searchCommands: Command[] = (results ?? []).map((result) => ({
      id: `result:${result.source}:${result.id}`,
      label: result.title,
      hint: result.snippet || `${result.source} match`,
      icon: result.source === "graph" ? Network : FileText,
      run: () => {
        if (result.source === "graph") {
          router.push(`/graph?focus=${encodeURIComponent(result.id)}`);
        } else if (result.document_id) {
          router.push(`/hub?document=${encodeURIComponent(result.document_id)}`);
        } else {
          router.push("/hub");
        }
      },
    }));

    const askCommand: Command[] = debouncedQuery
      ? [
          {
            id: "ask",
            label: `Ask the Copilot: "${debouncedQuery}"`,
            hint: "Run a full GraphRAG analysis",
            icon: Sparkles,
            run: () => router.push(`/copilot?q=${encodeURIComponent(debouncedQuery)}`),
          },
        ]
      : [];

    if (!query.trim()) return navCommands;

    const lowered = query.trim().toLowerCase();
    const filteredNav = navCommands.filter((command) =>
      command.label.toLowerCase().includes(lowered),
    );
    return [...askCommand, ...searchCommands, ...filteredNav];
  }, [navigation, results, query, debouncedQuery, router]);

  useResetOnChange(commands.length, () => setHighlight(0));

  // Keep the highlighted row scrolled into view during keyboard navigation.
  useEffect(() => {
    listRef.current
      ?.querySelector<HTMLElement>(`[data-index="${highlight}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [highlight]);

  if (!open) return null;

  const select = (command: Command) => {
    onOpenChange(false);
    command.run();
  };

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Escape") {
      onOpenChange(false);
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlight((index) => (commands.length ? (index + 1) % commands.length : 0));
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlight((index) => (commands.length ? (index - 1 + commands.length) % commands.length : 0));
    }
    if (event.key === "Enter" && commands[highlight]) {
      event.preventDefault();
      select(commands[highlight]);
    }
  };

  return (
    <div className="fixed inset-0 z-[90] flex items-start justify-center p-4 pt-[10vh] sm:pt-[14vh]">
      <div
        className="absolute inset-0 bg-foreground/40 backdrop-blur-[2px] animate-in fade-in-0"
        onClick={() => onOpenChange(false)}
        aria-hidden
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-label="Search and commands"
        onKeyDown={onKeyDown}
        className="relative flex w-full max-w-xl flex-col overflow-hidden rounded-xl border bg-popover shadow-md animate-in fade-in-0 zoom-in-95"
      >
        <div className="flex items-center gap-2.5 border-b px-3.5">
          {isLoading ? (
            <Loader2 className="size-4 shrink-0 animate-spin text-muted-foreground" aria-hidden />
          ) : (
            <Search className="size-4 shrink-0 text-muted-foreground" aria-hidden />
          )}
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search documents and entities, or jump to a page…"
            aria-label="Search"
            role="combobox"
            aria-expanded
            aria-controls="command-results"
            className="h-12 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
          <kbd className="hidden rounded border bg-muted px-1.5 py-0.5 font-mono text-[10px] sm:block">
            Esc
          </kbd>
        </div>

        <div
          id="command-results"
          ref={listRef}
          role="listbox"
          className="max-h-[min(24rem,55vh)] overflow-y-auto scrollbar-thin p-1.5"
        >
          {commands.length === 0 ? (
            <EmptyState
              compact
              icon={Search}
              title={isLoading ? "Searching…" : "No matches"}
              description={
                isLoading
                  ? undefined
                  : "Try a different term, or press Enter to ask the Copilot instead."
              }
            />
          ) : (
            commands.map((command, index) => (
              <button
                key={command.id}
                type="button"
                role="option"
                data-index={index}
                aria-selected={index === highlight}
                onMouseEnter={() => setHighlight(index)}
                onClick={() => select(command)}
                className={cn(
                  "flex w-full items-start gap-3 rounded-lg px-2.5 py-2.5 text-left transition-colors",
                  index === highlight ? "bg-accent" : "hover:bg-accent/60",
                )}
              >
                <command.icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{command.label}</span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {command.hint}
                  </span>
                </span>
                {index === highlight && (
                  <CornerDownLeft className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" aria-hidden />
                )}
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
