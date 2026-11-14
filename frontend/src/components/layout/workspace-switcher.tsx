"use client";

import { Check, ChevronsUpDown, FolderPlus, Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { InlineError } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/contexts/AuthContext";
import { useAction } from "@/hooks/use-async";
import { api, errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";

export function WorkspaceSwitcher({ onNavigate }: { onNavigate?: () => void }) {
  const { workspaces, activeWorkspace, selectWorkspace, refreshWorkspaces } = useAuth();
  const toast = useToast();

  const [isOpen, setIsOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const close = () => {
    setIsOpen(false);
    setIsCreating(false);
    setError(null);
  };

  // Close on outside click and on Escape, with focus returned to the trigger.
  useEffect(() => {
    if (!isOpen) return;

    const onPointerDown = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) close();
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        close();
        triggerRef.current?.focus();
      }
    };

    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [isOpen]);

  const { run: create, isPending } = useAction(async (workspaceName: string) => {
    const created = await api.createWorkspace({ name: workspaceName });
    await refreshWorkspaces();
    selectWorkspace(created.id);
    toast.success(`Workspace "${created.name}" created`);
    close();
    setName("");
  });

  const handleCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) {
      setError("Enter a name for the workspace.");
      return;
    }
    setError(null);
    try {
      await create(trimmed);
    } catch (err) {
      setError(errorMessage(err, "Could not create the workspace."));
    }
  };

  return (
    <div ref={containerRef} className="relative">
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        className="flex w-full items-center justify-between gap-2 rounded-lg border bg-card px-3 py-2 text-left text-sm transition-colors hover:bg-accent"
      >
        <span className="flex min-w-0 items-center gap-2.5">
          <span
            className="flex size-6 shrink-0 items-center justify-center rounded-md bg-primary/12 text-[11px] font-semibold text-primary"
            aria-hidden
          >
            {(activeWorkspace?.name ?? "W").charAt(0).toUpperCase()}
          </span>
          <span className="min-w-0">
            <span className="block truncate font-medium">
              {activeWorkspace?.name ?? "Select workspace"}
            </span>
            {activeWorkspace && (
              <span className="block truncate text-xs text-muted-foreground">
                {activeWorkspace.document_count}{" "}
                {activeWorkspace.document_count === 1 ? "document" : "documents"}
              </span>
            )}
          </span>
        </span>
        <ChevronsUpDown className="size-4 shrink-0 text-muted-foreground" aria-hidden />
      </button>

      {isOpen && (
        <div
          role="listbox"
          aria-label="Workspaces"
          className="absolute left-0 right-0 top-full z-50 mt-1.5 overflow-hidden rounded-lg border bg-popover shadow-md"
        >
          <div className="max-h-56 overflow-y-auto scrollbar-thin p-1">
            {workspaces.map((workspace) => {
              const isActive = workspace.id === activeWorkspace?.id;
              return (
                <button
                  key={workspace.id}
                  type="button"
                  role="option"
                  aria-selected={isActive}
                  onClick={() => {
                    selectWorkspace(workspace.id);
                    close();
                    onNavigate?.();
                  }}
                  className={cn(
                    "flex w-full items-center justify-between gap-2 rounded-md px-2.5 py-2 text-left text-sm transition-colors hover:bg-accent",
                    isActive && "bg-accent font-medium",
                  )}
                >
                  <span className="min-w-0">
                    <span className="block truncate">{workspace.name}</span>
                    <span className="block truncate text-xs text-muted-foreground">
                      {workspace.role?.toLowerCase()} · {workspace.member_count}{" "}
                      {workspace.member_count === 1 ? "member" : "members"}
                    </span>
                  </span>
                  {isActive && <Check className="size-4 shrink-0 text-primary" aria-hidden />}
                </button>
              );
            })}
          </div>

          <div className="border-t p-1">
            {isCreating ? (
              <form onSubmit={handleCreate} className="space-y-2 p-1.5">
                <label htmlFor="new-workspace-name" className="text-xs font-medium">
                  Workspace name
                </label>
                <input
                  id="new-workspace-name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="e.g. Plant Alpha"
                  autoFocus
                  maxLength={120}
                  className="w-full rounded-md border bg-background px-2.5 py-1.5 text-sm outline-none focus-visible:border-ring"
                />
                {error && <InlineError message={error} className="text-xs" />}
                <div className="flex justify-end gap-1.5">
                  <Button type="button" variant="ghost" size="sm" onClick={() => setIsCreating(false)}>
                    Cancel
                  </Button>
                  <Button type="submit" size="sm" disabled={isPending || !name.trim()}>
                    {isPending && <Loader2 className="size-3.5 animate-spin" />}
                    Create
                  </Button>
                </div>
              </form>
            ) : (
              <button
                type="button"
                onClick={() => setIsCreating(true)}
                className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-sm text-primary transition-colors hover:bg-accent"
              >
                <FolderPlus className="size-4" aria-hidden />
                New workspace
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
