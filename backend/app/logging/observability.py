from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Metrics:
    fallbacks: int = 0

    def reset(self) -> None:
        self.fallbacks = 0


metrics = Metrics()
