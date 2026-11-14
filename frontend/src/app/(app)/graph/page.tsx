"use client";

/**
 * Knowledge graph explorer.
 *
 * The canvas is client-only (it measures the DOM and draws to a 2D context), so
 * it is dynamically imported with SSR disabled and given an explicit measured
 * size rather than relying on the library's window-sized default, which
 * overflowed the app shell.
 */

import dynamic from "next/dynamic";
import { useSearchParams } from "next/navigation";
import { Loader2, Maximize2, Network, Search, X } from "lucide-react";
import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { entityColor } from "@/components/ui/status";
import { useAuth } from "@/contexts/AuthContext";
import { useAsync } from "@/hooks/use-async";
import { api, type GraphEdge, type GraphNode } from "@/lib/api";
import { cn } from "@/lib/utils";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center text-muted-foreground">
      <Loader2 className="size-5 animate-spin" aria-hidden />
    </div>
  ),
});

interface CanvasNode extends GraphNode {
  x?: number;
  y?: number;
  val: number;
}

export default function GraphPage() {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Loading…</div>}>
      <GraphExplorer />
    </Suspense>
  );
}

function GraphExplorer() {
  const { activeWorkspace } = useAuth();
  const searchParams = useSearchParams();
  const workspaceId = activeWorkspace?.id;

  const [selected, setSelected] = useState<CanvasNode | null>(null);
  const [filter, setFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState<string | null>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<{ zoomToFit?: (ms?: number, px?: number) => void } | null>(null);

  const topology = useAsync((signal) => api.graphTopology(signal), [workspaceId], {
    enabled: Boolean(workspaceId),
  });

  // The canvas needs pixel dimensions; observe the container instead of using
  // window size so it fits inside the shell at every breakpoint.
  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;

    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setSize({ width: Math.floor(width), height: Math.floor(height) });
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const entityTypes = useMemo(() => {
    const counts = new Map<string, number>();
    for (const node of topology.data?.nodes ?? []) {
      counts.set(node.type, (counts.get(node.type) ?? 0) + 1);
    }
    return [...counts.entries()].sort(([, a], [, b]) => b - a);
  }, [topology.data]);

  const graphData = useMemo(() => {
    const allNodes = topology.data?.nodes ?? [];
    const allEdges = topology.data?.edges ?? [];

    const term = filter.trim().toLowerCase();
    const visible = allNodes.filter((node) => {
      if (typeFilter && node.type !== typeFilter) return false;
      if (term && !node.canonical_name.toLowerCase().includes(term)) return false;
      return true;
    });

    const visibleIds = new Set(visible.map((node) => node.id));
    return {
      nodes: visible.map<CanvasNode>((node) => ({
        ...node,
        // Confidence drives node size, so weakly-supported entities read as less
        // prominent without needing a legend.
        val: 4 + node.confidence * 6,
      })),
      links: allEdges.filter(
        (edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target),
      ),
    };
  }, [topology.data, filter, typeFilter]);

  // Deep link from the command palette: /graph?focus=<entity>.
  // Derived rather than set in an effect, so the panel is correct on first
  // paint instead of appearing a frame later.
  const focusParam = searchParams.get("focus");
  const [dismissedFocus, setDismissedFocus] = useState(false);
  const focusedNode = useMemo(() => {
    if (!focusParam || dismissedFocus) return null;
    const match = topology.data?.nodes.find((node) => node.id === focusParam);
    return match ? { ...match, val: 8 } : null;
  }, [focusParam, dismissedFocus, topology.data]);

  const activeNode = selected ?? focusedNode;

  const activeNodeRef = useRef<CanvasNode | null>(null);
  useEffect(() => {
    activeNodeRef.current = activeNode;
  });

  const drawNode = useCallback(
    (node: CanvasNode, ctx: CanvasRenderingContext2D, scale: number) => {
      const radius = node.val;
      const isSelected = activeNodeRef.current?.id === node.id;

      ctx.beginPath();
      ctx.arc(node.x ?? 0, node.y ?? 0, radius, 0, 2 * Math.PI);
      ctx.fillStyle = entityColor(node.type);
      ctx.fill();

      if (isSelected) {
        ctx.strokeStyle = entityColor(node.type);
        ctx.lineWidth = 2 / scale;
        ctx.beginPath();
        ctx.arc(node.x ?? 0, node.y ?? 0, radius + 4, 0, 2 * Math.PI);
        ctx.stroke();
      }

      // Labels only once zoomed in far enough to be legible; drawing every
      // label at low zoom is unreadable and slow.
      if (scale > 1.2 || isSelected) {
        const fontSize = Math.max(10 / scale, 2.5);
        ctx.font = `${fontSize}px var(--font-sans), sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "top";
        ctx.fillStyle = getComputedStyle(document.documentElement)
          .getPropertyValue("--foreground")
          .trim() || "#111";
        ctx.fillText(node.canonical_name, node.x ?? 0, (node.y ?? 0) + radius + 2);
      }
    },
    [],
  );

  if (!activeWorkspace) {
    return (
      <div className="p-6">
        <EmptyState icon={Network} title="No workspace selected" />
      </div>
    );
  }

  const isEmpty =
    !topology.isLoading && !topology.error && (topology.data?.nodes.length ?? 0) === 0;

  return (
    <div className="flex h-[calc(100dvh-3.5rem)] flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b px-4 py-2.5">
        <div className="relative w-full sm:w-56">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <input
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            placeholder="Filter entities"
            aria-label="Filter entities by name"
            className="h-8 w-full rounded-lg border bg-card pl-8 pr-8 text-sm outline-none focus-visible:border-ring"
          />
          {filter && (
            <button
              type="button"
              onClick={() => setFilter("")}
              aria-label="Clear filter"
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="size-3.5" />
            </button>
          )}
        </div>

        <div className="flex flex-1 flex-wrap items-center gap-1.5">
          {entityTypes.map(([type, count]) => (
            <button
              key={type}
              type="button"
              aria-pressed={typeFilter === type}
              onClick={() => setTypeFilter((current) => (current === type ? null : type))}
              className={cn(
                "flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs transition-colors",
                typeFilter === type ? "border-primary bg-accent" : "hover:bg-accent",
              )}
            >
              <span
                className="size-2 rounded-full"
                style={{ backgroundColor: entityColor(type) }}
                aria-hidden
              />
              {type}
              <span className="tabular text-muted-foreground">{count}</span>
            </button>
          ))}
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={() => graphRef.current?.zoomToFit?.(400, 60)}
          disabled={graphData.nodes.length === 0}
        >
          <Maximize2 className="size-3.5" />
          Fit
        </Button>
      </div>

      {topology.data?.truncated && (
        <p className="border-b bg-warn-soft px-4 py-2 text-xs text-warn">
          Showing the first {topology.data.nodes.length} of {topology.data.total_nodes} entities.
          Filter by type or name to narrow the view.
        </p>
      )}

      <div className="relative flex min-h-0 flex-1">
        <div ref={containerRef} className="relative min-w-0 flex-1 bg-surface">
          {topology.isLoading ? (
            <div className="flex h-full items-center justify-center text-muted-foreground">
              <Loader2 className="size-5 animate-spin" aria-hidden />
            </div>
          ) : topology.error ? (
            <ErrorState message={topology.error} onRetry={topology.reload} className="m-6" />
          ) : isEmpty ? (
            <EmptyState
              icon={Network}
              title="No entities extracted yet"
              description="Upload and process a document; extracted equipment, components and failure modes appear here."
            />
          ) : graphData.nodes.length === 0 ? (
            <EmptyState
              icon={Search}
              title="No entities match this filter"
              description="Clear the filter or pick a different entity type."
            />
          ) : (
            size.width > 0 && (
              <ForceGraph2D
                ref={graphRef as never}
                width={size.width}
                height={size.height}
                graphData={graphData as never}
                nodeCanvasObject={drawNode as never}
                nodePointerAreaPaint={((node: CanvasNode, color: string, ctx: CanvasRenderingContext2D) => {
                  ctx.fillStyle = color;
                  ctx.beginPath();
                  ctx.arc(node.x ?? 0, node.y ?? 0, node.val + 4, 0, 2 * Math.PI);
                  ctx.fill();
                }) as never}
                onNodeClick={((node: CanvasNode) => setSelected(node)) as never}
                onBackgroundClick={() => setSelected(null)}
                linkColor={() => "rgba(128,128,128,0.35)"}
                linkDirectionalArrowLength={3}
                linkDirectionalArrowRelPos={1}
                cooldownTicks={80}
                backgroundColor="transparent"
              />
            )
          )}
        </div>

        {activeNode && (
          <EntityPanel
            node={activeNode}
            onClose={() => {
              setSelected(null);
              setDismissedFocus(true);
            }}
          />
        )}
      </div>
    </div>
  );
}

function EntityPanel({ node, onClose }: { node: CanvasNode; onClose: () => void }) {
  const detail = useAsync(() => api.graphNode(node.id, 1), [node.id]);
  const neighbours = detail.data?.subgraph.edges ?? [];

  return (
    <aside
      aria-label={`Details for ${node.canonical_name}`}
      className="absolute inset-y-0 right-0 z-10 flex w-full max-w-sm flex-col border-l bg-card shadow-md sm:w-80"
    >
      <div className="flex items-start justify-between gap-2 border-b p-4">
        <div className="min-w-0">
          <span
            className="mb-1.5 inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs"
            style={{ color: entityColor(node.type) }}
          >
            <span
              className="size-2 rounded-full"
              style={{ backgroundColor: entityColor(node.type) }}
              aria-hidden
            />
            {node.type}
          </span>
          <h2 className="break-words text-sm font-semibold">{node.canonical_name}</h2>
        </div>
        <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="Close details">
          <X className="size-4" />
        </Button>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto scrollbar-thin p-4 text-sm">
        {node.evidence_snippet && (
          <section className="space-y-1">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Evidence
            </h3>
            <p className="border-l-2 border-primary/40 pl-2.5 text-muted-foreground">
              {node.evidence_snippet}
            </p>
          </section>
        )}

        <section className="space-y-1">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Extraction confidence
          </h3>
          <p className="tabular">{Math.round(node.confidence * 100)}%</p>
        </section>

        {Object.keys(node.properties ?? {}).length > 0 && (
          <section className="space-y-1.5">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Properties
            </h3>
            <dl className="space-y-1">
              {Object.entries(node.properties).map(([key, value]) => (
                <div key={key} className="flex justify-between gap-3">
                  <dt className="shrink-0 text-muted-foreground">{key}</dt>
                  <dd className="break-words text-right">{String(value)}</dd>
                </div>
              ))}
            </dl>
          </section>
        )}

        <section className="space-y-1.5">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Relationships
          </h3>
          {detail.isLoading ? (
            <div className="space-y-1.5">
              {Array.from({ length: 3 }).map((_, index) => (
                <div key={index} className="h-6 animate-pulse rounded bg-muted" />
              ))}
            </div>
          ) : neighbours.length === 0 ? (
            <p className="text-muted-foreground">No relationships recorded.</p>
          ) : (
            <ul className="space-y-1.5">
              {neighbours.map((edge: GraphEdge, index: number) => (
                <li key={index} className="rounded-md border p-2 text-xs">
                  <p>
                    <span className="font-medium">{edge.source}</span>
                    <span className="mx-1 text-muted-foreground">{edge.type}</span>
                    <span className="font-medium">{edge.target}</span>
                  </p>
                  {edge.evidence && (
                    <p className="mt-1 text-muted-foreground">{edge.evidence}</p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </aside>
  );
}
