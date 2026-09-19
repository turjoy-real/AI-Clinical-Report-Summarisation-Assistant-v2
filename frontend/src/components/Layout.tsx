// App shell — sticky disclaimer banner, nav, and a backend health indicator.

import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { getHealth } from "../api";
import type { HealthInfo } from "../types";
import Disclaimer from "./Disclaimer";

type HealthState =
  | { kind: "loading" }
  | { kind: "live"; info: HealthInfo }
  | { kind: "unreachable" };

export default function Layout() {
  const [health, setHealth] = useState<HealthState>({ kind: "loading" });

  useEffect(() => {
    let active = true;
    getHealth()
      .then((info) => {
        if (active) setHealth({ kind: "live", info });
      })
      .catch(() => {
        if (active) setHealth({ kind: "unreachable" });
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="flex min-h-screen flex-col">
      <Disclaimer />
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-6 px-4 py-3">
          <NavLink to="/" className="text-sm font-semibold tracking-tight text-slate-900">
            Clinical Report Assistant
          </NavLink>
          <nav className="flex items-center gap-1 text-sm" aria-label="Primary">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                `rounded px-3 py-1.5 ${isActive ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"}`
              }
            >
              Inbox
            </NavLink>
            <NavLink
              to="/observability"
              className={({ isActive }) =>
                `rounded px-3 py-1.5 ${isActive ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"}`
              }
            >
              Observability
            </NavLink>
          </nav>
          <div className="ml-auto flex items-center gap-2 text-xs" aria-live="polite">
            {health.kind === "loading" && <span className="text-slate-400">checking backend…</span>}
            {health.kind === "live" && (
              <span className="flex items-center gap-1.5 text-slate-600">
                <span
                  className={`inline-block h-2 w-2 rounded-full ${health.info.mock_llm ? "bg-amber-500" : "bg-emerald-500"}`}
                  aria-hidden="true"
                />
                {health.info.mock_llm ? "backend live · mock LLM" : "backend live"}
              </span>
            )}
            {health.kind === "unreachable" && (
              <span className="flex items-center gap-1.5 text-slate-500">
                <span className="inline-block h-2 w-2 rounded-full bg-red-500" aria-hidden="true" />
                backend unreachable
              </span>
            )}
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
        <Outlet />
      </main>
      <footer className="border-t border-slate-200 py-4 text-center text-xs text-slate-400">
        Educational prototype. Not for clinical use. Synthetic patients only.
      </footer>
    </div>
  );
}
