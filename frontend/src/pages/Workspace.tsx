// Workspace — upload / paste / library-case inputs, agent timeline, HITL review,
// labs, and follow-up chat. Restores fully from GET /api/runs/{id} on refresh (A7).

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getCases, getRun, startRun, subscribeRunEvents } from "../api";
import ChatPanel from "../components/ChatPanel";
import HitlDrawer from "../components/HitlDrawer";
import LabTable from "../components/LabTable";
import Timeline from "../components/Timeline";
import type { CaseSummary, ChatMessage, RunEvent, RunRecord } from "../types";

const ACTIVE_STATUSES = new Set(["running", "ingested", "routed", "revising"]);
const STOP_POLL_STATUSES = new Set(["awaiting_review", "ingest_failed", "finalized"]);

function eventKey(event: RunEvent): string {
  return `${event.timestamp ?? ""}|${event.agent}|${event.decision}`;
}

function mergeEvents(previous: RunEvent[], incoming: RunEvent[]): RunEvent[] {
  const seen = new Set(previous.map(eventKey));
  const merged = [...previous];
  for (const event of incoming) {
    const key = eventKey(event);
    if (!seen.has(key)) {
      seen.add(key);
      merged.push(event);
    }
  }
  return merged;
}

export default function Workspace() {
  const navigate = useNavigate();
  const { runId } = useParams<{ runId?: string }>();

  // Inputs (before a run starts)
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [caseId, setCaseId] = useState("");
  const [pastedText, setPastedText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [starting, setStarting] = useState(false);

  // Run state
  const [run, setRun] = useState<RunRecord | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const seenRef = useRef<Set<string>>(new Set());
  const stopRef = useRef<(() => void) | null>(null);

  const hasInput = Boolean(caseId) || pastedText.trim().length > 0 || file !== null;

  const absorbRecord = useCallback((record: RunRecord) => {
    setRun(record);
    setEvents((previous) => {
      const merged = mergeEvents(previous, record.events ?? []);
      seenRef.current = new Set(merged.map(eventKey));
      return merged;
    });
  }, []);

  // Library cases for the picker
  useEffect(() => {
    getCases()
      .then(setCases)
      .catch(() => setCases([]));
  }, []);

  const refreshRun = useCallback(
    async (id: string) => {
      try {
        absorbRecord(await getRun(id));
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load run");
      }
    },
    [absorbRecord],
  );

  // Load + subscribe + poll for the active run (A4/A7)
  useEffect(() => {
    if (!runId) return;

    seenRef.current = new Set();
    setEvents([]);
    setRun(null);

    let cancelled = false;
    let pollTimer: number | undefined;

    refreshRun(runId); // restore from the persisted record — never create a second run

    stopRef.current = subscribeRunEvents(runId, {
      onEvent: (event) => {
        if (cancelled) return;
        const key = eventKey(event);
        if (seenRef.current.has(key)) return;
        seenRef.current.add(key);
        setEvents((previous) => [...previous, event]);
      },
      onStatus: (status) => {
        if (cancelled) return;
        // Status changed (or terminal reached) — pull the full record for summary/draft.
        void refreshRun(runId);
        if (STOP_POLL_STATUSES.has(status) && pollTimer !== undefined) {
          window.clearInterval(pollTimer);
          pollTimer = undefined;
        }
      },
      onDone: () => {
        if (pollTimer !== undefined) {
          window.clearInterval(pollTimer);
          pollTimer = undefined;
        }
      },
      onError: () => {
        // SSE failed — the poll interval below keeps the workspace alive.
      },
    });

    pollTimer = window.setInterval(() => {
      if (cancelled) return;
      void refreshRun(runId);
    }, 2500);

    return () => {
      cancelled = true;
      if (pollTimer !== undefined) window.clearInterval(pollTimer);
      stopRef.current?.();
      stopRef.current = null;
    };
  }, [runId, refreshRun]);

  async function handleStart() {
    if (!hasInput || starting) return;
    setStarting(true);
    setError(null);
    try {
      const result = await startRun({ caseId: caseId || undefined, text: pastedText, file });
      setPastedText("");
      setFile(null);
      navigate(`/workspace/${result.run_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start run");
    } finally {
      setStarting(false);
    }
  }

  function handleHistory(history: ChatMessage[]) {
    setRun((previous) => (previous ? { ...previous, chat_history: history } : previous));
  }

  function handleReviewed(status: string) {
    if (runId) void refreshRun(runId);
    if (status === "revising") {
      // Poll will pick up the next awaiting_review.
    }
  }

  const status = run?.status ?? "";
  const showDrawer = status === "awaiting_review";
  const isIngestFailed = status === "ingest_failed";
  const isFinalized = status === "finalized";

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {/* Left column: inputs + timeline */}
      <div className="space-y-4">
        {!runId && (
          <section aria-label="New run inputs" className="rounded-md border border-slate-200 bg-white p-4">
            <h2 className="text-sm font-semibold text-slate-900">Start a run</h2>
            <p className="mt-1 text-xs text-slate-500">
              Pick a library case, paste note text, or upload a file (.md / .txt / .pdf). Synthetic data only.
            </p>

            <div className="mt-3 space-y-3">
              <div>
                <label htmlFor="case-picker" className="block text-sm font-medium text-slate-700">
                  Library case
                </label>
                <select
                  id="case-picker"
                  value={caseId}
                  onChange={(event) => setCaseId(event.target.value)}
                  className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-sky-500 focus:outline-none"
                >
                  <option value="">— none —</option>
                  {cases.map((item) => (
                    <option key={item.case_id} value={item.case_id}>
                      {item.case_id} · {item.title}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="paste-area" className="block text-sm font-medium text-slate-700">
                  Pasted note text
                </label>
                <textarea
                  id="paste-area"
                  value={pastedText}
                  onChange={(event) => setPastedText(event.target.value)}
                  rows={5}
                  placeholder="Paste the synthetic clinical note here…"
                  className="mt-1 w-full rounded border border-slate-300 p-2 text-sm focus:border-sky-500 focus:outline-none"
                />
              </div>

              <div>
                <label htmlFor="file-input" className="block text-sm font-medium text-slate-700">
                  Upload file
                </label>
                <input
                  id="file-input"
                  type="file"
                  accept=".md,.txt,.pdf"
                  onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                  className="mt-1 block w-full text-sm text-slate-600"
                />
                {file && (
                  <button
                    type="button"
                    onClick={() => setFile(null)}
                    className="mt-1 text-xs text-slate-500 underline underline-offset-2"
                  >
                    Remove {file.name}
                  </button>
                )}
              </div>

              <button
                type="button"
                data-testid="run-assistant-btn"
                onClick={handleStart}
                disabled={!hasInput || starting}
                className="w-full rounded bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {starting ? "Starting…" : "Run assistant"}
              </button>
              {!hasInput && (
                <p className="text-xs text-slate-400">
                  Run assistant is disabled until there is text, a file, or a library case.
                </p>
              )}
            </div>
          </section>
        )}

        <section aria-label="Agent timeline" className="rounded-md border border-slate-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-900">Agent timeline</h2>
          <Timeline events={events} />
        </section>
      </div>

      {/* Right column: status, HITL, labs, chat */}
      <div className="space-y-4">
        {error && (
          <p className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
            {error}
          </p>
        )}

        {!run && !error && (
          <div className="rounded-md border border-slate-200 bg-white p-4">
            <p className="text-sm text-slate-500">No run loaded. Start one from the inputs.</p>
          </div>
        )}

        {run && (
          <section
            aria-label="Run status"
            data-testid="run-status"
            className={`rounded-md border p-4 text-sm ${
              isIngestFailed
                ? "border-red-300 bg-red-50"
                : showDrawer
                  ? "border-amber-300 bg-amber-50"
                  : isFinalized
                    ? "border-emerald-300 bg-emerald-50"
                    : "border-sky-300 bg-sky-50"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs text-slate-500">{run.run_id}</span>
              <span className="rounded bg-white/70 px-2 py-0.5 font-mono text-xs text-slate-700">{run.status}</span>
            </div>
            {isIngestFailed && (
              <div className="mt-2">
                <p className="font-medium text-red-800">The document could not be read.</p>
                <p className="mt-1 text-red-700">
                  Please paste the note as text instead — the assistant can only work on readable input. Use the
                  inputs to start a new run with pasted text.
                </p>
              </div>
            )}
            {ACTIVE_STATUSES.has(status) && <p className="mt-2 text-sky-800">Agents are working…</p>}
          </section>
        )}

        {showDrawer && run && <HitlDrawer run={run} onReviewed={handleReviewed} />}

        {isFinalized && run && (
          <section aria-label="Released draft" className="rounded-md border border-emerald-200 bg-white p-4">
            <h2 className="text-sm font-semibold text-slate-900">
              Released draft <span className="ml-2 rounded bg-emerald-100 px-2 py-0.5 text-xs text-emerald-700">finalized</span>
            </h2>
            <p className="mt-2 whitespace-pre-wrap text-sm text-slate-800">{run.summary}</p>
            {run.recommendations.length > 0 && (
              <ul className="mt-3 space-y-2 text-sm text-slate-700">
                {run.recommendations.map((rec, index) => (
                  <li key={`${rec.title}-${index}`}>
                    <span className="font-medium">{rec.title}</span>
                    {rec.detail && <span className="text-slate-600"> — {rec.detail}</span>}
                    {rec.citations.length > 0 && (
                      <span className="ml-1 text-xs text-slate-400">[{rec.citations.join("; ")}]</span>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {run.human_decision.decision !== "pending" && (
              <p className="mt-3 text-xs text-slate-400">
                Clinician decision: <span className="font-mono">{run.human_decision.decision}</span>
                {run.human_decision.decided_at ? ` at ${new Date(run.human_decision.decided_at).toLocaleString()}` : ""}
              </p>
            )}
          </section>
        )}

        {run && run.lab_flags.length > 0 && (
          <section aria-label="Labs" className="rounded-md border border-slate-200 bg-white p-4">
            <h2 className="mb-3 text-sm font-semibold text-slate-900">Labs</h2>
            <LabTable labs={run.lab_flags} />
          </section>
        )}

        {run && <ChatPanel run={run} onHistory={handleHistory} />}
      </div>
    </div>
  );
}
