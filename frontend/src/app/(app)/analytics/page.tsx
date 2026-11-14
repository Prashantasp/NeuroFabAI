"use client";

/**
 * Analytics.
 *
 * Only measured values appear here. The previous page displayed
 * "Vector Embeddings = readyDocs × 12", a number invented in the component, and
 * a hardcoded "Total Available Agents: 4" tile. Both are gone.
 */

import { BarChart3, Clock, Database, FileText, HardDrive } from "lucide-react";
import { useMemo } from "react";

import { CardSkeleton, EmptyState, ErrorState } from "@/components/ui/states";
import { ProgressBar, entityColor } from "@/components/ui/status";
import { useAuth } from "@/contexts/AuthContext";
import { useAsync } from "@/hooks/use-async";
import { api } from "@/lib/api";
import { formatBytes, formatDuration, formatNumber } from "@/lib/format";

export default function AnalyticsPage() {
  const { activeWorkspace } = useAuth();
  const workspaceId = activeWorkspace?.id;

  const stats = useAsync((signal) => api.documentStats(signal), [workspaceId], {
    enabled: Boolean(workspaceId),
  });
  const graph = useAsync((signal) => api.graphStats(signal), [workspaceId], {
    enabled: Boolean(workspaceId),
  });

  const entityBreakdown = useMemo(
    () =>
      Object.entries(graph.data?.entity_type_counts ?? {}).sort(([, a], [, b]) => b - a),
    [graph.data],
  );

  const relationshipBreakdown = useMemo(
    () =>
      Object.entries(graph.data?.relationship_type_counts ?? {})
        .sort(([, a], [, b]) => b - a)
        .slice(0, 10),
    [graph.data],
  );

  const isLoading = stats.isLoading || graph.isLoading;
  const error = stats.error ?? graph.error;
  const isEmpty = !isLoading && !error && (stats.data?.total ?? 0) === 0;

  return (
    <div className="mx-auto w-full max-w-[1400px] space-y-6 p-4 sm:p-6">
      <header className="space-y-1">
        <h2 className="text-xl font-semibold tracking-tight sm:text-2xl">Analytics</h2>
        <p className="text-sm text-muted-foreground">
          Ingestion throughput and knowledge-extraction coverage for {activeWorkspace?.name}.
        </p>
      </header>

      {error ? (
        <ErrorState
          message={error}
          onRetry={() => {
            void stats.reload();
            void graph.reload();
          }}
        />
      ) : isEmpty ? (
        <div className="rounded-xl border bg-card">
          <EmptyState
            icon={BarChart3}
            title="Nothing to measure yet"
            description="Metrics appear once documents have been uploaded and processed."
          />
        </div>
      ) : (
        <>
          <section aria-label="Summary" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {isLoading ? (
              Array.from({ length: 4 }).map((_, index) => <CardSkeleton key={index} />)
            ) : (
              <>
                <Metric
                  icon={FileText}
                  label="Documents processed"
                  value={formatNumber(stats.data?.ready ?? 0)}
                  detail={`${stats.data?.total ?? 0} total${
                    stats.data?.failed ? ` · ${stats.data.failed} failed` : ""
                  }`}
                />
                <Metric
                  icon={Database}
                  label="Indexed chunks"
                  value={formatNumber(stats.data?.total_chunks ?? 0)}
                  detail="Searchable passages"
                />
                <Metric
                  icon={Clock}
                  label="Average ingest time"
                  value={formatDuration(stats.data?.avg_processing_seconds)}
                  detail="Per document, end to end"
                />
                <Metric
                  icon={HardDrive}
                  label="Stored"
                  value={formatBytes(stats.data?.total_bytes ?? 0)}
                  detail="Original source files"
                />
              </>
            )}
          </section>

          <div className="grid gap-4 lg:grid-cols-2">
            <Panel
              title="Entities by type"
              subtitle={`${formatNumber(graph.data?.total_nodes ?? 0)} total`}
              isLoading={isLoading}
              isEmpty={entityBreakdown.length === 0}
              emptyMessage="No entities extracted yet."
            >
              <ul className="space-y-3">
                {entityBreakdown.map(([type, count]) => {
                  const total = graph.data?.total_nodes || 1;
                  return (
                    <li key={type} className="space-y-1.5">
                      <div className="flex items-center justify-between gap-2 text-sm">
                        <span className="flex min-w-0 items-center gap-2">
                          <span
                            className="size-2.5 shrink-0 rounded-full"
                            style={{ backgroundColor: entityColor(type) }}
                            aria-hidden
                          />
                          <span className="truncate">{type}</span>
                        </span>
                        <span className="tabular shrink-0 text-muted-foreground">
                          {count} · {Math.round((count / total) * 100)}%
                        </span>
                      </div>
                      <ProgressBar
                        value={(count / total) * 100}
                        label={`${type}: ${count} of ${total}`}
                      />
                    </li>
                  );
                })}
              </ul>
            </Panel>

            <Panel
              title="Relationship types"
              subtitle={`${formatNumber(graph.data?.total_relationships ?? 0)} total`}
              isLoading={isLoading}
              isEmpty={relationshipBreakdown.length === 0}
              emptyMessage="No relationships extracted yet."
            >
              <ul className="space-y-2">
                {relationshipBreakdown.map(([type, count]) => (
                  <li key={type} className="flex items-center justify-between gap-3 text-sm">
                    <code className="truncate rounded bg-muted px-1.5 py-0.5 font-mono text-xs">
                      {type}
                    </code>
                    <span className="tabular shrink-0 text-muted-foreground">{count}</span>
                  </li>
                ))}
              </ul>
            </Panel>
          </div>

          <Panel
            title="Pipeline status"
            subtitle="Where documents currently sit"
            isLoading={isLoading}
            isEmpty={Object.keys(stats.data?.by_status ?? {}).length === 0}
            emptyMessage="No documents yet."
          >
            <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {Object.entries(stats.data?.by_status ?? {}).map(([status, count]) => (
                <li
                  key={status}
                  className="flex items-center justify-between gap-3 rounded-lg border px-3 py-2 text-sm"
                >
                  <span className="truncate">{status.replaceAll("_", " ").toLowerCase()}</span>
                  <span className="tabular font-medium">{count}</span>
                </li>
              ))}
            </ul>
          </Panel>
        </>
      )}
    </div>
  );
}

function Metric({
  icon: Icon,
  label,
  value,
  detail,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="rounded-xl border bg-card p-4">
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">{label}</span>
        <Icon className="size-4 text-muted-foreground" aria-hidden />
      </div>
      <p className="mt-2 text-2xl font-semibold tabular">{value}</p>
      <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
    </div>
  );
}

function Panel({
  title,
  subtitle,
  isLoading,
  isEmpty,
  emptyMessage,
  children,
}: {
  title: string;
  subtitle?: string;
  isLoading: boolean;
  isEmpty: boolean;
  emptyMessage: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border bg-card">
      <div className="flex items-baseline justify-between border-b px-4 py-3">
        <h3 className="text-sm font-semibold">{title}</h3>
        {subtitle && <span className="text-xs text-muted-foreground">{subtitle}</span>}
      </div>
      <div className="p-4">
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="h-6 animate-pulse rounded bg-muted" />
            ))}
          </div>
        ) : isEmpty ? (
          <p className="py-4 text-center text-sm text-muted-foreground">{emptyMessage}</p>
        ) : (
          children
        )}
      </div>
    </section>
  );
}
