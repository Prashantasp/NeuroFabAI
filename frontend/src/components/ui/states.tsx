"use client";

/**
 * Shared empty / loading / error presentation.
 *
 * Every async surface in the app routes through these so the four states look
 * the same everywhere and none of them is a blank screen or a bare "Error".
 */

import { AlertCircle, RefreshCw } from "lucide-react";
import type { ComponentType, ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon?: ComponentType<{ className?: string }>;
  title: string;
  /** Say what the user can do next, not just that there is nothing here. */
  description?: string;
  action?: ReactNode;
  className?: string;
  compact?: boolean;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
  compact = false,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center text-center",
        compact ? "gap-2 px-4 py-8" : "gap-3 px-6 py-14",
        className,
      )}
    >
      {Icon && (
        <div
          className={cn(
            "flex items-center justify-center rounded-full bg-muted text-muted-foreground",
            compact ? "size-9" : "size-12",
          )}
          aria-hidden
        >
          <Icon className={compact ? "size-4" : "size-5"} />
        </div>
      )}
      <div className="space-y-1">
        <p className={cn("font-medium", compact ? "text-sm" : "text-base")}>{title}</p>
        {description && (
          <p className="mx-auto max-w-sm text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      {action && <div className="pt-1">{action}</div>}
    </div>
  );
}

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  className?: string;
  compact?: boolean;
}

export function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
  className,
  compact = false,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-lg border border-danger/25 bg-danger-soft text-center",
        compact ? "px-4 py-6" : "px-6 py-12",
        className,
      )}
    >
      <AlertCircle className="size-5 text-danger" aria-hidden />
      <div className="space-y-1">
        <p className="text-sm font-medium">{title}</p>
        <p className="mx-auto max-w-md text-sm text-muted-foreground">{message}</p>
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw className="size-3.5" />
          Try again
        </Button>
      )}
    </div>
  );
}

/** Inline error for a form field or a small region. */
export function InlineError({ message, className }: { message: string; className?: string }) {
  return (
    <p
      role="alert"
      className={cn("flex items-start gap-1.5 text-sm text-danger", className)}
    >
      <AlertCircle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
      <span>{message}</span>
    </p>
  );
}

/** Skeleton rows for a table body. */
export function TableSkeleton({ rows = 5, columns = 4 }: { rows?: number; columns?: number }) {
  return (
    <>
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <tr key={rowIndex} className="border-b border-border last:border-0">
          {Array.from({ length: columns }).map((__, columnIndex) => (
            <td key={columnIndex} className="px-4 py-3.5">
              <Skeleton className={cn("h-4", columnIndex === 0 ? "w-48" : "w-20")} />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}

export function CardSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("space-y-3 rounded-lg border bg-card p-5", className)}>
      <Skeleton className="h-3.5 w-24" />
      <Skeleton className="h-7 w-16" />
      <Skeleton className="h-3 w-32" />
    </div>
  );
}

/** Screen-reader-only announcement for async results. */
export function LiveAnnouncer({ message }: { message: string }) {
  return (
    <span aria-live="polite" className="sr-only">
      {message}
    </span>
  );
}
