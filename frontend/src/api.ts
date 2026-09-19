// API wrappers for every backend route (team/CONTRACTS.md §7). Adarsh owns this file.

import type {
  ChatMessage,
  CaseDetail,
  CaseSummary,
  HealthInfo,
  Metrics,
  ReviewPayload,
  RunEvent,
  RunListItem,
  RunRecord,
  StartRunResponse,
} from "./types";

const BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "") ?? "";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, init);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      // keep statusText
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

function jsonInit(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

// Health -----------------------------------------------------------------------

export function getHealth(): Promise<HealthInfo> {
  return request<HealthInfo>("/api/health");
}

// Cases ------------------------------------------------------------------------

export function getCases(): Promise<CaseSummary[]> {
  return request<CaseSummary[]>("/api/cases");
}

export function getCase(caseId: string): Promise<CaseDetail> {
  return request<CaseDetail>(`/api/cases/${encodeURIComponent(caseId)}`);
}

// Runs -------------------------------------------------------------------------

export async function startRun(input: {
  caseId?: string;
  text?: string;
  file?: File | null;
}): Promise<StartRunResponse> {
  const form = new FormData();
  if (input.caseId) form.append("case_id", input.caseId);
  if (input.text?.trim()) form.append("text", input.text.trim());
  if (input.file) form.append("file", input.file);
  return request<StartRunResponse>("/api/runs", { method: "POST", body: form });
}

export function listRuns(): Promise<RunListItem[]> {
  return request("/api/runs");
}

export function getRun(runId: string): Promise<RunRecord> {
  return request<RunRecord>(`/api/runs/${encodeURIComponent(runId)}`);
}

// SSE — returns a stop() function; tracks the last index so events are not duplicated.

export function subscribeRunEvents(
  runId: string,
  handlers: {
    onEvent: (event: RunEvent) => void;
    onStatus: (status: string) => void;
    onDone?: () => void;
    onError?: (error: unknown) => void;
  },
): () => void {
  const controller = new AbortController();
  const seen = new Set<string>();
  let closed = false;

  (async () => {
    try {
      const response = await fetch(`${BASE}/api/runs/${encodeURIComponent(runId)}/events`, {
        signal: controller.signal,
        headers: { Accept: "text/event-stream" },
      });
      if (!response.ok || !response.body) throw new ApiError(response.status, "SSE failed");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (!closed) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let boundary = buffer.indexOf("\n\n");
        while (boundary !== -1) {
          const rawEvent = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          boundary = buffer.indexOf("\n\n");

          let eventName = "message";
          const dataLines: string[] = [];
          for (const line of rawEvent.split("\n")) {
            if (line.startsWith("event:")) eventName = line.slice(6).trim();
            else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
          }
          if (!dataLines.length) continue;

          try {
            const data = JSON.parse(dataLines.join("\n"));
            if (eventName === "agent" && data.agent !== undefined) {
              const key = `${data.timestamp ?? ""}|${data.agent}|${data.decision}`;
              if (seen.has(key)) continue; // never duplicate an agent event
              seen.add(key);
              handlers.onEvent(data);
            } else if (eventName === "status") {
              handlers.onStatus(data.status);
            } else if (eventName === "done") {
              handlers.onDone?.();
            }
          } catch {
            // ignore malformed frames
          }
        }
      }
    } catch (error) {
      if (!closed) handlers.onError?.(error);
    }
  })();

  return () => {
    closed = true;
    controller.abort();
  };
}

// Review + chat ----------------------------------------------------------------

export function submitReview(runId: string, payload: ReviewPayload): Promise<{ run_id: string; status: string }> {
  return request(`/api/runs/${encodeURIComponent(runId)}/review`, jsonInit("POST", payload));
}

export function sendChat(runId: string, message: string): Promise<{ reply: string; chat_history: ChatMessage[] }> {
  return request(`/api/runs/${encodeURIComponent(runId)}/chat`, jsonInit("POST", { message }));
}

// Metrics + RAG ----------------------------------------------------------------

export function getMetrics(): Promise<Metrics> {
  return request<Metrics>("/api/metrics");
}

export function reindexRag(): Promise<{ chunks: number; embedded: number }> {
  return request("/api/rag/reindex", { method: "POST" });
}
