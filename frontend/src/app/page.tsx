"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { CheckCircle2, Activity, FileText, Database, GitBranch, Cpu, Clock, Search, ExternalLink } from "lucide-react";
import { api, DocumentResponse, GraphStats } from "@/lib/api";
import Link from "next/link";

export default function CommandCenter() {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [stats, setStats] = useState<GraphStats | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [docsData, statsData] = await Promise.all([
          api.getDocuments(),
          api.getGraphStats()
        ]);
        setDocuments(docsData.sort((a, b) => new Date(b.uploaded_at).getTime() - new Date(a.uploaded_at).getTime()));
        setStats(statsData);
      } catch (e) {
        console.error("Failed to fetch dashboard data", e);
      }
    };
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  const processingDocs = documents.filter(d => d.status !== 'Ready' && d.status !== 'Failed').length;
  const readyDocs = documents.filter(d => d.status === 'Ready').length;

  return (
    <div className="p-6 max-w-[1600px] mx-auto space-y-6">
      
      {/* Top KPI Row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-zinc-400">Total Documents</CardTitle>
            <FileText className="h-4 w-4 text-emerald-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-zinc-100">{documents.length}</div>
            <p className="text-xs text-zinc-500 mt-1">
              {readyDocs} Indexed • {processingDocs} Processing
            </p>
          </CardContent>
        </Card>
        
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-zinc-400">Knowledge Nodes</CardTitle>
            <Database className="h-4 w-4 text-cyan-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-zinc-100">{stats?.total_nodes || 0}</div>
            <p className="text-xs text-zinc-500 mt-1">Extracted Entities</p>
          </CardContent>
        </Card>

        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-zinc-400">Knowledge Edges</CardTitle>
            <GitBranch className="h-4 w-4 text-purple-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-zinc-100">{stats?.total_relationships || 0}</div>
            <p className="text-xs text-zinc-500 mt-1">Validated Relationships</p>
          </CardContent>
        </Card>

        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-zinc-400">Active Agents</CardTitle>
            <Cpu className="h-4 w-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-zinc-100">4</div>
            <p className="text-xs text-zinc-500 mt-1">Orchestrator, Search, Graph, Maintenance</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        {/* Recent Document Activity */}
        <Card className="bg-zinc-900 border-zinc-800 flex-1">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-zinc-100">Recent Ingestions</CardTitle>
              <CardDescription className="text-zinc-400">Latest files processed by the pipeline.</CardDescription>
            </div>
            <Link href="/hub">
              <Badge variant="outline" className="cursor-pointer hover:bg-zinc-800 border-zinc-700 text-zinc-400">View Hub <ExternalLink className="w-3 h-3 ml-1" /></Badge>
            </Link>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-[300px] pr-4">
              <div className="space-y-4">
                {documents.length === 0 ? (
                  <div className="text-center text-zinc-500 py-10">No documents ingested yet.</div>
                ) : (
                  documents.slice(0, 10).map((doc) => (
                    <div key={doc.id} className="flex items-start justify-between border-b border-zinc-800/50 pb-3 last:border-0">
                      <div className="flex gap-3">
                        <div className={`mt-0.5 ${doc.status === 'Ready' ? 'text-emerald-500' : doc.status === 'Failed' ? 'text-rose-500' : 'text-amber-500 animate-pulse'}`}>
                          {doc.status === 'Ready' ? <CheckCircle2 className="h-4 w-4" /> : doc.status === 'Failed' ? <Activity className="h-4 w-4" /> : <Clock className="h-4 w-4" />}
                        </div>
                        <div className="space-y-1">
                          <p className="text-sm font-medium text-zinc-300">{doc.filename}</p>
                          <p className="text-xs text-zinc-500">{new Date(doc.uploaded_at).toLocaleString()}</p>
                        </div>
                      </div>
                      <Badge variant="outline" className="border-zinc-800 bg-zinc-950 text-zinc-400 font-mono text-[10px]">
                        {doc.status}
                      </Badge>
                    </div>
                  ))
                )}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>

        {/* System Health Overview */}
        <Card className="bg-zinc-900 border-zinc-800 flex-1 flex flex-col">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-zinc-100">System Health</CardTitle>
              <CardDescription className="text-zinc-400">Live component statuses.</CardDescription>
            </div>
          </CardHeader>
          <CardContent className="space-y-4 flex-1">
            <div className="p-4 border border-zinc-800 rounded bg-zinc-950 flex justify-between items-center">
               <div className="flex items-center gap-3">
                 <Database className="w-5 h-5 text-emerald-500" />
                 <div>
                   <p className="text-sm font-medium text-zinc-200">Vector Store (Qdrant)</p>
                   <p className="text-xs text-zinc-500">Connected • FAISS In-Memory Mode</p>
                 </div>
               </div>
               <Badge className="bg-emerald-500/10 text-emerald-400 border-none">Online</Badge>
            </div>
            
            <div className="p-4 border border-zinc-800 rounded bg-zinc-950 flex justify-between items-center">
               <div className="flex items-center gap-3">
                 <GitBranch className="w-5 h-5 text-emerald-500" />
                 <div>
                   <p className="text-sm font-medium text-zinc-200">Graph Database (NetworkX)</p>
                   <p className="text-xs text-zinc-500">Connected • {stats?.total_nodes || 0} Nodes</p>
                 </div>
               </div>
               <Badge className="bg-emerald-500/10 text-emerald-400 border-none">Online</Badge>
            </div>

            <div className="p-4 border border-zinc-800 rounded bg-zinc-950 flex justify-between items-center">
               <div className="flex items-center gap-3">
                 <Cpu className="w-5 h-5 text-emerald-500" />
                 <div>
                   <p className="text-sm font-medium text-zinc-200">Multi-Agent Orchestrator</p>
                   <p className="text-xs text-zinc-500">LangGraph-inspired StateGraph</p>
                 </div>
               </div>
               <Badge className="bg-emerald-500/10 text-emerald-400 border-none">Online</Badge>
            </div>

            <div className="mt-6 border border-cyan-500/30 bg-cyan-500/10 rounded-lg p-4 text-center">
               <Search className="w-6 h-6 text-cyan-400 mx-auto mb-2" />
               <p className="text-sm text-zinc-300 font-medium">Ready to analyze</p>
               <p className="text-xs text-zinc-500 mt-1 mb-3">The NeuroFab backend is fully operational.</p>
               <Link href="/copilot">
                 <Badge className="bg-cyan-600 hover:bg-cyan-500 text-white cursor-pointer px-3 py-1">Open Copilot</Badge>
               </Link>
            </div>
          </CardContent>
        </Card>

      </div>
    </div>
  );
}
