"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Bot, ShieldAlert, CheckCircle2, Activity, AlertCircle, Wrench } from "lucide-react";
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

export default function MaintenanceIntelligence() {
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isReasoning, setIsReasoning] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isReasoning]);

  const handleSubmit = async (e?: React.FormEvent, presetQuery?: string) => {
    if (e) e.preventDefault();
    const text = presetQuery || query;
    if (!text.trim() || isReasoning) return;

    const userMsg: Message = { id: Date.now().toString(), role: "user", content: text };
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
    <div className="p-6 max-w-[1600px] mx-auto space-y-6 h-[calc(100vh-4rem)] flex flex-col">
      <div>
        <h2 className="text-2xl font-bold text-zinc-100 flex items-center gap-2">
          <Wrench className="h-6 w-6 text-emerald-500" />
          Maintenance Intelligence
        </h2>
        <p className="text-sm text-zinc-400 mt-1">Predictive asset health and AI-generated maintenance recommendations via Copilot.</p>
      </div>

      <div className="flex gap-2 overflow-x-auto no-scrollbar shrink-0">
        <Badge 
          variant="outline" 
          className="cursor-pointer hover:bg-zinc-800 border-zinc-700 text-zinc-400 py-1.5 px-3"
          onClick={() => handleSubmit(undefined, "What is the maintenance status of P-101?")}
        >
          Status of P-101
        </Badge>
        <Badge 
          variant="outline" 
          className="cursor-pointer hover:bg-zinc-800 border-zinc-700 text-zinc-400 py-1.5 px-3"
          onClick={() => handleSubmit(undefined, "Are there any critical maintenance warnings?")}
        >
          Find Critical Warnings
        </Badge>
        <Badge 
          variant="outline" 
          className="cursor-pointer hover:bg-zinc-800 border-zinc-700 text-zinc-400 py-1.5 px-3"
          onClick={() => handleSubmit(undefined, "Generate a maintenance schedule based on recent failures.")}
        >
          Generate Schedule
        </Badge>
      </div>

      <Card className="flex-1 flex flex-col bg-zinc-900 border-zinc-800 overflow-hidden">
        <ScrollArea className="flex-1 p-4" ref={scrollRef}>
          <div className="space-y-6 max-w-4xl mx-auto">
            
            {messages.length === 0 && !isReasoning && (
              <div className="flex flex-col items-center justify-center h-[400px] text-zinc-500 space-y-4">
                <Wrench className="h-12 w-12 text-zinc-700" />
                <p>Hello. I am the NeuroFab Maintenance Agent. Ask me to analyze any equipment.</p>
              </div>
            )}

            {messages.map((msg) => (
              <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                {msg.role === 'user' ? (
                  <div className="max-w-[80%] bg-zinc-800 rounded-lg rounded-tr-none p-4 text-zinc-100 text-sm">
                    {msg.content}
                  </div>
                ) : (
                  <div className="flex gap-3 max-w-[90%] w-full">
                    <div className="h-8 w-8 rounded-full bg-emerald-500/20 border border-emerald-500 flex items-center justify-center shrink-0 mt-1">
                      <Bot className="h-4 w-4 text-emerald-500" />
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
                  <div className="h-8 w-8 rounded-full bg-emerald-500/20 border border-emerald-500 flex items-center justify-center shrink-0 mt-1 animate-pulse">
                    <Bot className="h-4 w-4 text-emerald-500" />
                  </div>
                  <div className="bg-zinc-950 border border-zinc-800 rounded-lg rounded-tl-none p-4 text-sm text-zinc-400 flex items-center gap-2">
                    <Activity className="h-4 w-4 animate-spin text-emerald-500" />
                    Analyzing equipment history...
                  </div>
                </div>
              </div>
            )}

          </div>
        </ScrollArea>

        <div className="p-4 border-t border-zinc-800 bg-zinc-950">
          <form className="flex gap-2 max-w-4xl mx-auto" onSubmit={(e) => handleSubmit(e)}>
            <Input 
              placeholder="Ask for maintenance history, risk assessments, or SOPs..." 
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              disabled={isReasoning}
              className="bg-zinc-900 border-zinc-800 focus-visible:ring-emerald-500 text-zinc-100"
            />
            <Button type="submit" size="icon" disabled={isReasoning} className="bg-emerald-600 hover:bg-emerald-700 text-white shrink-0">
              <Send className="h-4 w-4" />
            </Button>
          </form>
        </div>
      </Card>
    </div>
  );
}
