from __future__ import annotations

import json
import threading
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import get_settings


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _percentile(values: list[int], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (len(ordered) - 1) * (pct / 100.0)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return round(ordered[low] * (1 - weight) + ordered[high] * weight, 1)


class MetricsStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self.total_runs = 0
            self.by_urgency: dict[str, int] = defaultdict(int)
            self.by_specialty: dict[str, int] = defaultdict(int)
            self.hitl_outcomes: dict[str, int] = defaultdict(int)
            self.models: dict[str, int] = defaultdict(int)
            self.errors = 0
            self.agent_latency_ms: dict[str, list[int]] = defaultdict(list)
            self.tool_calls: dict[str, int] = defaultdict(int)
            self.fallbacks = 0
            self.retries = 0
            self.tokens_total = 0

    def record_run(self, urgency: str | None, specialty: str | None, model: str) -> None:
        with self._lock:
            self.total_runs += 1
            if urgency:
                self.by_urgency[urgency] += 1
            if specialty:
                self.by_specialty[specialty] += 1
            self.models[model or "mock"] += 1

    def record_event(self, event: dict[str, Any]) -> None:
        with self._lock:
            agent = str(event.get("agent") or "unknown")
            self.agent_latency_ms[agent].append(int(event.get("latency_ms") or 0))
            self.tokens_total += int(event.get("tokens") or 0)
            for tool in event.get("tool_calls") or []:
                self.tool_calls[str(tool)] += 1
            if event.get("error"):
                self.errors += 1
            decision = str(event.get("decision") or "").lower()
            if "fallback" in decision or event.get("payload", {}).get("fallback"):
                self.fallbacks += 1
            if "retry" in decision:
                self.retries += 1
            model = str(event.get("model") or "")
            if model:
                self.models[model] += 1

    def record_hitl(self, decision: str) -> None:
        with self._lock:
            self.hitl_outcomes[decision] += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            latencies = {}
            all_ms: list[int] = []
            for agent, values in self.agent_latency_ms.items():
                all_ms.extend(values)
                latencies[agent] = {
                    "count": len(values),
                    "avg_ms": round(sum(values) / len(values), 1) if values else 0,
                    "p50_ms": _percentile(values, 50),
                    "p95_ms": _percentile(values, 95),
                    "max_ms": max(values) if values else 0,
                }
            hitl = dict(self.hitl_outcomes)
            return {
                "total_runs": self.total_runs,
                "runs_total": self.total_runs,
                "by_urgency": dict(self.by_urgency),
                "by_specialty": dict(self.by_specialty),
                "hitl_outcomes": hitl,
                "hitl_mix": hitl,
                "hitl_approvals": hitl.get("approve", 0),
                "hitl_rejections": hitl.get("reject", 0),
                "models": dict(self.models),
                "model_path": dict(self.models),
                "errors": self.errors,
                "fallbacks": self.fallbacks,
                "llm_fallbacks": self.fallbacks,
                "retries": self.retries,
                "tool_calls": dict(self.tool_calls),
                "agent_latency": latencies,
                "agent_latency_ms_avg": round(sum(all_ms) / len(all_ms), 1) if all_ms else 0,
                "tokens_total": self.tokens_total,
            }


metrics = MetricsStore()


def append_jsonl(run_id: str, event: dict[str, Any]) -> None:
    path: Path = get_settings().log_dir / f"{run_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")
