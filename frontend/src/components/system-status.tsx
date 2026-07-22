"use client";

import { useEffect, useState } from "react";
import { Activity, Database, GitBranch, Cpu, AlertCircle, CheckCircle2 } from "lucide-react";
import { api, GraphStats } from "@/lib/api";

export function SystemStatus() {
  const [stats, setStats] = useState<GraphStats | null>(null);
  const [error, setError] = useState<boolean>(false);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const data = await api.getGraphStats();
        setStats(data);
        setError(false);
      } catch (err) {
        setError(true);
      }
    };
    
    fetchStats();
    const interval = setInterval(fetchStats, 10000); // refresh every 10s
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="fixed bottom-4 right-4 z-50">
      <div className="bg-zinc-900/80 backdrop-blur-md border border-zinc-800 rounded-lg shadow-xl p-3 flex items-center gap-4 text-xs font-mono">
        <div className="flex items-center gap-1.5 border-r border-zinc-800 pr-4">
          <Activity className={`w-3.5 h-3.5 ${error ? 'text-red-500' : 'text-emerald-500 animate-pulse'}`} />
          <span className={error ? 'text-zinc-500' : 'text-zinc-300'}>
            {error ? 'API Offline' : 'System Online'}
          </span>
        </div>
        
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-zinc-400" title="Vector Store">
            <Database className="w-3.5 h-3.5" />
            <span>Ready</span>
          </div>
          
          <div className="flex items-center gap-1.5 text-cyan-400" title="Knowledge Graph Nodes & Relationships">
            <GitBranch className="w-3.5 h-3.5" />
            <span>{stats ? `${stats.total_nodes}N / ${stats.total_relationships}E` : '---'}</span>
          </div>
          
          <div className="flex items-center gap-1.5 text-purple-400" title="Active Agents">
            <Cpu className="w-3.5 h-3.5" />
            <span>4 Agents</span>
          </div>
        </div>
      </div>
    </div>
  );
}
