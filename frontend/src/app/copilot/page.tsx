"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, FileText, CheckCircle2, ShieldAlert, Activity, AlertCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { api, ChatResponse } from "@/lib/api";

type Message = {
  id: string;
  role: "user" | "ai";
  content: string;
  response?: ChatResponse;
  isError?: boolean;
};

export default function CopilotPage() {
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isReasoning, setIsReasoning] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const activeResponse = messages.length > 0 && messages[messages.length - 1].role === "ai" 
    ? messages[messages.length - 1].response 
    : null;

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isReasoning]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || isReasoning) return;

    const userMsg: Message = { id: Date.now().toString(), role: "user", content: query };
    setMessages(prev => [...prev, userMsg]);
    setQuery("");
    setIsReasoning(true);

    try {
      const data = await api.askCopilot(userMsg.content);
      const aiMsg: Message = { 
        id: (Date.now() + 1).toString(), 
        role: "ai", 
        content: "Done", 
        response: data 
      };
      setMessages(prev => [...prev, aiMsg]);
    } catch (err: any) {
      const aiMsg: Message = { 
        id: (Date.now() + 1).toString(), 
        role: "ai", 
        content: err.message || "Failed to reach the reasoning engine.", 
        isError: true 
      };
      setMessages(prev => [...prev, aiMsg]);
    } finally {
      setIsReasoning(false);
    }
  };

  return (
    <div className="flex h-full max-w-[1600px] mx-auto p-4 gap-4">
      
      {/* Left Pane: Chat Interface */}
      <Card className="flex-1 flex flex-col bg-zinc-900 border-zinc-800 h-[calc(100vh-8rem)]">
        <CardHeader className="border-b border-zinc-800 pb-4">
          <CardTitle className="text-zinc-100 flex items-center gap-2">
            <Bot className="h-5 w-5 text-cyan-500" />
            AI Copilot
          </CardTitle>
          <CardDescription className="text-zinc-400">
            Ask complex queries. The multi-agent orchestrator will resolve them.
          </CardDescription>
        </CardHeader>
        
        <ScrollArea className="flex-1 p-4" ref={scrollRef}>
          <div className="space-y-6">
            
            {messages.length === 0 && !isReasoning && (
              <div className="flex flex-col items-center justify-center h-full text-zinc-500 space-y-4 py-20">
                <Bot className="h-12 w-12 text-zinc-700" />
                <p>Hello. I am the NeuroFab Copilot. How can I assist you?</p>
              </div>
            )}

            {messages.map((msg) => (
              <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                {msg.role === 'user' ? (
                  <div className="max-w-[80%] bg-zinc-800 rounded-lg rounded-tr-none p-4 text-zinc-100 text-sm">
                    {msg.content}
                  </div>
                ) : (
                  <div className="flex gap-3 max-w-[90%]">
                    <div className="h-8 w-8 rounded-full bg-cyan-500/20 border border-cyan-500 flex items-center justify-center shrink-0 mt-1">
                      <Bot className="h-4 w-4 text-cyan-500" />
                    </div>
                    <div className="bg-zinc-950 border border-zinc-800 rounded-lg rounded-tl-none p-4 text-sm text-zinc-300 space-y-4 w-full">
                      
                      {msg.isError ? (
                        <div className="flex items-center gap-2 text-rose-400">
                          <AlertCircle className="w-4 h-4" />
                          <p>{msg.content}</p>
                        </div>
                      ) : (
                        msg.response?.decision && (
                          <>
                            <p className="text-zinc-200 text-base">{msg.response.decision.executive_summary}</p>
                            
                            <div className="p-3 bg-zinc-900 border border-zinc-800 rounded-md">
                              <h4 className="font-semibold text-zinc-100 mb-2 flex items-center gap-2">
                                <ShieldAlert className="h-4 w-4 text-amber-500" /> 
                                Root Cause
                              </h4>
                              <p className="text-sm text-zinc-400 mb-4">{msg.response.decision.root_cause}</p>
                              
                              <h4 className="font-semibold text-zinc-100 mb-2 flex items-center gap-2">
                                <CheckCircle2 className="h-4 w-4 text-emerald-500" /> 
                                Recommended Action
                              </h4>
                              <p className="text-sm text-zinc-400 mb-4">{msg.response.decision.recommended_action}</p>

                              <div className="flex flex-wrap gap-2 pt-2 border-t border-zinc-800">
                                <Badge variant="outline" className={`border-zinc-700 ${msg.response.decision.risk_level === 'High' ? 'text-rose-400 bg-rose-500/10' : 'text-amber-400 bg-amber-500/10'}`}>
                                  Risk: {msg.response.decision.risk_level}
                                </Badge>
                                <Badge variant="outline" className="text-emerald-400 border-emerald-500/30 bg-emerald-500/10">
                                  Impact: {msg.response.decision.business_impact}
                                </Badge>
                              </div>
                            </div>
                          </>
                        )
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}

            {isReasoning && (
              <div className="flex justify-start">
                <div className="flex gap-3 max-w-[90%]">
                  <div className="h-8 w-8 rounded-full bg-cyan-500/20 border border-cyan-500 flex items-center justify-center shrink-0 mt-1 animate-pulse">
                    <Bot className="h-4 w-4 text-cyan-500" />
                  </div>
                  <div className="bg-zinc-950 border border-zinc-800 rounded-lg rounded-tl-none p-4 text-sm text-zinc-400 flex items-center gap-2">
                    <Activity className="h-4 w-4 animate-spin text-cyan-500" />
                    NeuroFab Agents are Reasoning...
                  </div>
                </div>
              </div>
            )}

          </div>
        </ScrollArea>

        <div className="px-4 pb-2 pt-0 flex gap-2 overflow-x-auto no-scrollbar">
          <Badge 
            variant="outline" 
            className="cursor-pointer hover:bg-zinc-800 border-zinc-700 text-zinc-400 shrink-0"
            onClick={() => setQuery("Why is Pump P-101 overheating?")}
          >
            "Why is Pump P-101 overheating?"
          </Badge>
          <Badge 
            variant="outline" 
            className="cursor-pointer hover:bg-zinc-800 border-zinc-700 text-zinc-400 shrink-0"
            onClick={() => setQuery("Find the SOP.")}
          >
            "Find the SOP."
          </Badge>
          <Badge 
            variant="outline" 
            className="cursor-pointer hover:bg-zinc-800 border-zinc-700 text-zinc-400 shrink-0"
            onClick={() => setQuery("Why did it fail?")}
          >
            "Why did it fail?"
          </Badge>
        </div>

        <div className="p-4 border-t border-zinc-800">
          <form className="flex gap-2" onSubmit={handleSubmit}>
            <Input 
              placeholder="Ask about equipment, SOPs, or troubleshooting..." 
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              disabled={isReasoning}
              className="bg-zinc-950 border-zinc-800 focus-visible:ring-cyan-500 text-zinc-100"
            />
            <Button type="submit" size="icon" disabled={isReasoning} className="bg-cyan-600 hover:bg-cyan-700 text-white shrink-0">
              <Send className="h-4 w-4" />
            </Button>
          </form>
        </div>
      </Card>

      {/* Right Pane: Explainability Engine */}
      <div className="w-[400px] flex flex-col gap-4">
        
        {/* Reasoning Flow */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm text-zinc-100 flex items-center justify-between">
              Reasoning Timeline
              {activeResponse?.decision && (
                <Badge variant="outline" className="border-cyan-500/50 text-cyan-400 bg-cyan-500/10">
                  {Math.round(activeResponse.decision.confidence * 100)}% Confidence
                </Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {!activeResponse ? (
              <p className="text-xs text-zinc-500 text-center py-4">No active workflow.</p>
            ) : (
              <div className="space-y-4 relative before:absolute before:inset-0 before:ml-2 before:-translate-x-px md:before:mx-auto md:before:translate-x-0 before:h-full before:w-0.5 before:bg-gradient-to-b before:from-transparent before:via-zinc-800 before:to-transparent">
                
                {activeResponse.reasoning_timeline.map((event, idx) => (
                  <div key={idx} className="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group is-active">
                    <div className={`flex items-center justify-center w-5 h-5 rounded-full border bg-zinc-900 shadow shrink-0 z-10 ${event.action.includes('Fail') ? 'border-rose-500 text-rose-500' : 'border-cyan-500 text-cyan-500'}`}>
                      {event.action.includes('Fail') ? <AlertCircle className="h-3 w-3" /> : <CheckCircle2 className="h-3 w-3" />}
                    </div>
                    <div className="w-[calc(100%-2.5rem)] md:w-[calc(50%-1.25rem)] p-2 rounded border border-zinc-800 bg-zinc-950 ml-2">
                      <div className="flex items-center justify-between mb-1">
                        <p className="text-xs font-semibold text-zinc-300">{event.agent_name}</p>
                        <span className="text-[9px] text-zinc-500 font-mono">{event.duration_ms.toFixed(0)}ms</span>
                      </div>
                      <p className="text-[10px] text-cyan-400 mb-1">{event.action}</p>
                      <p className="text-[10px] text-zinc-500">{event.summary}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Supporting Evidence */}
        {activeResponse?.decision && activeResponse.decision.supporting_evidence.length > 0 && (
          <Card className="bg-zinc-900 border-zinc-800 flex-1">
            <CardHeader className="pb-3 flex flex-row items-center justify-between">
              <CardTitle className="text-sm text-zinc-100">Supporting Evidence</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {activeResponse.decision.supporting_evidence.map((evidence, idx) => (
                <div key={idx} className="p-2 rounded bg-zinc-950 border border-zinc-800 group cursor-pointer hover:border-cyan-500/50 transition-colors">
                  <div className="flex items-center gap-2 mb-1">
                    <FileText className="h-3 w-3 text-cyan-500" />
                    <span className="text-xs font-medium text-zinc-300">Extracted Fact</span>
                  </div>
                  <p className="text-[11px] text-zinc-400 italic border-l-2 border-cyan-500/30 pl-2">
                    {evidence}
                  </p>
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
