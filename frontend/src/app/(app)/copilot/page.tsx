"use client";

/**
 * Copilot.
 *
 * One page with three modes, replacing the three near-identical pages
 * (`/copilot`, `/maintenance`, `/compliance`) that shared ~200 lines each and
 * differed only in labels. Mode now changes the model's system prompt, so the
 * answers genuinely differ rather than just the heading.
 *
 * Conversations are persisted server-side, so history survives a refresh.
 */

import { useSearchParams } from "next/navigation";
import {
  AlertCircle,
  Check,
  ChevronDown,
  Copy,
  FileText,
  Loader2,
  MessageSquarePlus,
  Network,
  PanelRightClose,
  PanelRightOpen,
  Send,
  Sparkles,
  Trash2,
} from "lucide-react";
import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { RiskPill } from "@/components/ui/status";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/contexts/AuthContext";
import { useAsync } from "@/hooks/use-async";
import { useResetOnChange } from "@/hooks/use-reset-on-change";
import {
  api,
  errorMessage,
  streamAsk,
  type ConversationSummary,
  type CopilotMode,
  type Decision,
  type TimelineEvent,
} from "@/lib/api";
import { formatRelativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";

interface Turn {
  id: string;
  role: "user" | "assistant";
  content: string;
  decision?: Decision | null;
  timeline?: TimelineEvent[];
  error?: string | null;
}

const MODES: {
  value: CopilotMode;
  label: string;
  blurb: string;
  examples: string[];
}[] = [
  {
    value: "general",
    label: "General",
    blurb: "Answer operational questions from your documents.",
    examples: [
      "What equipment is described in these documents?",
      "Summarise the startup procedure.",
      "Which components are connected to the main pump?",
    ],
  },
  {
    value: "maintenance",
    label: "Maintenance",
    blurb: "Failure modes, root cause, and corrective action.",
    examples: [
      "Why would the outboard bearing overheat?",
      "What failure modes are documented for this equipment?",
      "What inspection should follow a high-vibration alarm?",
    ],
  },
  {
    value: "compliance",
    label: "Compliance",
    blurb: "Procedures, documentation gaps, and audit findings.",
    examples: [
      "Which safety procedures are documented?",
      "Are there any gaps in the documented SOPs?",
      "What standards do these documents reference?",
    ],
  },
];

export default function CopilotPage() {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Loading…</div>}>
      <Copilot />
    </Suspense>
  );
}

function Copilot() {
  const searchParams = useSearchParams();
  const toast = useToast();
  const { activeWorkspace } = useAuth();
  const workspaceId = activeWorkspace?.id;

  const [mode, setMode] = useState<CopilotMode>("general");
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [liveTimeline, setLiveTimeline] = useState<TimelineEvent[]>([]);
  const [isAnswering, setIsAnswering] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<ConversationSummary | null>(null);
  const [lastQuestion, setLastQuestion] = useState("");

  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const conversations = useAsync(
    (signal) => api.listConversations(signal),
    [workspaceId],
    { enabled: Boolean(workspaceId) },
  );

  const activeMode = MODES.find((m) => m.value === mode) ?? MODES[0];

  // Switching workspace must not leave another workspace's thread on screen.
  useResetOnChange(workspaceId, () => {
    setTurns([]);
    setConversationId(null);
    setLiveTimeline([]);
  });

  // Keep the newest turn in view.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, liveTimeline, isAnswering]);

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  // `liveTimeline` is read inside stream callbacks that close over stale state;
  // a ref keeps the events collected so far available to them.
  const liveTimelineRef = useRef<TimelineEvent[]>([]);
  useEffect(() => {
    liveTimelineRef.current = liveTimeline;
  }, [liveTimeline]);

  const ask = useCallback(
    async (question: string) => {
      const trimmed = question.trim();
      if (!trimmed || isAnswering) return;

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setLastQuestion(trimmed);
      setInput("");
      setLiveTimeline([]);
      setIsAnswering(true);
      setTurns((current) => [
        ...current,
        { id: `u-${Date.now()}`, role: "user", content: trimmed },
      ]);

      let settled = false;

      await streamAsk(
        { query: trimmed, mode, conversation_id: conversationId },
        {
          onConversation: ({ conversation_id }) => setConversationId(conversation_id),
          onTimeline: (event) => setLiveTimeline((current) => [...current, event]),
          onDecision: ({ decision, message_id }) => {
            settled = true;
            setTurns((current) => [
              ...current,
              {
                id: message_id,
                role: "assistant",
                content: decision.executive_summary,
                decision,
                timeline: liveTimelineRef.current,
              },
            ]);
            void conversations.refresh();
          },
          onError: (message) => {
            settled = true;
            setTurns((current) => [
              ...current,
              {
                id: `e-${Date.now()}`,
                role: "assistant",
                content: "",
                error: message,
                timeline: liveTimelineRef.current,
              },
            ]);
          },
        },
        controller.signal,
      );

      // The stream can end without a terminal event if the connection drops.
      if (!settled && !controller.signal.aborted) {
        setTurns((current) => [
          ...current,
          {
            id: `e-${Date.now()}`,
            role: "assistant",
            content: "",
            error: "The connection ended before an answer arrived. Please try again.",
          },
        ]);
      }

      setIsAnswering(false);
      setLiveTimeline([]);
    },
    [conversationId, isAnswering, mode, conversations],
  );

  // Deep link from the command palette: /copilot?q=...
  const initialQuery = searchParams.get("q");
  const hasRunInitial = useRef(false);
  useEffect(() => {
    if (!initialQuery || hasRunInitial.current || !workspaceId) return;
    hasRunInitial.current = true;
    void ask(initialQuery);
  }, [initialQuery, workspaceId, ask]);

  const loadConversation = async (id: string) => {
    try {
      const detail = await api.getConversation(id);
      setConversationId(detail.id);
      setMode(detail.mode);
      setTurns(
        detail.messages.map((message) => ({
          id: message.id,
          role: message.role,
          content: message.content,
          decision: message.payload?.decision ?? null,
          timeline: message.payload?.reasoning_timeline ?? [],
          error: message.error,
        })),
      );
      setShowHistory(false);
    } catch (error) {
      toast.error("Could not open that conversation", { description: errorMessage(error) });
    }
  };

  const startNew = () => {
    abortRef.current?.abort();
    setConversationId(null);
    setTurns([]);
    setLiveTimeline([]);
    setIsAnswering(false);
    inputRef.current?.focus();
  };

  const deleteConversation = async () => {
    if (!pendingDelete) return;
    const target = pendingDelete;
    setPendingDelete(null);
    try {
      await api.deleteConversation(target.id);
      if (conversationId === target.id) startNew();
      await conversations.refresh();
      toast.success("Conversation deleted");
    } catch (error) {
      toast.error("Could not delete", { description: errorMessage(error) });
    }
  };

  const onSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    void ask(input);
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter sends; Shift+Enter inserts a newline.
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void ask(input);
    }
  };

  const history = conversations.data?.items ?? [];

  return (
    <div className="flex h-[calc(100dvh-3.5rem)]">
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mode selector + actions */}
        <div className="flex flex-wrap items-center gap-2 border-b px-4 py-2.5">
          <div
            role="radiogroup"
            aria-label="Copilot mode"
            className="flex gap-1 rounded-lg border p-0.5"
          >
            {MODES.map((option) => (
              <button
                key={option.value}
                type="button"
                role="radio"
                aria-checked={mode === option.value}
                onClick={() => setMode(option.value)}
                title={option.blurb}
                className={cn(
                  "rounded-md px-2.5 py-1.5 text-sm transition-colors",
                  mode === option.value
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground",
                )}
              >
                {option.label}
              </button>
            ))}
          </div>

          <p className="hidden text-xs text-muted-foreground lg:block">{activeMode.blurb}</p>

          <div className="ml-auto flex items-center gap-1.5">
            <Button variant="outline" size="sm" onClick={startNew} disabled={turns.length === 0}>
              <MessageSquarePlus className="size-3.5" />
              New
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => setShowHistory((open) => !open)}
              aria-label={showHistory ? "Hide history" : "Show history"}
              aria-expanded={showHistory}
            >
              {showHistory ? (
                <PanelRightClose className="size-4" />
              ) : (
                <PanelRightOpen className="size-4" />
              )}
            </Button>
          </div>
        </div>

        {/* Conversation */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto scrollbar-thin">
          <div className="mx-auto max-w-3xl space-y-5 px-4 py-5">
            {turns.length === 0 && !isAnswering && (
              <Welcome mode={activeMode} onPick={(example) => void ask(example)} />
            )}

            {turns.map((turn) =>
              turn.role === "user" ? (
                <UserBubble key={turn.id} content={turn.content} />
              ) : (
                <AssistantTurn
                  key={turn.id}
                  turn={turn}
                  onRetry={() => void ask(lastQuestion)}
                />
              ),
            )}

            {isAnswering && <Thinking events={liveTimeline} />}
          </div>
        </div>

        {/* Composer */}
        <div className="border-t bg-background px-4 py-3">
          <form onSubmit={onSubmit} className="mx-auto max-w-3xl">
            <label htmlFor="copilot-input" className="sr-only">
              Ask a question about your documents
            </label>
            <div className="flex items-end gap-2 rounded-xl border bg-card p-2 transition-colors focus-within:border-ring">
              <textarea
                id="copilot-input"
                ref={inputRef}
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={onKeyDown}
                rows={1}
                maxLength={4000}
                disabled={isAnswering}
                placeholder={`Ask about equipment, procedures, or failures…`}
                className="max-h-40 min-h-9 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none placeholder:text-muted-foreground disabled:opacity-60"
                // Grow with content up to the max height.
                onInput={(event) => {
                  const el = event.currentTarget;
                  el.style.height = "auto";
                  el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
                }}
              />
              <Button
                type="submit"
                size="icon"
                disabled={isAnswering || !input.trim()}
                aria-label="Send question"
              >
                {isAnswering ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Send className="size-4" />
                )}
              </Button>
            </div>
            <p className="mt-1.5 px-1 text-[11px] text-muted-foreground">
              AI drafts cite document passages. Check the original sources before acting.
              Press Enter to send, Shift+Enter for a new line.
            </p>
          </form>
        </div>
      </div>

      {/* History panel */}
      {showHistory && (
        <aside className="hidden w-72 shrink-0 flex-col border-l bg-card lg:flex">
          <div className="border-b px-4 py-3">
            <h2 className="text-sm font-semibold">History</h2>
          </div>
          <div className="flex-1 overflow-y-auto scrollbar-thin p-2">
            <HistoryList
              conversations={history}
              isLoading={conversations.isLoading}
              error={conversations.error}
              activeId={conversationId}
              onOpen={loadConversation}
              onDelete={setPendingDelete}
              onRetry={conversations.reload}
            />
          </div>
        </aside>
      )}

      {/* History drawer on small screens */}
      {showHistory && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-foreground/40 backdrop-blur-[2px]"
            onClick={() => setShowHistory(false)}
            aria-hidden
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Conversation history"
            className="absolute inset-y-0 right-0 flex w-72 max-w-[85vw] flex-col border-l bg-card shadow-md animate-in slide-in-from-right"
          >
            <div className="flex items-center justify-between border-b px-4 py-3">
              <h2 className="text-sm font-semibold">History</h2>
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={() => setShowHistory(false)}
                aria-label="Close history"
              >
                <PanelRightClose className="size-4" />
              </Button>
            </div>
            <div className="flex-1 overflow-y-auto scrollbar-thin p-2">
              <HistoryList
                conversations={history}
                isLoading={conversations.isLoading}
                error={conversations.error}
                activeId={conversationId}
                onOpen={loadConversation}
                onDelete={setPendingDelete}
                onRetry={conversations.reload}
              />
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title="Delete this conversation?"
        description={
          pendingDelete
            ? `"${pendingDelete.title}" and its messages will be permanently removed.`
            : ""
        }
        confirmLabel="Delete"
        destructive
        onConfirm={deleteConversation}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}

function Welcome({
  mode,
  onPick,
}: {
  mode: (typeof MODES)[number];
  onPick: (example: string) => void;
}) {
  return (
    <div className="py-10 text-center">
      <span
        className="mx-auto flex size-12 items-center justify-center rounded-full bg-primary/12 text-primary"
        aria-hidden
      >
        <Sparkles className="size-5" />
      </span>
      <h2 className="mt-3 text-base font-semibold">Ask about your documents</h2>
      <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">{mode.blurb}</p>

      <ul className="mx-auto mt-5 grid max-w-lg gap-2">
        {mode.examples.map((example) => (
          <li key={example}>
            <button
              type="button"
              onClick={() => onPick(example)}
              className="w-full rounded-lg border bg-card px-3.5 py-2.5 text-left text-sm transition-colors hover:border-primary/40 hover:bg-accent"
            >
              {example}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function UserBubble({ content }: { content: string }) {
  return (
    <div className="flex justify-end">
      <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-sm text-primary-foreground">
        {content}
      </p>
    </div>
  );
}

function AssistantTurn({ turn, onRetry }: { turn: Turn; onRetry: () => void }) {
  if (turn.error) {
    return (
      <ErrorState
        compact
        title="The Copilot could not answer"
        message={turn.error}
        onRetry={onRetry}
      />
    );
  }
  if (!turn.decision) return null;
  return <DecisionCard decision={turn.decision} timeline={turn.timeline ?? []} />;
}

function DecisionCard({
  decision,
  timeline,
}: {
  decision: Decision;
  timeline: TimelineEvent[];
}) {
  const toast = useToast();
  const [copied, setCopied] = useState(false);
  const [showReasoning, setShowReasoning] = useState(false);

  const plainText = useMemo(
    () =>
      [
        decision.executive_summary,
        decision.root_cause && `\nRoot cause: ${decision.root_cause}`,
        decision.recommended_action && `\nRecommended action: ${decision.recommended_action}`,
        decision.supporting_evidence.length
          ? `\nEvidence:\n${decision.supporting_evidence.map((e) => `- ${e}`).join("\n")}`
          : "",
      ]
        .filter(Boolean)
        .join("\n"),
    [decision],
  );

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(plainText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Could not copy to the clipboard");
    }
  };

  return (
    <article className="space-y-3 rounded-xl border bg-card p-4">
      <header className="flex flex-wrap items-center gap-2">
        {decision.risk_level && decision.evidence_status === "references_checked" && (
          <RiskPill risk={decision.risk_level} />
        )}
        <span className="tabular text-xs text-muted-foreground">
          AI draft: accuracy not independently verified
        </span>
        {decision.evidence_status !== "references_checked" && (
          <span className="flex items-center gap-1 rounded-full bg-warn-soft px-2 py-0.5 text-xs text-warn">
            <AlertCircle className="size-3" aria-hidden />
            Insufficient cited evidence
          </span>
        )}
        <Button variant="ghost" size="icon-sm" onClick={copy} className="ml-auto" aria-label="Copy answer">
          {copied ? <Check className="size-3.5 text-ok" /> : <Copy className="size-3.5" />}
        </Button>
      </header>

      <p className="text-sm leading-relaxed">{decision.executive_summary}</p>

      {decision.root_cause && (
        <Section title="Root cause" body={decision.root_cause} />
      )}
      {decision.recommended_action && (
        <Section title="Recommended action" body={decision.recommended_action} />
      )}
      {decision.business_impact && (
        <Section title="Impact" body={decision.business_impact} />
      )}

      {decision.supporting_evidence.length > 0 && (
        <div className="space-y-1.5">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Evidence
          </h3>
          <ul className="space-y-1.5">
            {decision.supporting_evidence.map((item, index) => (
              <li
                key={index}
                className="border-l-2 border-primary/40 pl-2.5 text-sm text-muted-foreground"
              >
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}

      {decision.citations.length > 0 && (
        <div className="space-y-1.5 border-t pt-3">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Sources ({decision.citations.length})
          </h3>
          <ul className="flex flex-wrap gap-1.5">
            {decision.citations.slice(0, 8).map((citation, index) => (
              <li
                key={index}
                title={citation.snippet ?? citation.relation ?? undefined}
                className="flex max-w-full items-center gap-1.5 rounded-md border bg-background px-2 py-1 text-xs"
              >
                {citation.kind === "graph" ? (
                  <Network className="size-3 shrink-0 text-muted-foreground" aria-hidden />
                ) : (
                  <FileText className="size-3 shrink-0 text-muted-foreground" aria-hidden />
                )}
                <span className="truncate">
                  {citation.document_title ?? citation.relation ?? "Source"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {timeline.length > 0 && (
        <div className="border-t pt-2">
          <button
            type="button"
            onClick={() => setShowReasoning((open) => !open)}
            aria-expanded={showReasoning}
            className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            <ChevronDown
              className={cn("size-3.5 transition-transform", showReasoning && "rotate-180")}
              aria-hidden
            />
            How this answer was produced ({timeline.length} steps)
          </button>

          {showReasoning && (
            <ol className="mt-2.5 space-y-2">
              {timeline.map((event, index) => (
                <li key={index} className="flex gap-2.5 text-xs">
                  <span
                    className={cn(
                      "mt-1 size-1.5 shrink-0 rounded-full",
                      event.status === "failed"
                        ? "bg-danger"
                        : event.status === "skipped"
                          ? "bg-muted-foreground"
                          : "bg-ok",
                    )}
                    aria-hidden
                  />
                  <div className="min-w-0">
                    <p className="font-medium">
                      {event.agent_name}
                      <span className="ml-1.5 font-normal text-muted-foreground">
                        {event.action} Â· {Math.round(event.duration_ms)}ms
                      </span>
                    </p>
                    <p className="text-muted-foreground">{event.summary}</p>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </article>
  );
}

function Section({ title, body }: { title: string; body: string }) {
  return (
    <div className="space-y-1">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </h3>
      <p className="text-sm leading-relaxed">{body}</p>
    </div>
  );
}

/** Live agent progress while the answer is being produced. */
function Thinking({ events }: { events: TimelineEvent[] }) {
  const latest = events[events.length - 1];
  return (
    <div
      role="status"
      aria-live="polite"
      className="space-y-2 rounded-xl border border-dashed bg-card/50 p-4"
    >
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" aria-hidden />
        {latest ? `${latest.agent_name}: ${latest.action}` : "Retrieving evidence…"}
      </p>
      {events.length > 0 && (
        <ol className="space-y-1 pl-6">
          {events.map((event, index) => (
            <li key={index} className="text-xs text-muted-foreground">
              {event.summary}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function HistoryList({
  conversations,
  isLoading,
  error,
  activeId,
  onOpen,
  onDelete,
  onRetry,
}: {
  conversations: ConversationSummary[];
  isLoading: boolean;
  error: string | null;
  activeId: string | null;
  onOpen: (id: string) => void;
  onDelete: (conversation: ConversationSummary) => void;
  onRetry: () => void;
}) {
  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, index) => (
          <div key={index} className="h-12 animate-pulse rounded-lg bg-muted" />
        ))}
      </div>
    );
  }
  if (error) return <ErrorState compact message={error} onRetry={onRetry} />;
  if (conversations.length === 0) {
    return (
      <EmptyState
        compact
        icon={MessageSquarePlus}
        title="No conversations yet"
        description="Your questions are saved here automatically."
      />
    );
  }

  return (
    <ul className="space-y-0.5">
      {conversations.map((conversation) => (
        <li key={conversation.id} className="group relative">
          <button
            type="button"
            onClick={() => onOpen(conversation.id)}
            className={cn(
              "w-full rounded-lg px-2.5 py-2 pr-9 text-left transition-colors hover:bg-accent",
              activeId === conversation.id && "bg-accent",
            )}
          >
            <span className="block truncate text-sm">{conversation.title}</span>
            <span className="block truncate text-xs text-muted-foreground">
              {conversation.mode} Â· {formatRelativeTime(conversation.updated_at)}
            </span>
          </button>
          <button
            type="button"
            onClick={() => onDelete(conversation)}
            aria-label={`Delete "${conversation.title}"`}
            className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-muted-foreground opacity-0 transition-opacity hover:bg-danger-soft hover:text-danger focus-visible:opacity-100 group-hover:opacity-100"
          >
            <Trash2 className="size-3.5" />
          </button>
        </li>
      ))}
    </ul>
  );
}
