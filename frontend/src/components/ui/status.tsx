"use client";

/**
 * Status presentation shared by every screen.
 *
 * Colour alone never conveys meaning here: each status carries an icon and a
 * text label, so the UI works for colour-blind users and in monochrome.
 */

import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  CircleSlash,
  Loader2,
  XCircle,
} from "lucide-react";
import type { ComponentType } from "react";

import type { DocumentStatus, RiskLevel, StageStatus } from "@/lib/api";
import { cn } from "@/lib/utils";

type Tone = "ok" | "warn" | "danger" | "info" | "neutral" | "progress";

const TONE_CLASSES: Record<Tone, string> = {
  ok: "bg-ok-soft text-ok border-ok/25",
  warn: "bg-warn-soft text-warn border-warn/25",
  danger: "bg-danger-soft text-danger border-danger/25",
  info: "bg-info-soft text-info border-info/25",
  progress: "bg-info-soft text-info border-info/25",
  neutral: "bg-muted text-muted-foreground border-border",
};

const TONE_ICONS: Record<Tone, ComponentType<{ className?: string }>> = {
  ok: CheckCircle2,
  warn: AlertTriangle,
  danger: XCircle,
  info: CircleDashed,
  progress: Loader2,
  neutral: CircleSlash,
};

/** Human-readable labels for the pipeline stages. */
const DOCUMENT_STATUS_META: Record<DocumentStatus, { label: string; tone: Tone }> = {
  UPLOADING: { label: "Uploading", tone: "progress" },
  QUEUED: { label: "Queued", tone: "info" },
  VALIDATING: { label: "Validating", tone: "progress" },
  TEXT_EXTRACTION: { label: "Extracting text", tone: "progress" },
  CHUNKING: { label: "Chunking", tone: "progress" },
  EMBEDDING: { label: "Embedding", tone: "progress" },
  VECTOR_INDEXING: { label: "Indexing", tone: "progress" },
  KNOWLEDGE_GRAPH: { label: "Building graph", tone: "progress" },
  READY: { label: "Ready", tone: "ok" },
  FAILED: { label: "Failed", tone: "danger" },
  ARCHIVED: { label: "Archived", tone: "neutral" },
};

const STAGE_STATUS_META: Record<StageStatus, { label: string; tone: Tone }> = {
  PENDING: { label: "Pending", tone: "neutral" },
  RUNNING: { label: "Running", tone: "progress" },
  COMPLETED: { label: "Complete", tone: "ok" },
  FAILED: { label: "Failed", tone: "danger" },
  SKIPPED: { label: "Skipped", tone: "neutral" },
};

const RISK_META: Record<RiskLevel, { tone: Tone }> = {
  Low: { tone: "ok" },
  Medium: { tone: "warn" },
  High: { tone: "danger" },
  Critical: { tone: "danger" },
};

export function isTerminalStatus(status: DocumentStatus): boolean {
  return status === "READY" || status === "FAILED" || status === "ARCHIVED";
}

interface StatusPillProps {
  label: string;
  tone: Tone;
  className?: string;
  size?: "sm" | "md";
}

export function StatusPill({ label, tone, className, size = "md" }: StatusPillProps) {
  const Icon = TONE_ICONS[tone];
  return (
    <span
      className={cn(
        "inline-flex w-fit items-center gap-1.5 rounded-full border font-medium whitespace-nowrap",
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-xs",
        TONE_CLASSES[tone],
        className,
      )}
    >
      <Icon className={cn("size-3.5 shrink-0", tone === "progress" && "animate-spin")} aria-hidden />
      {label}
    </span>
  );
}

export function DocumentStatusPill({
  status,
  className,
}: {
  status: DocumentStatus;
  className?: string;
}) {
  const meta = DOCUMENT_STATUS_META[status] ?? { label: status, tone: "neutral" as Tone };
  return <StatusPill label={meta.label} tone={meta.tone} className={className} />;
}

export function StageStatusPill({ status }: { status: StageStatus }) {
  const meta = STAGE_STATUS_META[status] ?? { label: status, tone: "neutral" as Tone };
  return <StatusPill label={meta.label} tone={meta.tone} size="sm" />;
}

export function RiskPill({ risk }: { risk: RiskLevel }) {
  return <StatusPill label={`${risk} risk`} tone={RISK_META[risk]?.tone ?? "neutral"} />;
}

export function documentStatusLabel(status: DocumentStatus): string {
  return DOCUMENT_STATUS_META[status]?.label ?? status;
}

/** A small, accessible determinate progress bar. */
export function ProgressBar({
  value,
  label,
  className,
}: {
  value: number;
  label?: string;
  className?: string;
}) {
  const clamped = Math.max(0, Math.min(100, Math.round(value)));
  return (
    <div
      role="progressbar"
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label ?? "Progress"}
      className={cn("h-1.5 w-full overflow-hidden rounded-full bg-muted", className)}
    >
      <div
        className="h-full rounded-full bg-primary transition-[width] duration-500 ease-out"
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}

/** Colour for a knowledge-graph entity type, resolved from design tokens. */
export function entityColor(type: string | undefined): string {
  switch ((type ?? "").toLowerCase()) {
    case "equipment":
    case "asset":
    case "machine":
      return "var(--entity-equipment)";
    case "component":
    case "part":
      return "var(--entity-component)";
    case "failuremode":
    case "failure_mode":
    case "failure":
    case "incident":
      return "var(--entity-failure)";
    case "process":
    case "procedure":
      return "var(--entity-process)";
    default:
      return "var(--entity-document)";
  }
}
