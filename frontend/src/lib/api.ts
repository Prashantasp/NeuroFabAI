// API Client for NeuroFab AI Backend

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export interface DocumentResponse {
  id: string;
  filename: string;
  status: string;
  uploaded_at: string;
  processed_at: string | null;
  processing_duration: number | null;
  failure_stage: string | null;
  error_message: string | null;
}

export interface GraphStats {
  total_nodes: number;
  total_relationships: number;
  entity_type_counts: Record<string, number>;
  relationship_type_counts: Record<string, number>;
  last_updated?: string;
}

export interface ReasoningTimelineEvent {
  timestamp: string;
  agent_name: string;
  action: string;
  duration_ms: number;
  summary: string;
  evidence_generated: number;
}

export interface DecisionResponse {
  executive_summary: string;
  root_cause: string;
  supporting_evidence: string[];
  recommended_action: string;
  business_impact: string;
  risk_level: string;
  confidence: number;
  citations: any[];
}

export interface ChatResponse {
  decision: DecisionResponse | null;
  reasoning_timeline: ReasoningTimelineEvent[];
  errors: string[];
}

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function fetchWithRetry(url: string, options: RequestInit, retries = 2): Promise<Response> {
  let lastError;
  
  for (let i = 0; i <= retries; i++) {
    try {
      const response = await fetch(url, { ...options, signal: AbortSignal.timeout(60000) });
      if (!response.ok) {
        throw new ApiError(response.status, `HTTP error ${response.status}`);
      }
      return response;
    } catch (err: any) {
      lastError = err;
      if (err.name === 'AbortError' || (err instanceof ApiError && err.status < 500)) {
        throw err; // Don't retry client errors or explicit aborts
      }
      // Wait before retrying
      if (i < retries) await new Promise(r => setTimeout(r, 1000 * (i + 1)));
    }
  }
  throw lastError;
}

export const api = {
  async getDocuments(): Promise<DocumentResponse[]> {
    const res = await fetchWithRetry(`${BASE_URL}/documents/`, { method: 'GET' });
    return res.json();
  },

  async uploadDocument(file: File): Promise<DocumentResponse> {
    const formData = new FormData();
    formData.append('file', file);
    
    // No retries for file uploads to avoid duplicate submissions
    const res = await fetch(`${BASE_URL}/documents/upload/`, {
      method: 'POST',
      body: formData,
      signal: AbortSignal.timeout(120000) // 2 min timeout for upload
    });
    
    if (!res.ok) {
      const errorText = await res.text();
      throw new ApiError(res.status, `Upload failed: ${errorText}`);
    }
    return res.json();
  },

  async getGraphStats(): Promise<GraphStats> {
    const res = await fetchWithRetry(`${BASE_URL}/graph/stats`, { method: 'GET' });
    return res.json();
  },

  async getGraphTopology(): Promise<{ nodes: any[]; edges: any[] }> {
    const res = await fetchWithRetry(`${BASE_URL}/graph/topology`, { method: 'GET' });
    return res.json();
  },

  async askCopilot(query: string): Promise<ChatResponse> {
    const res = await fetchWithRetry(`${BASE_URL}/chat/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    }, 0); // No retries for chat to avoid duplicate processing
    return res.json();
  }
};
