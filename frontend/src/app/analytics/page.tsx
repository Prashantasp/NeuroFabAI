"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { TrendingUp, Database, FileText, GitBranch, Cpu, Activity, Clock } from "lucide-react";
import { api, DocumentResponse, GraphStats } from "@/lib/api";

export default function Analytics() {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [stats, setStats] = useState<any>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [docsData, statsData] = await Promise.all([
          api.getDocuments(),
          api.getGraphStats()
        ]);
        setDocuments(docsData);
        setStats(statsData);
      } catch (e) {
        console.error("Failed to fetch analytics data", e);
      }
    };
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  const processingDocs = documents.filter(d => d.status !== 'Ready' && d.status !== 'Failed').length;
  const readyDocs = documents.filter(d => d.status === 'Ready').length;
  
  // Calculate average processing time
  const processedDocs = documents.filter(d => d.processing_duration != null);
  const avgProcessingTime = processedDocs.length > 0 
    ? (processedDocs.reduce((acc, d) => acc + (d.processing_duration || 0), 0) / processedDocs.length).toFixed(2)
    : "0.00";

  return (
    <div className="p-6 max-w-[1600px] mx-auto space-y-6">
      <div className="flex justify-between items-start">
        <div>
          <h2 className="text-2xl font-bold text-zinc-100 flex items-center gap-2">
            <TrendingUp className="h-6 w-6 text-cyan-500" />
            Platform Analytics
          </h2>
          <p className="text-sm text-zinc-400 mt-1">Real-time metrics on ingestion, extraction, and orchestrator performance.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-zinc-400">Total Documents</CardTitle>
            <FileText className="h-4 w-4 text-emerald-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-zinc-100">{documents.length}</div>
            <p className="text-xs text-emerald-500 mt-1">{readyDocs} Successfully Indexed</p>
          </CardContent>
        </Card>
        
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-zinc-400">Extracted Entities</CardTitle>
            <Database className="h-4 w-4 text-emerald-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-zinc-100">{stats?.total_nodes || 0}</div>
            <p className="text-xs text-emerald-500 mt-1">Canonical Knowledge Nodes</p>
          </CardContent>
        </Card>

        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-zinc-400">Graph Relationships</CardTitle>
            <GitBranch className="h-4 w-4 text-cyan-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-zinc-100">{stats?.total_relationships || 0}</div>
            <p className="text-xs text-cyan-500 mt-1">Validated Edges</p>
          </CardContent>
        </Card>

        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-zinc-400">Avg Processing Time</CardTitle>
            <Clock className="h-4 w-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-zinc-100">{avgProcessingTime}s</div>
            <p className="text-xs text-amber-500 mt-1">Per Document Pipeline</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-zinc-100">Knowledge Graph Breakdown</CardTitle>
            <CardDescription className="text-zinc-400">Entities extracted by type.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {stats?.entity_type_counts && Object.entries(stats.entity_type_counts).map(([type, count]) => (
                <div key={type} className="flex items-center justify-between">
                  <span className="text-sm text-zinc-300">{String(type)}</span>
                  <span className="text-sm font-medium text-zinc-100">{String(count)}</span>
                </div>
              ))}
              {!stats?.entity_type_counts && (
                <div className="text-sm text-zinc-500">No entities extracted yet.</div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-zinc-100">Orchestrator Activity</CardTitle>
            <CardDescription className="text-zinc-400">Live agent metrics.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-6">
               <div className="flex justify-between items-center pb-4 border-b border-zinc-800">
                  <div className="flex gap-3 items-center">
                    <Cpu className="text-emerald-500 w-5 h-5" />
                    <div>
                      <p className="text-sm font-medium text-zinc-200">Total Available Agents</p>
                      <p className="text-xs text-zinc-500">Coordinator, Search, Graph, Maintenance</p>
                    </div>
                  </div>
                  <span className="text-xl font-bold text-zinc-100">4</span>
               </div>
               <div className="flex justify-between items-center pb-4 border-b border-zinc-800">
                  <div className="flex gap-3 items-center">
                    <Activity className="text-cyan-500 w-5 h-5" />
                    <div>
                      <p className="text-sm font-medium text-zinc-200">Vector Embeddings</p>
                      <p className="text-xs text-zinc-500">In-memory FAISS store size</p>
                    </div>
                  </div>
                  <span className="text-xl font-bold text-zinc-100">
                     {documents.length > 0 ? readyDocs * 12 : 0} {/* Approximation based on docs */}
                  </span>
               </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
