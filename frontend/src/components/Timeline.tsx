// Timeline of agent events — agent name + decision per row.

import type { RunEvent } from "../types";

const AGENT_LABELS: Record<string, string> = {
  ingest: "Ingest",
  router: "Router",
  urgent_safety: "Urgent safety",
  fanout: "Fanout",
  analysis: "Analysis",
  labs: "Labs",
  rag: "Guideline retrieval",
  synthesize: "Synthesize",
  summary: "Summary",
  recommendation: "Recommendations",
  safety: "Safety",
  hitl_review: "HITL review",
  clinician: "Clinician",
  finalize: "Finalize",
};

const ACTIVE_DECISIONS = new Set(["running", "parallel_start", "stub"]);

function formatTime(timestamp?: string): string {
  if (!timestamp) return "";
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime()) ? timestamp : date.toLocaleTimeString();
}

export default function Timeline({ events }: { events: RunEvent[] }) {
  if (!events.length) {
    return <p className="text-sm text-slate-500">No agent events yet…</p>;
  }
  return (
    <ol className="space-y-2" aria-label="Agent timeline">
      {events.map((event, index) => {
        const active = ACTIVE_DECISIONS.has(event.decision) && index === events.length - 1;
        return (
          <li
            key={`${event.timestamp}-${event.agent}-${event.decision}-${index}`}
            className="flex items-start gap-3 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
          >
            <span
              className={`mt-1 inline-block h-2 w-2 shrink-0 rounded-full ${
                event.error ? "bg-red-500" : active ? "animate-pulse bg-sky-500" : "bg-slate-300"
              }`}
              aria-hidden="true"
            />
            <div className="min-w-0">
              <div className="flex flex-wrap items-baseline gap-x-2">
                <span className="font-medium text-slate-900">{AGENT_LABELS[event.agent] ?? event.agent}</span>
                <span className="font-mono text-xs text-slate-500">{event.decision}</span>
                <span className="ml-auto text-xs text-slate-400">{formatTime(event.timestamp)}</span>
              </div>
              {event.error && <p className="mt-1 text-xs text-red-600">{event.error}</p>}
              {event.payload && Object.keys(event.payload).length > 0 && (
                <p className="mt-1 truncate font-mono text-xs text-slate-400">{JSON.stringify(event.payload)}</p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
