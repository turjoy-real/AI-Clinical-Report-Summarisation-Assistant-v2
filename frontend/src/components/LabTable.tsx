// Lab results table from the run record's lab_flags.

import type { LabFlag } from "../types";

const FLAG_STYLES: Record<string, string> = {
  normal: "bg-emerald-50 text-emerald-700",
  high: "bg-amber-50 text-amber-700",
  low: "bg-amber-50 text-amber-700",
  critical_high: "bg-red-50 text-red-700 font-semibold",
  critical_low: "bg-red-50 text-red-700 font-semibold",
  unknown: "bg-slate-100 text-slate-600",
};

export default function LabTable({ labs }: { labs: LabFlag[] }) {
  if (!labs.length) {
    return <p className="text-sm text-slate-500">No lab data on this run.</p>;
  }
  return (
    <div className="overflow-x-auto rounded-md border border-slate-200">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <caption className="sr-only">Lab results</caption>
        <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th scope="col" className="px-3 py-2">Analyte</th>
            <th scope="col" className="px-3 py-2">Value</th>
            <th scope="col" className="px-3 py-2">Unit</th>
            <th scope="col" className="px-3 py-2">Flag</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white">
          {labs.map((lab, index) => (
            <tr key={`${lab.analyte}-${index}`}>
              <td className="px-3 py-2 font-medium text-slate-800">{lab.analyte}</td>
              <td className="px-3 py-2 font-mono">{lab.value}</td>
              <td className="px-3 py-2 text-slate-500">{lab.unit || "—"}</td>
              <td className="px-3 py-2">
                <span className={`rounded px-1.5 py-0.5 text-xs ${FLAG_STYLES[lab.flag] ?? FLAG_STYLES.unknown}`}>
                  {lab.flag}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
