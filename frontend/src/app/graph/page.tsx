"use client";

import dynamic from "next/dynamic";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useCallback, useRef, useState, useEffect } from "react";
import { Info, User, Wrench, FileText, AlertCircle, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, GraphStats } from "@/lib/api";

// Dynamically import the graph to avoid SSR issues
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
});

export default function KnowledgeGraph() {
  const fgRef = useRef<any>(null);
  const [hoverNode, setHoverNode] = useState<any>(null);
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [stats, setStats] = useState<GraphStats | null>(null);
  const [graphData, setGraphData] = useState<{nodes: any[], links: any[]}>({ nodes: [], links: [] });

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsData, topoData] = await Promise.all([
          api.getGraphStats(),
          api.getGraphTopology()
        ]);
        setStats(statsData);
        // Rename edges to links for ForceGraph2D
        setGraphData({
          nodes: topoData.nodes.map((n: any) => ({
            ...n,
            name: n.canonical_name || n.id,
            group: n.type ? n.type.toLowerCase() : "unknown",
            val: Math.max(5, (n.confidence || 0) * 10)
          })),
          links: topoData.edges
        });
      } catch (e) {
        console.error("Failed to fetch graph data", e);
      }
    };
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  const getNodeColor = (group: string) => {
    switch (group) {
      case "equipment": return "#06b6d4"; // Cyan
      case "document": return "#71717a";  // Gray
      case "incident": return "#f43f5e";  // Rose
      case "personnel": return "#10b981"; // Emerald
      case "component": return "#8b5cf6"; // Violet
      default: return "#ffffff";
    }
  };

  const getIcon = (group: string) => {
    switch (group) {
      case "equipment": return <Wrench className="w-4 h-4 text-cyan-500" />;
      case "document": return <FileText className="w-4 h-4 text-zinc-400" />;
      case "incident": return <AlertCircle className="w-4 h-4 text-rose-500" />;
      case "personnel": return <User className="w-4 h-4 text-emerald-500" />;
      case "component": return <Wrench className="w-4 h-4 text-violet-500" />;
      default: return null;
    }
  };

  // Build an adjacency list for highlighting
  const neighbors = useRef(new Map());
  if (neighbors.current.size === 0) {
    graphData.links.forEach(link => {
      const a = typeof link.source === 'object' ? (link.source as any).id : link.source;
      const b = typeof link.target === 'object' ? (link.target as any).id : link.target;
      if (!neighbors.current.has(a)) neighbors.current.set(a, new Set());
      if (!neighbors.current.has(b)) neighbors.current.set(b, new Set());
      neighbors.current.get(a).add(b);
      neighbors.current.get(b).add(a);
    });
  }

  const drawNode = useCallback((node: any, ctx: any, globalScale: any) => {
    const label = node.name;
    const fontSize = 12/globalScale;
    ctx.font = `${fontSize}px Sans-Serif`;

    const isHovered = hoverNode === node;
    const isSelected = selectedNode === node;
    
    // Dim non-connected nodes when a node is selected or hovered
    const activeNode = selectedNode || hoverNode;
    const isNeighbor = activeNode && neighbors.current.get(activeNode.id)?.has(node.id);
    const isFaded = activeNode && !isSelected && !isHovered && !isNeighbor;

    ctx.globalAlpha = isFaded ? 0.2 : 1;

    ctx.fillStyle = getNodeColor(node.group);
    ctx.beginPath();
    
    // Draw different shapes based on group
    if (node.group === "equipment") {
      ctx.arc(node.x, node.y, 8, 0, 2 * Math.PI, false);
      ctx.fill();
    } else if (node.group === "document") {
      ctx.fillRect(node.x - 6, node.y - 6, 12, 12);
    } else if (node.group === "incident") {
      ctx.moveTo(node.x, node.y - 8);
      ctx.lineTo(node.x + 8, node.y + 8);
      ctx.lineTo(node.x - 8, node.y + 8);
      ctx.fill();
    } else {
      ctx.arc(node.x, node.y, 6, 0, 2 * Math.PI, false);
      ctx.fill();
    }

    if (isHovered || isSelected) {
      ctx.strokeStyle = getNodeColor(node.group);
      ctx.lineWidth = 2 / globalScale;
      ctx.beginPath();
      ctx.arc(node.x, node.y, 12, 0, 2 * Math.PI, false);
      ctx.stroke();
    }

    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = isFaded ? '#71717a' : '#e4e4e7';
    ctx.fillText(label, node.x, node.y + 12);
    
    ctx.globalAlpha = 1; // reset
  }, [hoverNode, selectedNode]);

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col relative overflow-hidden">
      <div className="absolute top-6 left-6 z-10 w-80 space-y-4 pointer-events-none">
        <div>
          <h2 className="text-2xl font-bold text-zinc-100 drop-shadow-md">NeuroFab Fabric</h2>
          <p className="text-sm text-zinc-300 drop-shadow-md">Interactive visual topology of connected industrial assets.</p>
        </div>
        
        <Card className="bg-zinc-950/80 backdrop-blur-md border-zinc-800 pointer-events-auto shadow-lg shadow-black/50">
          <div className="p-4 space-y-3">
            <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Legend</h3>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-cyan-500" /> Equipment</div>
              <div className="flex items-center gap-2"><div className="w-3 h-3 bg-zinc-500" /> Document</div>
              <div className="flex items-center gap-2">
                <div className="w-0 h-0 border-l-[6px] border-l-transparent border-r-[6px] border-r-transparent border-b-[10px] border-b-rose-500" /> Incident
              </div>
              <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-emerald-500" /> Personnel</div>
            </div>
          </div>
        </Card>

        <Card className="bg-zinc-950/80 backdrop-blur-md border-zinc-800 pointer-events-auto shadow-lg shadow-black/50">
          <div className="p-4 flex gap-3 items-start">
            <Info className="w-5 h-5 text-cyan-500 shrink-0" />
            <p className="text-[11px] text-zinc-300 leading-relaxed">
              <strong>Tip:</strong> Scroll to zoom, drag background to pan, drag nodes to manipulate the physics engine, and click to view metadata.
            </p>
          </div>
        </Card>
      </div>

      {/* Selected Node Details Panel */}
      {selectedNode && (
        <div className="absolute top-6 right-6 z-20 w-80 pointer-events-auto animate-in slide-in-from-right-8 duration-300">
          <Card className="bg-zinc-950 border-zinc-700 shadow-2xl shadow-black/50">
            <CardHeader className="pb-3 border-b border-zinc-800">
              <div className="flex justify-between items-start">
                <div className="flex items-center gap-2">
                  {getIcon(selectedNode.group)}
                  <Badge variant="outline" className="capitalize text-[10px] border-zinc-700 text-zinc-400">
                    {selectedNode.group}
                  </Badge>
                </div>
                <Button variant="ghost" size="icon" className="h-6 w-6 text-zinc-400 hover:text-white" onClick={() => setSelectedNode(null)}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
              <CardTitle className="text-lg text-zinc-100 mt-2">{selectedNode.name}</CardTitle>
            </CardHeader>
            <CardContent className="pt-4 space-y-4">
              <div>
                <p className="text-xs text-zinc-500 mb-1">Description</p>
                <p className="text-sm text-zinc-300">{selectedNode.desc}</p>
              </div>
              <div>
                <p className="text-xs text-zinc-500 mb-1">System ID</p>
                <p className="text-xs text-zinc-400 font-mono bg-zinc-900 p-1.5 rounded">{selectedNode.id}</p>
              </div>
              <div>
                <p className="text-xs text-zinc-500 mb-2">Connected Entities</p>
                <div className="space-y-2">
                  {graphData.links.filter(l => (typeof l.source === 'object' ? (l.source as any).id : l.source) === selectedNode.id || (typeof l.target === 'object' ? (l.target as any).id : l.target) === selectedNode.id).map((link, i) => {
                    const isSource = (typeof link.source === 'object' ? (link.source as any).id : link.source) === selectedNode.id;
                    const relatedId = isSource ? (typeof link.target === 'object' ? (link.target as any).id : link.target) : (typeof link.source === 'object' ? (link.source as any).id : link.source);
                    return (
                      <div key={i} className="flex justify-between items-center text-xs">
                        <span className="text-cyan-400 uppercase tracking-wider text-[10px]">{link.label}</span>
                        <span className="text-zinc-300">{relatedId}</span>
                      </div>
                    )
                  })}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      <div className="flex-1 bg-[#09090b] relative">
        <ForceGraph2D
          ref={fgRef}
          graphData={graphData}
          nodeLabel="" // Disable default tooltip since we use custom drawing
          nodeColor={(n: any) => getNodeColor(n.group)}
          linkColor={(l: any) => {
            const activeNode = selectedNode || hoverNode;
            if (activeNode) {
              const aId = typeof l.source === 'object' ? l.source.id : l.source;
              const bId = typeof l.target === 'object' ? l.target.id : l.target;
              if (aId === activeNode.id || bId === activeNode.id) return getNodeColor(activeNode.group); // Highlight color
              return "#27272a22"; // Fade out
            }
            return "#3f3f46"; // Default link color
          }}
          linkWidth={(l: any) => {
            const activeNode = selectedNode || hoverNode;
            if (activeNode) {
              const aId = typeof l.source === 'object' ? l.source.id : l.source;
              const bId = typeof l.target === 'object' ? l.target.id : l.target;
              if (aId === activeNode.id || bId === activeNode.id) return 2;
            }
            return 1;
          }}
          linkDirectionalArrowLength={3.5}
          linkDirectionalArrowRelPos={1}
          linkCurvature={0.25}
          nodeCanvasObject={drawNode}
          onNodeHover={setHoverNode}
          onNodeClick={(node) => {
            setSelectedNode(node);
            // Optional: center node on click
            if (fgRef.current) {
              fgRef.current.centerAt(node.x, node.y, 1000);
              fgRef.current.zoom(2, 1000);
            }
          }}
          backgroundColor="#09090b"
          width={typeof window !== "undefined" ? window.innerWidth - 256 : 800}
          height={typeof window !== "undefined" ? window.innerHeight - 64 : 600}
        />
      </div>

      {/* Live Backend Statistics */}
      {stats && (
        <div className="absolute bottom-6 left-6 z-10 w-80 pointer-events-none">
          <Card className="bg-zinc-950/80 backdrop-blur-md border-zinc-800 pointer-events-auto shadow-lg shadow-black/50">
            <div className="p-4 space-y-3">
              <h3 className="text-xs font-semibold text-cyan-400 uppercase tracking-wider flex items-center justify-between">
                Live Backend Stats
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              </h3>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-zinc-500 text-xs">Total Nodes</p>
                  <p className="text-zinc-100 font-mono text-lg">{stats.total_nodes}</p>
                </div>
                <div>
                  <p className="text-zinc-500 text-xs">Total Relationships</p>
                  <p className="text-zinc-100 font-mono text-lg">{stats.total_relationships}</p>
                </div>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
