// Home inbox — matches the mother project: worklist, upload/paste, then case library.

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getCases, listRuns, startRun } from "../api";
import type { CaseSummary, RunListItem } from "../types";

const URGENCY_STYLES: Record<string, string> = {
  routine: "bg-slate-100 text-slate-600",
  critical: "bg-red-700 text-white",
};

export default function Library() {
  const navigate = useNavigate();
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | undefined>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [urgency, setUrgency] = useState("");
  const [status, setStatus] = useState("");

  useEffect(() => {
    getCases()
      .then(setCases)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load cases"));
  }, []);

  useEffect(() => {
    listRuns()
      .then(setRuns)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load runs"));
  }, []);

  const sorted = useMemo(() => {
    return [...runs]
      .filter((run) => !urgency || run.urgency === urgency)
      .filter((run) => !status || run.status === status)
      .sort((a, b) => {
        const rank = (item: RunListItem) => (item.urgency === "critical" ? 0 : 1);
        return rank(a) - rank(b);
      });
  }, [runs, urgency, status]);

  async function launch(input: { caseId?: string; text?: string; file?: File }) {
    setBusy(true);
    setError("");
    try {
      const result = await startRun(input);
      navigate(`/workspace/${result.run_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to start run");
    } finally {
      setBusy(false);
    }
  }

  function onUpload(event: FormEvent) {
    event.preventDefault();
    void launch({ text, file });
  }

  const canUpload = Boolean(text.trim() || file);

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="text-lg font-semibold">Inbox</h2>
        <p className="text-sm text-slate-600">Worklist by urgency. Synthetic cases only.</p>
        <div className="mt-3 flex flex-wrap gap-3 text-sm">
          <select className="rounded border px-2 py-1" value={urgency} onChange={(e) => setUrgency(e.target.value)}>
            <option value="">All urgency</option>
            <option value="critical">Critical</option>
            <option value="routine">Routine</option>
          </select>
          <select className="rounded border px-2 py-1" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All status</option>
            <option value="awaiting_review">Awaiting review</option>
            <option value="finalized">Finalized</option>
            <option value="ingest_failed">Ingest failed</option>
            <option value="running">Running</option>
          </select>
        </div>
        <table className="mt-3 w-full text-left text-sm">
          <thead>
            <tr className="text-slate-500">
              <th className="py-2">Urgency</th>
              <th>Case</th>
              <th>Status</th>
              <th>Source</th>
              <th>Age</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((run) => (
              <tr
                key={run.run_id}
                className="cursor-pointer border-t hover:bg-slate-50"
                onClick={() => navigate(`/workspace/${run.run_id}`)}
              >
                <td className={`py-2 ${run.urgency === "critical" ? "font-semibold text-red-700" : ""}`}>
                  {run.urgency || "—"}
                </td>
                <td>{run.case_id || "upload"}</td>
                <td>{run.status}</td>
                <td>{run.source || "upload"}</td>
                <td>{run.age_seconds != null ? `${Math.round(run.age_seconds / 60)}m` : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {sorted.length === 0 && <p className="mt-3 text-sm text-slate-500">No runs in this filter yet.</p>}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-4" aria-label="Upload or paste a report">
        <h2 className="text-lg font-semibold">Upload or paste a report</h2>
        <p className="mt-1 text-sm text-slate-600">
          Upload a .pdf / .txt / .md file or paste a synthetic clinical note. Educational prototype. Not for clinical use.
        </p>
        <form onSubmit={onUpload} className="mt-3 space-y-3">
          <label htmlFor="home-paste-area" className="sr-only">
            Paste a synthetic clinical note
          </label>
          <textarea
            id="home-paste-area"
            className="w-full rounded-md border border-slate-300 p-3 text-sm"
            rows={5}
            placeholder="Paste a synthetic clinical note"
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
          <div>
            <label htmlFor="home-file-input" className="block text-sm font-medium text-slate-700">
              Document upload
            </label>
            <input
              id="home-file-input"
              data-testid="home-file-input"
              type="file"
              accept=".pdf,.txt,.md"
              className="mt-1 block w-full text-sm text-slate-700"
              onChange={(event) => setFile(event.target.files?.[0])}
            />
            {file && <p className="mt-1 text-xs text-slate-500">Selected: {file.name}</p>}
          </div>
          <button
            type="submit"
            data-testid="upload-submit"
            disabled={busy || !canUpload}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-40"
          >
            {busy ? "Starting…" : "Run assistant"}
          </button>
        </form>
        {error && (
          <p className="mt-2 text-sm text-red-700" role="alert">
            {error}
          </p>
        )}
      </section>

      <section>
        <h2 className="text-lg font-semibold">Synthetic case library</h2>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          {cases.map((item) => (
            <div key={item.case_id} className="rounded-xl border border-slate-200 bg-white p-4 text-left">
              <div className="flex items-center justify-between">
                <p className="font-medium">{item.case_id}</p>
                <span
                  className={`rounded px-2 py-0.5 text-xs uppercase ${URGENCY_STYLES[item.urgency] ?? "text-slate-500"}`}
                >
                  {item.urgency}
                </span>
              </div>
              <p className="mt-1 text-sm text-slate-800">{item.title}</p>
              <p className="mt-1 text-sm text-slate-600">{item.description}</p>
              <div className="mt-3 flex gap-2">
                <button
                  type="button"
                  onClick={() => launch({ caseId: item.case_id })}
                  disabled={busy}
                  data-testid={`run-assistant-${item.case_id}`}
                  className="rounded-md bg-slate-900 px-3 py-1.5 text-xs text-white disabled:opacity-40"
                >
                  Start
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
