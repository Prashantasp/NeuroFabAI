"use client";

/**
 * Documents.
 *
 * Fixes carried over from the audit: statuses now compare against the real
 * enum values (the previous page compared `'Ready'` to a backend that emits
 * `'READY'`, so nothing ever showed as complete), progress and failure reasons
 * are actually present in the API response, pagination reflects a real total,
 * and delete/reprocess use a proper dialog and toasts rather than `confirm()`.
 */

import {
  AlertTriangle,
  Download,
  FileText,
  Loader2,
  RefreshCw,
  Search,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { useCallback, useRef, useState } from "react";

import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState, TableSkeleton } from "@/components/ui/states";
import {
  DocumentStatusPill,
  ProgressBar,
  StageStatusPill,
  documentStatusLabel,
  isTerminalStatus,
} from "@/components/ui/status";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/contexts/AuthContext";
import { useAction, useAsync, useDebounced } from "@/hooks/use-async";
import { api, errorMessage, type Document } from "@/lib/api";
import { formatBytes, formatDuration, formatRelativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 15;
const MAX_UPLOAD_MB = 50;

export default function DocumentsPage() {
  const { activeWorkspace, refreshWorkspaces } = useAuth();
  const toast = useToast();
  const workspaceId = activeWorkspace?.id;

  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [pendingDelete, setPendingDelete] = useState<Document | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const debouncedSearch = useDebounced(search, 300);

  const documents = useAsync(
    (signal) =>
      api.listDocuments({
        page,
        page_size: PAGE_SIZE,
        search: debouncedSearch || undefined,
        signal,
      }),
    [workspaceId, page, debouncedSearch],
    { enabled: Boolean(workspaceId) },
  );

  const items = documents.data?.items ?? [];
  const anyProcessing = items.some((doc) => !isTerminalStatus(doc.status));

  // Refresh on a short interval only while the pipeline is running.
  useAsync(
    async (signal) => {
      const result = await api.listDocuments({
        page,
        page_size: PAGE_SIZE,
        search: debouncedSearch || undefined,
        signal,
      });
      documents.mutate(() => result);
      return result;
    },
    [workspaceId, page, debouncedSearch, anyProcessing],
    { enabled: Boolean(workspaceId) && anyProcessing, refreshInterval: 2500 },
  );

  const { run: upload, isPending: isUploading } = useAction(async (file: File) => {
    const toastId = toast.loading(`Uploading ${file.name}…`);
    try {
      await api.uploadDocument(file, file.name);
      toast.update(toastId, "success", "Upload complete", {
        description: "Processing has started. Progress updates below.",
      });
      setPage(1);
      await documents.reload();
      await refreshWorkspaces();
    } catch (error) {
      toast.update(toastId, "error", "Upload failed", { description: errorMessage(error) });
    }
  });

  const handleFileChange = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      // Reset immediately so re-picking the same file still fires a change event.
      event.target.value = "";
      if (!file) return;

      // Client-side pre-checks give instant feedback; the server validates again.
      if (!file.name.toLowerCase().endsWith(".pdf")) {
        toast.error("Only PDF files are supported", {
          description: `"${file.name}" is not a PDF.`,
        });
        return;
      }
      if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
        toast.error("File is too large", {
          description: `The limit is ${MAX_UPLOAD_MB} MB; this file is ${formatBytes(file.size)}.`,
        });
        return;
      }
      await upload(file);
    },
    [toast, upload],
  );

  const handleDelete = async () => {
    if (!pendingDelete) return;
    const target = pendingDelete;
    setPendingDelete(null);
    setBusyId(target.id);
    try {
      await api.deleteDocument(target.id);
      toast.success(`"${target.title}" deleted`, {
        description: "Its text index and graph entities were removed too.",
      });
      await documents.reload();
      await refreshWorkspaces();
    } catch (error) {
      toast.error("Could not delete the document", { description: errorMessage(error) });
    } finally {
      setBusyId(null);
    }
  };

  const handleReprocess = async (doc: Document) => {
    setBusyId(doc.id);
    try {
      await api.reprocessDocument(doc.id);
      toast.success(`Reprocessing "${doc.title}"`);
      await documents.reload();
    } catch (error) {
      toast.error("Could not reprocess", { description: errorMessage(error) });
    } finally {
      setBusyId(null);
    }
  };

  const handleDownload = async (doc: Document) => {
    try {
      await api.downloadDocument(doc.id, doc.filename);
    } catch (error) {
      toast.error("Download failed", { description: errorMessage(error) });
    }
  };

  const total = documents.data?.total_items ?? 0;
  const canWrite = activeWorkspace?.role !== "VIEWER";

  return (
    <div className="mx-auto w-full max-w-[1400px] space-y-5 p-4 sm:p-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-1">
          <h2 className="text-xl font-semibold tracking-tight sm:text-2xl">Documents</h2>
          <p className="text-sm text-muted-foreground">
            PDFs are parsed, indexed for search, and turned into knowledge-graph entities.
          </p>
        </div>

        {canWrite && (
          <div className="flex shrink-0 items-center gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf,.pdf"
              onChange={handleFileChange}
              className="sr-only"
              aria-label="Choose a PDF to upload"
            />
            <Button onClick={() => fileInputRef.current?.click()} disabled={isUploading}>
              {isUploading ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Upload className="size-4" />
              )}
              {isUploading ? "Uploading…" : "Upload PDF"}
            </Button>
          </div>
        )}
      </header>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <div className="relative flex-1 sm:max-w-xs">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <input
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            placeholder="Search by title or filename"
            aria-label="Search documents"
            className="h-9 w-full rounded-lg border bg-card pl-9 pr-9 text-sm outline-none transition-colors focus-visible:border-ring"
          />
          {search && (
            <button
              type="button"
              onClick={() => setSearch("")}
              aria-label="Clear search"
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-muted-foreground hover:text-foreground"
            >
              <X className="size-3.5" />
            </button>
          )}
        </div>

        <div className="flex items-center gap-2 sm:ml-auto">
          {total > 0 && (
            <span className="tabular text-sm text-muted-foreground">
              {total} {total === 1 ? "document" : "documents"}
            </span>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={documents.refresh}
            disabled={documents.isRefreshing}
            aria-label="Refresh list"
          >
            <RefreshCw className={cn("size-3.5", documents.isRefreshing && "animate-spin")} />
            Refresh
          </Button>
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border bg-card">
        {documents.error && !documents.data ? (
          <ErrorState message={documents.error} onRetry={documents.reload} className="m-4" />
        ) : (
          <>
            {/* Table on desktop */}
            <div className="hidden overflow-x-auto md:block">
              <table className="w-full text-sm">
                <caption className="sr-only">
                  Documents in {activeWorkspace?.name ?? "this workspace"}
                </caption>
                <thead>
                  <tr className="border-b bg-muted/40 text-left text-xs text-muted-foreground">
                    <th scope="col" className="px-4 py-2.5 font-medium">Document</th>
                    <th scope="col" className="px-4 py-2.5 font-medium">Status</th>
                    <th scope="col" className="px-4 py-2.5 font-medium">Search index</th>
                    <th scope="col" className="px-4 py-2.5 font-medium">Graph</th>
                    <th scope="col" className="px-4 py-2.5 font-medium">Uploaded</th>
                    <th scope="col" className="px-4 py-2.5 text-right font-medium">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {documents.isLoading ? (
                    <TableSkeleton rows={5} columns={6} />
                  ) : items.length === 0 ? (
                    <tr>
                      <td colSpan={6}>
                        <EmptyStateForList search={debouncedSearch} canWrite={canWrite} onUpload={() => fileInputRef.current?.click()} />
                      </td>
                    </tr>
                  ) : (
                    items.map((doc) => (
                      <tr key={doc.id} className="border-b last:border-0 hover:bg-accent/30">
                        <td className="max-w-xs px-4 py-3">
                          <div className="flex items-start gap-2.5">
                            <FileText className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
                            <div className="min-w-0">
                              <p className="truncate font-medium">{doc.title}</p>
                              <p className="truncate text-xs text-muted-foreground">
                                {formatBytes(doc.file_size)}
                                {doc.page_count ? ` · ${doc.page_count}pp` : ""}
                                {doc.chunk_count ? ` · ${doc.chunk_count} chunks` : ""}
                              </p>
                            </div>
                          </div>
                        </td>

                        <td className="px-4 py-3">
                          <div className="space-y-1.5">
                            <DocumentStatusPill status={doc.status} />
                            {!isTerminalStatus(doc.status) && (
                              <ProgressBar
                                value={doc.progress_percentage}
                                label={`${doc.title}: ${documentStatusLabel(doc.status)}`}
                                className="max-w-32"
                              />
                            )}
                            {doc.failure_reason && (
                              <p
                                className="flex max-w-52 items-start gap-1 text-xs text-danger"
                                title={doc.failure_reason}
                              >
                                <AlertTriangle className="mt-0.5 size-3 shrink-0" aria-hidden />
                                <span className="line-clamp-2">{doc.failure_reason}</span>
                              </p>
                            )}
                          </div>
                        </td>

                        <td className="px-4 py-3">
                          <StageStatusPill status={doc.embedding_status} />
                        </td>
                        <td className="px-4 py-3">
                          <div className="space-y-1">
                            <StageStatusPill status={doc.graph_status} />
                            {doc.entity_count > 0 && (
                              <p className="tabular text-xs text-muted-foreground">
                                {doc.entity_count} entities · {doc.relationship_count} links
                              </p>
                            )}
                          </div>
                        </td>

                        <td className="px-4 py-3 text-xs text-muted-foreground">
                          <p>{formatRelativeTime(doc.uploaded_at)}</p>
                          {doc.processing_duration && (
                            <p>in {formatDuration(doc.processing_duration)}</p>
                          )}
                        </td>

                        <td className="px-4 py-3">
                          <RowActions
                            document={doc}
                            busy={busyId === doc.id}
                            canWrite={canWrite}
                            onDownload={() => handleDownload(doc)}
                            onReprocess={() => handleReprocess(doc)}
                            onDelete={() => setPendingDelete(doc)}
                          />
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Cards on mobile: a horizontally scrolling table is unusable on a phone */}
            <div className="md:hidden">
              {documents.isLoading ? (
                <div className="space-y-3 p-4">
                  {Array.from({ length: 4 }).map((_, index) => (
                    <div key={index} className="h-28 animate-pulse rounded-lg bg-muted" />
                  ))}
                </div>
              ) : items.length === 0 ? (
                <EmptyStateForList
                  search={debouncedSearch}
                  canWrite={canWrite}
                  onUpload={() => fileInputRef.current?.click()}
                />
              ) : (
                <ul className="divide-y">
                  {items.map((doc) => (
                    <li key={doc.id} className="space-y-2.5 p-4">
                      <div className="flex items-start gap-2.5">
                        <FileText className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium">{doc.title}</p>
                          <p className="truncate text-xs text-muted-foreground">
                            {formatBytes(doc.file_size)} · {formatRelativeTime(doc.uploaded_at)}
                          </p>
                        </div>
                      </div>

                      <div className="flex flex-wrap items-center gap-1.5">
                        <DocumentStatusPill status={doc.status} />
                        <StageStatusPill status={doc.embedding_status} />
                        <StageStatusPill status={doc.graph_status} />
                      </div>

                      {!isTerminalStatus(doc.status) && (
                        <ProgressBar
                          value={doc.progress_percentage}
                          label={`${doc.title}: ${documentStatusLabel(doc.status)}`}
                        />
                      )}
                      {doc.failure_reason && (
                        <p className="flex items-start gap-1 text-xs text-danger">
                          <AlertTriangle className="mt-0.5 size-3 shrink-0" aria-hidden />
                          <span>{doc.failure_reason}</span>
                        </p>
                      )}

                      <RowActions
                        document={doc}
                        busy={busyId === doc.id}
                        canWrite={canWrite}
                        onDownload={() => handleDownload(doc)}
                        onReprocess={() => handleReprocess(doc)}
                        onDelete={() => setPendingDelete(doc)}
                      />
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </>
        )}
      </div>

      {documents.data && documents.data.total_pages > 1 && (
        <nav
          aria-label="Pagination"
          className="flex items-center justify-between gap-3 text-sm"
        >
          <p className="text-muted-foreground">
            Page {documents.data.page} of {documents.data.total_pages}
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={!documents.data.has_previous}
              onClick={() => setPage((current) => Math.max(1, current - 1))}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={!documents.data.has_next}
              onClick={() => setPage((current) => current + 1)}
            >
              Next
            </Button>
          </div>
        </nav>
      )}

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title="Delete this document?"
        description={
          pendingDelete
            ? `"${pendingDelete.title}" and everything derived from it — indexed text and graph entities — will be permanently removed. This cannot be undone.`
            : ""
        }
        confirmLabel="Delete"
        destructive
        onConfirm={handleDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}

function EmptyStateForList({
  search,
  canWrite,
  onUpload,
}: {
  search: string;
  canWrite: boolean;
  onUpload: () => void;
}) {
  if (search) {
    return (
      <EmptyState
        icon={Search}
        title={`No documents match "${search}"`}
        description="Try a different search term, or clear the search to see everything."
      />
    );
  }
  return (
    <EmptyState
      icon={FileText}
      title="No documents yet"
      description="Upload a PDF manual, SOP, or maintenance report to start building this workspace's knowledge graph."
      action={
        canWrite ? (
          <Button onClick={onUpload}>
            <Upload className="size-4" />
            Upload a PDF
          </Button>
        ) : undefined
      }
    />
  );
}

function RowActions({
  document,
  busy,
  canWrite,
  onDownload,
  onReprocess,
  onDelete,
}: {
  document: Document;
  busy: boolean;
  canWrite: boolean;
  onDownload: () => void;
  onReprocess: () => void;
  onDelete: () => void;
}) {
  const canReprocess = document.status === "FAILED" || document.status === "READY";

  return (
    <div className="flex items-center justify-end gap-1">
      {busy && <Loader2 className="size-4 animate-spin text-muted-foreground" aria-hidden />}

      <Button
        variant="ghost"
        size="icon-sm"
        onClick={onDownload}
        aria-label={`Download ${document.title}`}
        title="Download original"
      >
        <Download className="size-4" />
      </Button>

      {canWrite && canReprocess && (
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={onReprocess}
          disabled={busy}
          aria-label={`Reprocess ${document.title}`}
          title="Run the pipeline again"
        >
          <RefreshCw className="size-4" />
        </Button>
      )}

      {canWrite && (
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={onDelete}
          disabled={busy}
          aria-label={`Delete ${document.title}`}
          title="Delete"
          className="text-muted-foreground hover:bg-danger-soft hover:text-danger"
        >
          <Trash2 className="size-4" />
        </Button>
      )}
    </div>
  );
}
