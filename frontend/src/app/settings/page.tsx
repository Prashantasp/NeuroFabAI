"use client";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Settings as SettingsIcon, Database, Key, Bell, Shield, Cpu, GitBranch, Search } from "lucide-react";

export default function Settings() {
  return (
    <div className="p-6 max-w-[1200px] mx-auto space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-zinc-100 flex items-center gap-2">
          <SettingsIcon className="h-6 w-6 text-cyan-500" />
          System Settings
        </h2>
        <p className="text-sm text-zinc-400 mt-1">Read-only configuration for the NeuroFab AI platform.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        
        {/* Settings Navigation */}
        <div className="space-y-1">
          <div className="w-full flex items-center px-4 py-2 text-sm text-zinc-300 bg-zinc-800/50 rounded-md">
            <Cpu className="w-4 h-4 mr-2" />
            AI Orchestrator
          </div>
          <div className="w-full flex items-center px-4 py-2 text-sm text-zinc-500 opacity-50">
            <Database className="w-4 h-4 mr-2" />
            Data Connectors
          </div>
          <div className="w-full flex items-center px-4 py-2 text-sm text-zinc-500 opacity-50">
            <Shield className="w-4 h-4 mr-2" />
            Security & Access
          </div>
        </div>

        {/* Settings Content */}
        <div className="md:col-span-3 space-y-6">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-zinc-100">Language Models</CardTitle>
              <CardDescription className="text-zinc-400">Models powering the multi-agent system.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex justify-between items-center p-3 border border-zinc-800 rounded bg-zinc-950">
                <div>
                  <p className="text-sm font-medium text-zinc-200">Primary Reasoning Model</p>
                  <p className="text-xs text-zinc-500 font-mono mt-1">gemini-flash-latest</p>
                </div>
                <Badge className="bg-emerald-500/10 text-emerald-400 border-none">Active</Badge>
              </div>

              <div className="flex justify-between items-center p-3 border border-zinc-800 rounded bg-zinc-950">
                <div>
                  <p className="text-sm font-medium text-zinc-200">Embedding Model</p>
                  <p className="text-xs text-zinc-500 font-mono mt-1">gemini-embedding-2</p>
                </div>
                <Badge className="bg-emerald-500/10 text-emerald-400 border-none">Active</Badge>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-zinc-100">Databases & Infrastructure</CardTitle>
              <CardDescription className="text-zinc-400">Current persistent and in-memory stores.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between p-3 border border-zinc-800 rounded bg-zinc-950">
                <div className="flex items-center gap-3">
                  <GitBranch className="w-5 h-5 text-emerald-500" />
                  <div>
                    <span className="text-sm font-medium text-zinc-200 block">Knowledge Graph</span>
                    <span className="text-xs text-zinc-500 font-mono">NetworkX (Local In-Memory)</span>
                  </div>
                </div>
                <Badge className="bg-emerald-500/10 text-emerald-400 border-none">Connected</Badge>
              </div>

              <div className="flex items-center justify-between p-3 border border-zinc-800 rounded bg-zinc-950">
                <div className="flex items-center gap-3">
                  <Search className="w-5 h-5 text-emerald-500" />
                  <div>
                    <span className="text-sm font-medium text-zinc-200 block">Vector Store</span>
                    <span className="text-xs text-zinc-500 font-mono">Qdrant (Local Index)</span>
                  </div>
                </div>
                <Badge className="bg-emerald-500/10 text-emerald-400 border-none">Connected</Badge>
              </div>
              
              <div className="flex items-center justify-between p-3 border border-zinc-800 rounded bg-zinc-950">
                <div className="flex items-center gap-3">
                  <Database className="w-5 h-5 text-emerald-500" />
                  <div>
                    <span className="text-sm font-medium text-zinc-200 block">Relational Database</span>
                    <span className="text-xs text-zinc-500 font-mono">SQLite (neurofab_os.db)</span>
                  </div>
                </div>
                <Badge className="bg-emerald-500/10 text-emerald-400 border-none">Connected</Badge>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
