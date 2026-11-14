"use client";

/**
 * Workspace overview.
 *
 * Rebuilt around signals that are actually measured. The previous version had
 * three permanently-green "Online" cards, an "Active Agents: 4" tile, and a
 * "FAISS In-Memory Mode" label for a system that uses Qdrant. Everything here
 * comes from a real endpoint, and anything that cannot be measured is not shown.
 */

import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  FileText,
  GitBranch,
  Network,
  Sparkles,
  Upload,
} from "lucide-react";
import { useMemo } from "react";

import { Button } from "@/components/ui/button";
import { CardSkeleton, EmptyState, ErrorState } from "@/components/ui/states";
import {
  DocumentStatusPill,
  ProgressBar,
  documentStatusLabel,
  entityColor,
  isTerminalStatus,
} from "@/components/ui/status";
import { useAuth } from "@/contexts/AuthContext";
import { useAsync } from "@/hooks/use-async";
import { api, type Document } from "@/lib/api";
import { formatBytes, formatRelativeTime } from "@/lib/format";

export default function DashboardPage() {
  const { activeWorkspace } = useAuth();
  const workspaceId = activeWorkspace?.id;

  const documents = useAsync(
    (signal) => api.listDocuments({ page_size: 8, signal }),
    [workspaceId],
    { enabled: Boolean(workspaceId) },
  );

  const stats = useAsync((signal) => api.documentStats(signal), [workspaceId], {
    enabled: Boolean(workspaceId),
  });

  const graph = useAsync((signal) => api.graphStats(signal), [workspaceId], {
    enabled: Boolean(workspaceId),
  });

  const items = documents.data?.items ?? [];
  const hasProcessing = items.some((doc) => !isTerminalStatus(doc.status));

  // Poll only while something is actually moving through the pipeline.
  const live = useAsync(
    (signal) => api.listDocuments({ page_size: 8, signal }),
    [workspaceId, hasProcessing],
    { enabled: Boolean(workspaceId) && hasProcessing, refreshInterval: 3000 },
  );
  const visibleDocuments = live.data?.items ?? items;

  const isEmpty =
    !documents.isLoading && !documents.error && (stats.data?.total ?? 0) === 0;

  const topEntityTypes = useMemo(() => {
    const counts = graph.data?.entity_type_counts ?? {};
    return Object.entries(counts)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 5);
  }, [graph.data]);

  if (!activeWorkspace) {
    return (
      <div className="p-4 sm:p-6">
        <EmptyState
          icon={Network}
          title="No workspace selected"
          description="Choose a workspace from the switcher, or create one to get started."
        />
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-[1400px] space-y-6 p-4 sm:p-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-1">
          <h2 className="text-xl font-semibold tracking-tight sm:text-2xl">
            {activeWorkspace.name}
          </h2>
          <p className="text-sm text-muted-foreground">
            {isEmpty
              ? "Upload a document to build this workspace's knowledge graph."
              : "Ingestion status and knowledge coverage for this workspace."}
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button render={<Link href="/hub" />} variant="outline">
              <Upload className="size-4" />
              Upload
            </Button>
          <Button render={<Link href="/copilot" />}>
              <Sparkles className="size-4" />
              Ask Copilot
            </Button>
        </div>
      </header>

      {isEmpty ? (
        <div className="rounded-xl border bg-card">
          <EmptyState
            icon={FileText}
            title="This workspace is empty"
            description="Upload a PDF manual, SOP, or maintenance report. NeuroFab extracts the text, indexes it for search, and builds a knowledge graph you can question."
            action={
              <Button render={<Link href="/hub" />}>
                  <Upload className="size-4" />
                  Upload your first document
            </Button>
            }
          />
        </div>
      ) : (
        <>
          <section aria-label="Key metrics" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {stats.isLoading || graph.isLoading ? (
              Array.from({ length: 4 }).map((_, index) => <CardSkeleton key={index} />)
            ) : (
              <>
                <MetricCard
                  label="Documents"
                  value={stats.data?.total ?? 0}
                  detail={
                    stats.data
                      ? `${stats.data.ready} ready · ${stats.data.processing} processing${
                          stats.data.failed ? ` · ${stats.data.failed} failed` : ""
                        }`
                      : undefined
                  }
                  icon={FileText}
                  href="/hub"
                />
                <MetricCard
                  label="Entities"
                  value={graph.data?.total_nodes ?? 0}
                  detail="Extracted from your documents"
                  icon={Network}
                  href="/graph"
                />
                <MetricCard
                  label="Relationships"
                  value={graph.data?.total_relationships ?? 0}
                  detail="Links between entities"
                  icon={GitBranch}
                  href="/graph"
                />
                <MetricCard
                  label="Searchable chunks"
                  value={stats.data?.total_chunks ?? 0}
                  detail={
                    stats.data?.avg_processing_seconds
                      ? `${stats.data.avg_processing_seconds}s average ingest`
                      : "Indexed passages"
                  }
                  icon={Sparkles}
                />
              </>
            )}
          </section>

          <div className="grid gap-4 lg:grid-cols-5">
            <section
              aria-label="Recent documents"
              className="rounded-xl border bg-card lg:col-span-3"
            >
              <div className="flex items-center justify-between border-b px-4 py-3">
                <h3 className="text-sm font-semibold">Recent documents</h3>
                <Link
                  href="/hub"
                  className="flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                >
                  View all
                  <ArrowRight className="size-3" aria-hidden />
                </Link>
              </div>

              {documents.isLoading ? (
                <div className="space-y-3 p-4">
                  {Array.from({ length: 4 }).map((_, index) => (
                    <div key={index} className="h-12 animate-pulse rounded-lg bg-muted" />
                  ))}
                </div>
              ) : documents.error ? (
                <ErrorState compact message={documents.error} onRetry={documents.reload} className="m-4" />
              ) : visibleDocuments.length === 0 ? (
                <EmptyState compact icon={FileText} title="No documents yet" />
              ) : (
                <ul className="divide-y">
                  {visibleDocuments.map((doc) => (
                    <DocumentRow key={doc.id} document={doc} />
                  ))}
                </ul>
              )}
            </section>

            <section
              aria-label="Knowledge coverage"
              className="rounded-xl border bg-card lg:col-span-2"
            >
              <div className="border-b px-4 py-3">
                <h3 className="text-sm font-semibold">Knowledge coverage</h3>
              </div>

              <div className="p-4">
                {graph.isLoading ? (
                  <div className="space-y-3">
                    {Array.from({ length: 4 }).map((_, index) => (
                      <div key={index} className="h-6 animate-pulse rounded bg-muted" />
                    ))}
                  </div>
                ) : topEntityTypes.length === 0 ? (
                  <EmptyState
                    compact
                    icon={Network}
                    title="No entities extracted yet"
                    description="Entities appear once a document finishes processing."
                  />
                ) : (
                  <ul className="space-y-3">
                    {topEntityTypes.map(([type, count]) => {
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
                            <span className="tabular text-muted-foreground">{count}</span>
                          </div>
                          <ProgressBar
                            value={(count / total) * 100}
                            label={`${type}: ${count} of ${total} entities`}
                          />
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
            </section>
          </div>
        </>
      )}
    </div>
  );
}

function MetricCard({
  label,
  value,
  detail,
  icon: Icon,
  href,
}: {
  label: string;
  value: number;
  detail?: string;
  icon: React.ComponentType<{ className?: string }>;
  href?: string;
}) {
  const content = (
    <>
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">{label}</span>
        <Icon className="size-4 text-muted-foreground" aria-hidden />
      </div>
      <p className="mt-2 text-2xl font-semibold tabular">{value.toLocaleString()}</p>
      {detail && <p className="mt-1 text-xs text-muted-foreground">{detail}</p>}
    </>
  );

  const className =
    "block rounded-xl border bg-card p-4 transition-colors" +
    (href ? " hover:border-primary/40 hover:bg-accent/40" : "");

  return href ? (
    <Link href={href} className={className}>
      {content}
    </Link>
  ) : (
    <div className={className}>{content}</div>
  );
}

function DocumentRow({ document }: { document: Document }) {
  const inProgress = !isTerminalStatus(document.status);

  return (
    <li className="flex items-center gap-3 px-4 py-3">
      <FileText className="size-4 shrink-0 text-muted-foreground" aria-hidden />

      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{document.title}</p>
        <p className="truncate text-xs text-muted-foreground">
          {formatBytes(document.file_size)} · {formatRelativeTime(document.uploaded_at)}
        </p>
        {inProgress && (
          <div className="mt-1.5 flex items-center gap-2">
            <ProgressBar
              value={document.progress_percentage}
              label={`${document.title}: ${documentStatusLabel(document.status)}`}
              className="max-w-40"
            />
            <span className="tabular text-[11px] text-muted-foreground">
              {document.progress_percentage}%
            </span>
          </div>
        )}
        {document.status === "FAILED" && document.failure_reason && (
          <p className="mt-1 flex items-start gap-1 text-xs text-danger">
            <AlertTriangle className="mt-0.5 size-3 shrink-0" aria-hidden />
            <span className="line-clamp-2">{document.failure_reason}</span>
          </p>
        )}
      </div>

      <DocumentStatusPill status={document.status} />
    </li>
  );
}
