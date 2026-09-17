from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="AI Clinical Report Summarisation Assistant",
    description="Educational prototype. Not for clinical use.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "disclaimer": "Educational prototype. Not for clinical use.",
        "mock_llm": True if settings.mock_llm else False,
    }


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "AI Clinical Report Summarisation Assistant",
        "disclaimer": "Educational prototype. Not for clinical use.",
        "docs": "/docs",
    }
