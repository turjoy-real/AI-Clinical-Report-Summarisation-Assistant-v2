// Case library — cards from GET /api/cases, preview on click, Run assistant action.

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getCase, getCases, startRun } from "../api";
import type { CaseDetail, CaseSummary } from "../types";

const URGENCY_STYLES: Record<string, string> = {
  routine: "bg-slate-100 text-slate-600",
  critical: "bg-red-700 text-white",
};

const SPECIALTY_LABELS: Record<string, string> = {
  endocrine: "Endocrinology",
  cardio: "Cardiology",
  infectious_disease: "Infectious disease",
  renal: "Renal",
  heme: "Hematology",
  general: "General",
};

export default function Library() {
  const navigate = useNavigate();
  const [cases, setCases] = useState<CaseSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<CaseDetail | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [running, setRunning] = useState<string | null>(null);

  useEffect(() => {
    getCases()
      .then(setCases)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load cases"));
  }, []);

  async function openCase(caseId: string) {
    if (previewLoading) return;
    setPreviewLoading(true);
    setError(null);
    try {
      setSelected(await getCase(caseId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load case");
    } finally {
      setPreviewLoading(false);
    }
  }

  async function runAssistant(caseId: string) {
    if (running) return;
    setRunning(caseId);
    setError(null);
    try {
      const result = await startRun({ caseId });
      navigate(`/workspace/${result.run_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start run");
      setRunning(null);
    }
  }

  if (error && !cases) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700" role="alert">
        {error}
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="ml-3 underline underline-offset-2"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-xl font-semibold text-slate-900">Synthetic case library</h1>
      <p className="mt-1 text-sm text-slate-500">
        Educational teaching cases only. No real patient data. Educational prototype. Not for clinical use.
      </p>

      {error && (
        <p className="mt-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
          {error}
        </p>
      )}

      {cases === null ? (
        <ul className="mt-4 grid gap-3 sm:grid-cols-2" aria-label="Loading cases">
          {[0, 1, 2, 3].map((index) => (
            <li key={index} className="h-32 animate-pulse rounded-md bg-slate-100" aria-hidden="true" />
          ))}
        </ul>
      ) : cases.length === 0 ? (
        <div className="mt-4 rounded-md border border-slate-200 bg-white p-6 text-center text-sm text-slate-500">
          No cases available yet. The synthetic library is owned by Turjoy (data/cases.json).
        </div>
      ) : (
        <ul className="mt-4 grid gap-3 sm:grid-cols-2">
          {cases.map((item) => {
            const isSelected = selected?.case_id === item.case_id;
            const isRunning = running === item.case_id;
            return (
              <li key={item.case_id}>
                <article
                  className={`h-full rounded-md border bg-white p-4 transition-shadow hover:shadow-sm ${
                    isSelected ? "border-sky-400" : "border-slate-200"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xs text-slate-400">{item.case_id}</span>
                    <span className={`rounded px-2 py-0.5 text-xs font-medium ${URGENCY_STYLES[item.urgency] ?? URGENCY_STYLES.routine}`}>
                      {item.urgency === "critical" ? "Critical · " + item.urgency : item.urgency}
                    </span>
                  </div>
                  <h2 className="mt-1 text-sm font-semibold text-slate-900">{item.title}</h2>
                  <p className="mt-1 text-sm text-slate-500">{item.description}</p>
                  <p className="mt-2 text-xs text-slate-400">{SPECIALTY_LABELS[item.specialty] ?? item.specialty}</p>

                  {isSelected && (
                    <div className="mt-3 rounded bg-slate-50 p-3">
                      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Report preview
                      </h3>
                      <pre className="mt-1 max-h-48 overflow-y-auto whitespace-pre-wrap text-xs leading-relaxed text-slate-700">
                        {selected.report_text || "No report text found."}
                      </pre>
                    </div>
                  )}

                  <div className="mt-3 flex gap-2">
                    <button
                      type="button"
                      onClick={() => (isSelected ? setSelected(null) : openCase(item.case_id))}
                      className="rounded border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
                      aria-expanded={isSelected}
                    >
                      {isSelected ? "Hide report" : previewLoading ? "Loading…" : "Preview report"}
                    </button>
                    <button
                      type="button"
                      onClick={() => runAssistant(item.case_id)}
                      disabled={running !== null}
                      data-testid={`run-assistant-${item.case_id}`}
                      className="rounded bg-sky-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {isRunning ? "Starting…" : "Run assistant"}
                    </button>
                  </div>
                </article>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
