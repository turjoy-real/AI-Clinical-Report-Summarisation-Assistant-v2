// Observability — Turjoy owns the numbers (GET /api/metrics); this page renders them.

import { useEffect, useState } from "react";
import { getMetrics } from "../api";
import type { Metrics } from "../types";

const LABELS: Record<string, string> = {
  runs_total: "Runs total",
  runs_finalized: "Runs finalized",
  hitl_approvals: "HITL approvals",
  hitl_rejections: "HITL rejections",
  llm_fallbacks: "LLM fallbacks",
  agent_latency_ms_avg: "Avg agent latency (ms)",
  tokens_total: "Tokens total",
};

export default function Observability() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMetrics()
      .then(setMetrics)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load metrics"));
  }, []);

  const latency = metrics?.agent_latency ?? {};
  const models = metrics?.model_path ?? metrics?.models ?? {};
  const hitlMix = metrics?.hitl_mix ?? {};

  return (
    <div>
      <h1 className="text-xl font-semibold text-slate-900">Observability</h1>
      <p className="mt-1 text-sm text-slate-500">
        Run-level metrics from the backend. Educational prototype. Not for clinical use.
      </p>

      {error && (
        <p className="mt-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
          {error}
        </p>
      )}

      {!metrics && !error && (
        <div className="mt-4 h-40 animate-pulse rounded-md bg-slate-100" aria-hidden="true" />
      )}

      {metrics && (
        <>
          <table className="mt-4 min-w-full divide-y divide-slate-200 rounded-md border border-slate-200 bg-white text-sm">
            <caption className="sr-only">Run metrics</caption>
            <tbody className="divide-y divide-slate-100">
              {Object.keys(LABELS).map((key) => (
                <tr key={key}>
                  <th scope="row" className="px-4 py-2 text-left font-medium text-slate-700">
                    {LABELS[key]}
                  </th>
                  <td className="px-4 py-2 text-right font-mono text-slate-900">
                    {String(metrics[key as keyof Metrics] ?? 0)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {Object.keys(models).length > 0 && (
            <section className="mt-6">
              <h2 className="text-sm font-semibold text-slate-800">Model path</h2>
              <ul className="mt-2 text-sm text-slate-700">
                {Object.entries(models).map(([name, count]) => (
                  <li key={name} className="flex justify-between border-b border-slate-100 py-1">
                    <span>{name}</span>
                    <span className="font-mono">{count}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {Object.keys(hitlMix).length > 0 && (
            <section className="mt-6">
              <h2 className="text-sm font-semibold text-slate-800">HITL mix</h2>
              <ul className="mt-2 text-sm text-slate-700">
                {Object.entries(hitlMix).map(([name, count]) => (
                  <li key={name} className="flex justify-between border-b border-slate-100 py-1">
                    <span>{name}</span>
                    <span className="font-mono">{count}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {Object.keys(latency).length > 0 && (
            <section className="mt-6">
              <h2 className="text-sm font-semibold text-slate-800">Latency by agent (p50 / p95)</h2>
              <table className="mt-2 min-w-full divide-y divide-slate-200 rounded-md border border-slate-200 bg-white text-sm">
                <thead>
                  <tr className="text-left text-slate-500">
                    <th className="px-3 py-2">Agent</th>
                    <th className="px-3 py-2">p50 ms</th>
                    <th className="px-3 py-2">p95 ms</th>
                    <th className="px-3 py-2">avg ms</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(latency).map(([agent, row]) => (
                    <tr key={agent} className="border-t border-slate-100">
                      <td className="px-3 py-2 font-mono">{agent}</td>
                      <td className="px-3 py-2 font-mono">{row.p50_ms}</td>
                      <td className="px-3 py-2 font-mono">{row.p95_ms}</td>
                      <td className="px-3 py-2 font-mono">{row.avg_ms}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}
        </>
      )}
    </div>
  );
}
