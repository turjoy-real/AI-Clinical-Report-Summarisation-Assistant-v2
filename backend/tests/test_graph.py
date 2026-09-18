from app.graph.qa import answer_followup
from app.config import get_settings
from app.graph.workflow import build_graph
from langgraph.checkpoint.memory import MemorySaver


def _load(case_id: str) -> str:
    return (get_settings().data_dir / "reports" / f"{case_id}.md").read_text(encoding="utf-8")


def _run_until_hitl(case_id: str, thread_id: str):
    graph = build_graph(MemorySaver())
    config = {"configurable": {"thread_id": thread_id}}
    graph.invoke(
        {
            "thread_id": thread_id,
            "case_id": case_id,
            "raw_text": _load(case_id),
            "extracted_text": "",
            "report_type": "text",
            "human_decision": "pending",
            "errors": [],
            "events": [],
        },
        config,
    )
    return graph, config, graph.get_state(config)


def test_parallel_fanout_and_hitl_interrupt():
    graph, config, snapshot = _run_until_hitl("CR-001", "t-hitl-1")
    agents = [event["agent"] for event in snapshot.values.get("events", [])]
    assert "analysis" in agents and "labs" in agents and "rag" in agents
    assert "fanout" in agents and "synthesize" in agents
    assert snapshot.next == ("hitl_review",)
    assert snapshot.values.get("status") == "awaiting_review"
    assert snapshot.values.get("specialty") == "endocrine"
    summary = snapshot.values.get("summary", "").lower()
    assert "diabetes" in summary and "9.2" in summary
    topics = {doc.get("topic") for doc in snapshot.values.get("retrieved_docs", [])}
    assert "diabetes" in topics
    graph.update_state(config, {"human_decision": "approve"})
    graph.invoke(None, config)
    final = graph.get_state(config)
    assert final.values.get("status") == "finalized"
    assert not final.next


def test_reject_does_not_finalize_on_first_pass():
    graph, config, snapshot = _run_until_hitl("CR-001", "t-reject-1")
    assert snapshot.next == ("hitl_review",)
    graph.update_state(config, {"human_decision": "reject", "human_feedback": "too aggressive"})
    graph.invoke(None, config)
    after = graph.get_state(config)
    assert after.values.get("status") == "awaiting_review"
    assert after.next == ("hitl_review",)
    assert after.values.get("status") != "finalized"


def test_critical_sepsis_locks_hitl():
    _, _, snapshot = _run_until_hitl("CR-003", "t-sepsis")
    assert snapshot.values.get("urgency") == "critical"
    assert snapshot.values.get("safety_flags")
    assert snapshot.next == ("hitl_review",)
    assert snapshot.values.get("hitl_required") is True
    rec_text = " ".join(
        f"{item.get('title', '')} {item.get('detail', '')}" for item in snapshot.values.get("recommendations", [])
    ).lower()
    assert "urgent" in rec_text or "escalat" in rec_text or "immediately" in rec_text


def test_normal_case_has_no_critical_flags():
    _, _, snapshot = _run_until_hitl("CR-005", "t-normal")
    assert snapshot.values.get("urgency") == "routine"
    critical = [
        row
        for row in snapshot.values.get("lab_flags", [])
        if str(row.get("flag") or "").startswith("critical")
    ]
    assert critical == []


def test_memory_followup_uses_case_state():
    _, _, snapshot = _run_until_hitl("CR-001", "t-memory")
    answer = answer_followup("what was the A1c?", snapshot.values)
    assert "9.2" in answer
