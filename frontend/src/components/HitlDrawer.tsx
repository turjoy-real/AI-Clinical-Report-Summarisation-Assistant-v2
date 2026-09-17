// HITL drawer — the core human-in-the-loop surface. Appears only when the run is
// awaiting_review. Every action persists through POST /api/runs/{id}/review.

import { useState } from "react";
import { submitReview } from "../api";
import type { LabFlag, Recommendation, RunRecord } from "../types";

type Mode = "view" | "edit" | "reject";

export default function HitlDrawer({
  run,
  onReviewed,
}: {
  run: RunRecord;
  onReviewed: (status: string) => void;
}) {
  const [mode, setMode] = useState<Mode>("view");
  const [edits, setEdits] = useState("");
  const [feedback, setFeedback] = useState("");
  const [inFlight, setInFlight] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const recommendations: Recommendation[] = run.recommendations ?? [];
  const labs: LabFlag[] = run.lab_flags ?? [];

  async function act(
    decision: "approve" | "edit" | "reject",
    body: { edits?: string; feedback?: string } = {},
  ) {
    if (inFlight) return;
    setInFlight(true);
    setError(null);
    try {
      const result = await submitReview(run.run_id, { decision, ...body });
      onReviewed(result.status);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Review failed");
    } finally {
      setInFlight(false);
    }
  }

  return (
    <section
      aria-label="Clinician review"
      data-testid="hitl-drawer"
      className="rounded-md border border-amber-300 bg-amber-50/60 p-4"
    >
      <header className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-amber-900">
          Clinician review required
        </h2>
        <span className="rounded bg-amber-200 px-2 py-0.5 text-xs font-medium text-amber-900">
          awaiting_review
        </span>
      </header>
      <p className="mt-1 text-xs text-amber-800">
        Nothing is released from this draft until a clinician approves. Educational prototype. Not for
        clinical use.
      </p>

      {/* Draft summary */}
      <div className="mt-3 rounded border border-amber-200 bg-white p-3">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Draft summary</h3>
        <p data-testid="draft-summary" className="mt-1 whitespace-pre-wrap text-sm text-slate-800">
          {run.summary || "No draft summary available."}
        </p>
      </div>

      {/* Recommendations + citations */}
      {recommendations.length > 0 && (
        <div className="mt-3 rounded border border-amber-200 bg-white p-3">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Draft recommendations
          </h3>
          <ul className="mt-1 space-y-2 text-sm text-slate-800">
            {recommendations.map((rec, index) => (
              <li key={`${rec.title}-${index}`}>
                <span className="font-medium">{rec.title}</span>
                {rec.detail && <span className="text-slate-600"> — {rec.detail}</span>}
                {rec.citations.length > 0 && (
                  <span className="ml-1 text-xs text-slate-400">[{rec.citations.join("; ")}]</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Safety + lab flags */}
      {run.safety_flags.length > 0 && (
        <p className="mt-3 text-xs text-amber-800">
          Safety flags: <span className="font-mono">{run.safety_flags.join(", ")}</span>
        </p>
      )}
      {labs.length > 0 && (
        <p className="mt-1 text-xs text-amber-800">
          Lab flags on this run:{" "}
          <span className="font-mono">{labs.map((lab) => `${lab.analyte} ${lab.value}${lab.unit}`).join(" · ")}</span>
        </p>
      )}

      {/* Mode-specific input */}
      {mode === "edit" && (
        <div className="mt-3">
          <label htmlFor="hitl-edits" className="block text-sm font-medium text-slate-700">
            Edited recommendation text
          </label>
          <textarea
            id="hitl-edits"
            data-testid="hitl-edits"
            value={edits}
            onChange={(event) => setEdits(event.target.value)}
            rows={4}
            className="mt-1 w-full rounded border border-slate-300 p-2 text-sm focus:border-sky-500 focus:outline-none"
            placeholder="Rewrite the recommendation as a clinician…"
          />
        </div>
      )}
      {mode === "reject" && (
        <div className="mt-3">
          <label htmlFor="hitl-feedback" className="block text-sm font-medium text-slate-700">
            Feedback for revision
          </label>
          <textarea
            id="hitl-feedback"
            data-testid="hitl-feedback"
            value={feedback}
            onChange={(event) => setFeedback(event.target.value)}
            rows={3}
            className="mt-1 w-full rounded border border-slate-300 p-2 text-sm focus:border-sky-500 focus:outline-none"
            placeholder="What should the assistant reconsider?"
          />
        </div>
      )}

      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

      {/* Actions — disabled while the request is in flight */}
      <div className="mt-4 flex flex-wrap gap-2">
        {mode === "view" && (
          <>
            <button
              type="button"
              data-testid="approve-btn"
              onClick={() => act("approve")}
              disabled={inFlight}
              className="rounded bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {inFlight ? "Working…" : "Approve"}
            </button>
            <button
              type="button"
              data-testid="edit-btn"
              onClick={() => setMode("edit")}
              disabled={inFlight}
              className="rounded bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Save edits
            </button>
            <button
              type="button"
              data-testid="reject-btn"
              onClick={() => setMode("reject")}
              disabled={inFlight}
              className="rounded border border-red-300 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Reject
            </button>
          </>
        )}
        {mode === "edit" && (
          <>
            <button
              type="button"
              data-testid="edit-save-btn"
              onClick={() => act("edit", { edits })}
              disabled={inFlight || !edits.trim()}
              className="rounded bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {inFlight ? "Saving…" : "Submit edited plan"}
            </button>
            <button
              type="button"
              onClick={() => setMode("view")}
              disabled={inFlight}
              className="rounded border border-slate-300 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 disabled:opacity-50"
            >
              Back
            </button>
          </>
        )}
        {mode === "reject" && (
          <>
            <button
              type="button"
              data-testid="reject-confirm-btn"
              onClick={() => act("reject", { feedback })}
              disabled={inFlight || !feedback.trim()}
              className="rounded bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {inFlight ? "Sending…" : "Send feedback"}
            </button>
            <button
              type="button"
              onClick={() => setMode("view")}
              disabled={inFlight}
              className="rounded border border-slate-300 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 disabled:opacity-50"
            >
              Back
            </button>
          </>
        )}
      </div>
    </section>
  );
}
