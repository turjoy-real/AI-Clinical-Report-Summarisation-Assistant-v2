"""Shared Pydantic contracts from team/CONTRACTS.md. Do not change without the whole team."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class PatientData(BaseModel):
    name: str = "synthetic-unknown"
    age: int | None = None
    sex: str | None = None
    mrn: str | None = None  # synthetic IDs only, e.g. SYN-1001
    setting: str | None = None  # clinic, ED, ward
    date: str | None = None
    source_case_id: str | None = None


class LabFlag(BaseModel):
    analyte: str
    value: str
    unit: str = ""
    flag: Literal["normal", "high", "low", "critical_high", "critical_low", "unknown"] = "unknown"


class MedicalData(BaseModel):
    chief_concern: str = ""
    problems: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    vitals: dict[str, str] = Field(default_factory=dict)
    labs: list[LabFlag] = Field(default_factory=list)
    assessment: str = ""
    plan: str = ""
    missing_sections: list[str] = Field(default_factory=list)


class GuidelineChunk(BaseModel):
    id: str
    title: str
    topic: str
    source: str
    text: str
    citation: str = ""


class RetrievedDoc(BaseModel):
    id: str
    title: str
    topic: str
    source: str  # filename, e.g. diabetes.md
    text: str
    score: float = 0.0
    citation: str = ""  # public teaching source title, never a copyrighted PDF


class Recommendation(BaseModel):
    title: str
    detail: str
    citations: list[str] = Field(default_factory=list)


class SummaryDraft(BaseModel):
    disclaimer: str = "Educational prototype. Not for clinical use."
    summary: str  # in-depth SOAP-style writeup (Sneha)
    used_topics: list[str] = Field(default_factory=list)


class SummaryBundle(BaseModel):
    """Turjoy joins Sneha + Lakshmi outputs onto graph state. Do not implement this join yourself."""

    disclaimer: str = "Educational prototype. Not for clinical use."
    summary: str
    recommendations: list[Recommendation] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    used_topics: list[str] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    decision: Literal["approve", "edit", "reject"]
    edits: str = ""
    feedback: str = ""


# --- Run persistence (Adarsh) -------------------------------------------------


class RunEvent(BaseModel):
    """One agent timeline event; shape matches graph/state.py append_event."""

    timestamp: str = ""
    agent: str
    decision: str
    latency_ms: int = 0
    tokens: int = 0
    model: str = "mock"
    tool_calls: list[str] = Field(default_factory=list)
    error: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    timestamp: str = ""


class HumanDecision(BaseModel):
    """Last clinician decision recorded on a run."""

    decision: Literal["pending", "approve", "edit", "reject"] = "pending"
    edits: str = ""
    feedback: str = ""
    decided_at: str | None = None


class RunRecord(BaseModel):
    run_id: str
    case_id: str | None = None
    status: str = "running"
    disclaimer: str = "Educational prototype. Not for clinical use."
    summary: str = ""
    recommendations: list[Recommendation] = Field(default_factory=list)
    lab_flags: list[dict[str, Any]] = Field(default_factory=list)
    retrieved_docs: list[dict[str, Any]] = Field(default_factory=list)
    safety_flags: list[str] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    analysis: dict[str, Any] = Field(default_factory=dict)
    events: list[RunEvent] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    chat_history: list[ChatMessage] = Field(default_factory=list)
    human_decision: HumanDecision = Field(default_factory=HumanDecision)
    created_at: str = ""
    updated_at: str = ""


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
