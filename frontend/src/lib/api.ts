/**
 * NeuroFab AI API client.
 *
 * Two things are deliberate here:
 *
 * 1. The access token lives in a module-level variable, never in localStorage.
 *    A token in localStorage is readable by any script on the page, so a single
 *    XSS turns into a stolen session. On reload the token is re-obtained from
 *    the HttpOnly refresh cookie, which JavaScript cannot read.
 * 2. Every response is unwrapped from the `{success, data, error}` envelope in
 *    one place, so callers deal in domain objects and `ApiError`, never in
 *    response shapes.
 */

const DEFAULT_API_PORT = "8000";

/**
 * Resolve the API base URL.
 *
 * When `NEXT_PUBLIC_API_URL` is not set, the host is taken from the page rather
 * than hardcoded to `localhost`. `localhost` and `127.0.0.1` are *different
 * sites* to a browser, so a page served from one calling an API on the other
 * makes the `SameSite=Lax` refresh cookie cross-site: the browser silently
 * discards it and every login appears to succeed then immediately bounce back
 * to the sign-in page.
 */
function resolveBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (configured) return configured.replace(/\/$/, "");

  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:${DEFAULT_API_PORT}/api/v1`;
  }
  return `http://localhost:${DEFAULT_API_PORT}/api/v1`;
}

let cachedBaseUrl: string | null = null;

function baseUrl(): string {
  // Resolved lazily and memoised: at module-eval time on the server there is no
  // `window` to read the hostname from.
  cachedBaseUrl ??= resolveBaseUrl();
  return cachedBaseUrl;
}

const DEFAULT_TIMEOUT_MS = 30_000;
const UPLOAD_TIMEOUT_MS = 180_000;
const COPILOT_TIMEOUT_MS = 120_000;

/* -------------------------------------------------------------------------- */
/* Types                                                                       */
/* -------------------------------------------------------------------------- */

export type WorkspaceRole = "OWNER" | "ADMIN" | "MEMBER" | "VIEWER";

export type DocumentStatus =
  | "UPLOADING"
  | "QUEUED"
  | "VALIDATING"
  | "TEXT_EXTRACTION"
  | "CHUNKING"
  | "EMBEDDING"
  | "VECTOR_INDEXING"
  | "KNOWLEDGE_GRAPH"
  | "READY"
  | "FAILED"
  | "ARCHIVED";

export type StageStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "SKIPPED";

export type RiskLevel = "Low" | "Medium" | "High" | "Critical";

export type CopilotMode = "general" | "maintenance" | "compliance";

export interface User {
  id: string;
  email: string;
  username: string | null;
  full_name: string | null;
  company: string | null;
  role: string;
  is_active: boolean;
  is_verified: boolean;
  avatar_url: string | null;
  last_login: string | null;
  last_workspace_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface Workspace {
  id: string;
  name: string;
  description: string | null;
  owner_id: string;
  created_at: string;
  updated_at: string;
  role: WorkspaceRole | null;
  member_count: number;
  document_count: number;
}

export interface WorkspaceMember {
  user_id: string;
  email: string;
  full_name: string | null;
  role: WorkspaceRole;
  joined_at: string;
}

export interface Document {
  id: string;
  workspace_id: string;
  owner_id: string;
  title: string;
  filename: string;
  file_size: number;
  mime_type: string;
  checksum: string;
  version: number;
  page_count: number | null;
  status: DocumentStatus;
  embedding_status: StageStatus;
  graph_status: StageStatus;
  current_stage: string | null;
  progress_percentage: number;
  failure_reason: string | null;
  failure_stage: string | null;
  error_message: string | null;
  retryable: boolean;
  retry_count: number;
  uploaded_at: string;
  started_at: string | null;
  completed_at: string | null;
  processed_at: string | null;
  processing_duration: number | null;
  summary: string | null;
  chunk_count: number;
  entity_count: number;
  relationship_count: number;
  metadata_json: Record<string, unknown>;
}

export interface DocumentStats {
  total: number;
  ready: number;
  failed: number;
  processing: number;
  by_status: Record<string, number>;
  total_chunks: number;
  avg_processing_seconds: number;
  total_bytes: number;
}

export interface GraphStats {
  total_nodes: number;
  total_relationships: number;
  entity_type_counts: Record<string, number>;
  relationship_type_counts: Record<string, number>;
}

export interface GraphNode {
  id: string;
  name: string;
  canonical_name: string;
  raw_name: string;
  type: string;
  group: string;
  confidence: number;
  confidence_label: string;
  source_document_id: string;
  evidence_snippet: string;
  page_number: number | null;
  properties: Record<string, unknown>;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
  label: string;
  confidence: number;
  evidence: string;
  source_document_id: string;
  page_number: number | null;
}

export interface GraphTopology {
  nodes: GraphNode[];
  edges: GraphEdge[];
  truncated: boolean;
  total_nodes: number;
}

export interface Citation {
  document_id: string | null;
  document_title: string | null;
  kind: "semantic" | "graph";
  snippet: string | null;
  relation: string | null;
  page_number: number | null;
}

export interface TimelineEvent {
  timestamp: string;
  agent_name: string;
  action: string;
  duration_ms: number;
  summary: string;
  evidence_generated: number;
  status: "ok" | "failed" | "skipped";
}

export interface Decision {
  executive_summary: string;
  root_cause: string;
  supporting_evidence: string[];
  recommended_action: string;
  business_impact: string;
  risk_level: RiskLevel | null;
  confidence: number | null;
  evidence_status?: "references_checked" | "insufficient";
  citations: Citation[];
  grounded: boolean;
}

export interface AskResult {
  conversation_id: string;
  conversation_title: string;
  message_id: string;
  decision: Decision;
  reasoning_timeline: TimelineEvent[];
  errors: string[];
}

export interface ConversationSummary {
  id: string;
  title: string;
  mode: CopilotMode;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  payload: {
    decision?: Decision | null;
    reasoning_timeline?: TimelineEvent[];
    errors?: string[];
    mode?: CopilotMode;
  };
  error: string | null;
  created_at: string;
}

export interface ConversationDetail extends ConversationSummary {
  messages: ChatMessage[];
}

export interface SearchResult {
  id: string;
  score: number;
  source: "keyword" | "semantic" | "graph" | "hybrid";
  title: string;
  snippet: string;
  document_id: string | null;
  payload: Record<string, unknown>;
}

export interface SystemComponent {
  name: string;
  online: boolean;
  detail: string;
}

export interface SystemStatus {
  environment: string;
  version: string;
  components: SystemComponent[];
  all_online: boolean;
  models: {
    reasoning: string | null;
    embedding: string | null;
    embedding_dimension: number;
  };
}

export interface Paginated<T> {
  items: T[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

interface Envelope<T> {
  success: boolean;
  data: T | null;
  error?: { code: string; message: string; details?: unknown } | null;
}

export interface FieldError {
  field: string;
  message: string;
}

/* -------------------------------------------------------------------------- */
/* Errors                                                                      */
/* -------------------------------------------------------------------------- */

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code = "ERROR",
    public fieldErrors: FieldError[] = [],
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** True when retrying the same request could plausibly succeed. */
  get isRetryable(): boolean {
    return this.status === 0 || this.status === 429 || this.status >= 500;
  }

  get isAuthError(): boolean {
    return this.status === 401;
  }
}

/** Turn any thrown value into a message safe to render. */
export function errorMessage(error: unknown, fallback = "Something went wrong."): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof DOMException && error.name === "AbortError") {
    return "The request timed out. Please try again.";
  }
  if (error instanceof TypeError) {
    return "Could not reach the NeuroFab server. Check your connection and try again.";
  }
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

/* -------------------------------------------------------------------------- */
/* Session state                                                               */
/* -------------------------------------------------------------------------- */

let accessToken: string | null = null;
let activeWorkspaceId: string | null = null;

/** Coalesces concurrent 401s into a single refresh call. */
let refreshInFlight: Promise<string> | null = null;

type AuthExpiredHandler = () => void;
let onAuthExpired: AuthExpiredHandler | null = null;

export function setAuthExpiredHandler(handler: AuthExpiredHandler | null): void {
  onAuthExpired = handler;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function setActiveWorkspaceId(id: string | null): void {
  activeWorkspaceId = id;
  if (typeof window === "undefined") return;
  // Only the workspace *selection* is persisted, never a credential.
  if (id) window.localStorage.setItem("neurofab.workspace", id);
  else window.localStorage.removeItem("neurofab.workspace");
}

export function getActiveWorkspaceId(): string | null {
  if (activeWorkspaceId) return activeWorkspaceId;
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("neurofab.workspace");
}

/* -------------------------------------------------------------------------- */
/* Transport                                                                   */
/* -------------------------------------------------------------------------- */

function buildHeaders(init: RequestInit, includeWorkspace: boolean): Headers {
  const headers = new Headers(init.headers);
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

  if (includeWorkspace) {
    const workspaceId = getActiveWorkspaceId();
    if (workspaceId) headers.set("X-Workspace-ID", workspaceId);
  }
  return headers;
}

async function readEnvelope<T>(response: Response): Promise<Envelope<T> | null> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as Envelope<T>;
  } catch {
    return null;
  }
}

async function toApiError(response: Response): Promise<ApiError> {
  const envelope = await readEnvelope<unknown>(response);
  const error = envelope?.error;
  const fieldErrors = Array.isArray(error?.details)
    ? (error?.details as FieldError[]).filter((d) => d && typeof d.message === "string")
    : [];
  return new ApiError(
    response.status,
    error?.message ?? `Request failed (${response.status})`,
    error?.code ?? "ERROR",
    fieldErrors,
  );
}

async function refreshAccessToken(): Promise<string> {
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    try {
      const response = await fetch(`${baseUrl()}/auth/refresh`, {
        method: "POST",
        credentials: "include",
        signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
      });
      if (!response.ok) throw await toApiError(response);

      const envelope = await readEnvelope<{ access_token: string }>(response);
      const token = envelope?.data?.access_token;
      if (!token) throw new ApiError(401, "Session expired. Please sign in again.");

      accessToken = token;
      return token;
    } catch (error) {
      accessToken = null;
      onAuthExpired?.();
      throw error;
    } finally {
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
}

interface RequestOptions extends RequestInit {
  timeoutMs?: number;
  includeWorkspace?: boolean;
  /** Skip the automatic refresh-and-retry on 401. */
  skipAuthRetry?: boolean;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const {
    timeoutMs = DEFAULT_TIMEOUT_MS,
    includeWorkspace = true,
    skipAuthRetry = false,
    ...init
  } = options;

  const send = async (): Promise<Response> => {
    // A caller-supplied signal wins; otherwise every request is bounded so a
    // hung backend cannot leave the UI spinning forever.
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      return await fetch(`${baseUrl()}${path}`, {
        ...init,
        headers: buildHeaders(init, includeWorkspace),
        credentials: "include",
        signal: init.signal ?? controller.signal,
      });
    } finally {
      clearTimeout(timer);
    }
  };

  let response: Response;
  try {
    response = await send();
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "Could not reach the NeuroFab server.", "NETWORK_ERROR");
  }

  if (response.status === 401 && !skipAuthRetry) {
    await refreshAccessToken(); // throws (and signals expiry) if it cannot recover
    try {
      response = await send();
    } catch {
      throw new ApiError(0, "Could not reach the NeuroFab server.", "NETWORK_ERROR");
    }
  }

  if (!response.ok) throw await toApiError(response);

  if (response.status === 204) return undefined as T;

  const envelope = await readEnvelope<T>(response);
  if (!envelope) throw new ApiError(response.status, "The server returned an unreadable response.");
  if (envelope.success === false) {
    throw new ApiError(
      response.status,
      envelope.error?.message ?? "Request failed.",
      envelope.error?.code,
    );
  }
  return envelope.data as T;
}

function json(body: unknown): RequestInit {
  return { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

function query(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const encoded = search.toString();
  return encoded ? `?${encoded}` : "";
}

/* -------------------------------------------------------------------------- */
/* API surface                                                                 */
/* -------------------------------------------------------------------------- */

export const api = {
  /* --- auth --------------------------------------------------------------- */

  async login(email: string, password: string): Promise<string> {
    const data = await request<{ access_token: string }>("/auth/login", {
      method: "POST",
      ...json({ email, password }),
      includeWorkspace: false,
      skipAuthRetry: true,
    });
    accessToken = data.access_token;
    return data.access_token;
  },

  register(payload: {
    email: string;
    password: string;
    full_name?: string;
    company?: string;
  }): Promise<User> {
    return request<User>("/auth/register", {
      method: "POST",
      ...json(payload),
      includeWorkspace: false,
      skipAuthRetry: true,
    });
  },

  /** Ask the API to validate its HttpOnly cookie, including across app/API hosts. */
  restoreSession(): Promise<string> {
    return refreshAccessToken();
  },

  async logout(): Promise<void> {
    try {
      await request<{ message: string }>("/auth/logout", {
        method: "POST",
        includeWorkspace: false,
        skipAuthRetry: true,
      });
    } finally {
      // Local state is cleared even if the server call fails, so the UI never
      // shows a signed-in shell after the user asked to leave.
      accessToken = null;
      setActiveWorkspaceId(null);
    }
  },

  me(): Promise<User> {
    return request<User>("/auth/me", { includeWorkspace: false });
  },

  updateProfile(payload: {
    full_name?: string;
    company?: string;
    username?: string;
  }): Promise<User> {
    return request<User>("/users/me", {
      method: "PATCH",
      ...json(payload),
      includeWorkspace: false,
    });
  },

  changePassword(current_password: string, new_password: string): Promise<{ message: string }> {
    return request<{ message: string }>("/users/me/password", {
      method: "POST",
      ...json({ current_password, new_password }),
      includeWorkspace: false,
    });
  },

  rememberWorkspace(workspaceId: string): Promise<User> {
    return request<User>(`/users/me/workspace/${workspaceId}`, {
      method: "PATCH",
      includeWorkspace: false,
    });
  },

  /* --- workspaces --------------------------------------------------------- */

  listWorkspaces(): Promise<Workspace[]> {
    return request<Workspace[]>("/workspaces", { includeWorkspace: false });
  },

  createWorkspace(payload: { name: string; description?: string }): Promise<Workspace> {
    return request<Workspace>("/workspaces", {
      method: "POST",
      ...json(payload),
      includeWorkspace: false,
    });
  },

  getActiveWorkspace(): Promise<Workspace> {
    return request<Workspace>("/workspaces/active");
  },

  updateWorkspace(payload: { name?: string; description?: string }): Promise<Workspace> {
    return request<Workspace>("/workspaces/active", { method: "PATCH", ...json(payload) });
  },

  deleteWorkspace(): Promise<{ message: string }> {
    return request<{ message: string }>("/workspaces/active", { method: "DELETE" });
  },

  listMembers(): Promise<WorkspaceMember[]> {
    return request<WorkspaceMember[]>("/workspaces/active/members");
  },

  addMember(email: string, role: WorkspaceRole): Promise<WorkspaceMember> {
    return request<WorkspaceMember>("/workspaces/active/members", {
      method: "POST",
      ...json({ email, role }),
    });
  },

  updateMemberRole(userId: string, role: WorkspaceRole): Promise<{ message: string }> {
    return request<{ message: string }>(`/workspaces/active/members/${userId}`, {
      method: "PATCH",
      ...json({ role }),
    });
  },

  removeMember(userId: string): Promise<{ message: string }> {
    return request<{ message: string }>(`/workspaces/active/members/${userId}`, {
      method: "DELETE",
    });
  },

  /* --- documents ---------------------------------------------------------- */

  listDocuments(params: {
    page?: number;
    page_size?: number;
    search?: string;
    status?: DocumentStatus;
    sort?: string;
    order?: "asc" | "desc";
    signal?: AbortSignal;
  } = {}): Promise<Paginated<Document>> {
    const { signal, ...rest } = params;
    return request<Paginated<Document>>(`/documents${query(rest)}`, { signal });
  },

  documentStats(signal?: AbortSignal): Promise<DocumentStats> {
    return request<DocumentStats>("/documents/stats", { signal });
  },

  getDocument(id: string): Promise<Document & { extracted_knowledge: Record<string, unknown> }> {
    return request(`/documents/${id}`);
  },

  async uploadDocument(file: File, title?: string): Promise<Document> {
    const form = new FormData();
    form.append("file", file);
    if (title) form.append("title", title);
    // No Content-Type header: the browser must set the multipart boundary.
    return request<Document>("/documents/upload", {
      method: "POST",
      body: form,
      timeoutMs: UPLOAD_TIMEOUT_MS,
    });
  },

  reprocessDocument(id: string): Promise<Document> {
    return request<Document>(`/documents/${id}/reprocess`, { method: "POST" });
  },

  deleteDocument(id: string): Promise<{ message: string }> {
    return request<{ message: string }>(`/documents/${id}`, { method: "DELETE" });
  },

  /** Download URL is not a plain link: the request must carry the bearer token. */
  async downloadDocument(id: string, filename: string): Promise<void> {
    const response = await fetch(`${baseUrl()}/documents/${id}/download`, {
      headers: buildHeaders({}, true),
      credentials: "include",
    });
    if (!response.ok) throw await toApiError(response);

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = window.document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    window.document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  },

  /* --- graph -------------------------------------------------------------- */

  graphStats(signal?: AbortSignal): Promise<GraphStats> {
    return request<GraphStats>("/graph/stats", { signal });
  },

  graphTopology(signal?: AbortSignal): Promise<GraphTopology> {
    return request<GraphTopology>("/graph/topology", { signal });
  },

  graphNode(nodeId: string, depth = 1): Promise<{
    node: GraphNode;
    subgraph: { nodes: GraphNode[]; edges: GraphEdge[] };
  }> {
    return request(`/graph/nodes/${encodeURIComponent(nodeId)}${query({ depth })}`);
  },

  /* --- search ------------------------------------------------------------- */

  search(payload: {
    query: string;
    strategy?: SearchResult["source"];
    limit?: number;
    signal?: AbortSignal;
  }): Promise<SearchResult[]> {
    const { signal, ...body } = payload;
    return request<SearchResult[]>("/search", { method: "POST", ...json(body), signal });
  },

  /* --- copilot ------------------------------------------------------------ */

  ask(payload: {
    query: string;
    mode?: CopilotMode;
    conversation_id?: string | null;
    signal?: AbortSignal;
  }): Promise<AskResult> {
    const { signal, conversation_id, ...rest } = payload;
    return request<AskResult>("/chat/ask", {
      method: "POST",
      ...json({ ...rest, conversation_id: conversation_id ?? null }),
      timeoutMs: COPILOT_TIMEOUT_MS,
      signal,
    });
  },

  listConversations(signal?: AbortSignal): Promise<Paginated<ConversationSummary>> {
    return request<Paginated<ConversationSummary>>("/chat/conversations", { signal });
  },

  getConversation(id: string, signal?: AbortSignal): Promise<ConversationDetail> {
    return request<ConversationDetail>(`/chat/conversations/${id}`, { signal });
  },

  renameConversation(id: string, title: string): Promise<ConversationSummary> {
    return request<ConversationSummary>(`/chat/conversations/${id}`, {
      method: "PATCH",
      ...json({ title }),
    });
  },

  deleteConversation(id: string): Promise<{ message: string }> {
    return request<{ message: string }>(`/chat/conversations/${id}`, { method: "DELETE" });
  },

  /* --- system ------------------------------------------------------------- */

  systemStatus(signal?: AbortSignal): Promise<SystemStatus> {
    return request<SystemStatus>("/health/status", { includeWorkspace: false, signal });
  },
};

/* -------------------------------------------------------------------------- */
/* Copilot streaming                                                           */
/* -------------------------------------------------------------------------- */

export interface StreamHandlers {
  onConversation?: (data: { conversation_id: string; title: string }) => void;
  onTimeline?: (event: TimelineEvent) => void;
  onDecision?: (data: {
    conversation_id: string;
    conversation_title: string;
    message_id: string;
    decision: Decision;
    errors: string[];
  }) => void;
  onError?: (message: string) => void;
}

/**
 * Consume the Copilot SSE stream.
 *
 * `fetch` rather than `EventSource` because the request needs an Authorization
 * header and a POST body, neither of which EventSource supports.
 */
export async function streamAsk(
  payload: { query: string; mode?: CopilotMode; conversation_id?: string | null },
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const run = async (): Promise<Response> =>
    fetch(`${baseUrl()}/chat/stream`, {
      method: "POST",
      headers: (() => {
        const headers = buildHeaders({}, true);
        headers.set("Content-Type", "application/json");
        headers.set("Accept", "text/event-stream");
        return headers;
      })(),
      credentials: "include",
      body: JSON.stringify({ ...payload, conversation_id: payload.conversation_id ?? null }),
      signal,
    });

  let response: Response;
  try {
    response = await run();
    if (response.status === 401) {
      await refreshAccessToken();
      response = await run();
    }
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") return;
    handlers.onError?.("Could not reach the NeuroFab server.");
    return;
  }

  if (!response.ok || !response.body) {
    handlers.onError?.((await toApiError(response)).message);
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE frames are separated by a blank line. A frame may arrive split
      // across chunks, so only complete frames are consumed.
      let separator = buffer.indexOf("\n\n");
      while (separator !== -1) {
        dispatchFrame(buffer.slice(0, separator), handlers);
        buffer = buffer.slice(separator + 2);
        separator = buffer.indexOf("\n\n");
      }
    }
  } catch (error) {
    if (!(error instanceof DOMException && error.name === "AbortError")) {
      handlers.onError?.("The connection was interrupted. Please try again.");
    }
  } finally {
    reader.releaseLock();
  }
}

function dispatchFrame(frame: string, handlers: StreamHandlers): void {
  let event = "message";
  const dataLines: string[] = [];

  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return;

  let data: unknown;
  try {
    data = JSON.parse(dataLines.join("\n"));
  } catch {
    return; // a malformed frame must not tear down the stream
  }

  switch (event) {
    case "conversation":
      handlers.onConversation?.(data as { conversation_id: string; title: string });
      break;
    case "timeline":
      handlers.onTimeline?.(data as TimelineEvent);
      break;
    case "decision":
      handlers.onDecision?.(data as Parameters<NonNullable<StreamHandlers["onDecision"]>>[0]);
      break;
    case "error":
      handlers.onError?.((data as { message?: string }).message ?? "The AI could not answer.");
      break;
    default:
      break;
  }
}
