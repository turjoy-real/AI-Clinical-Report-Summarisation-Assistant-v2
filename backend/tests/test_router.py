from app.config import get_settings
from app.graph.router import route_report


def _text(case_id: str) -> str:
    return (get_settings().data_dir / "reports" / f"{case_id}.md").read_text(encoding="utf-8")


def test_sepsis_routes_critical_infectious():
    result = route_report(_text("CR-003"))
    assert result["urgency"] == "critical"
    assert result["specialty"] == "infectious_disease"


def test_chest_pain_routes_critical_cardio():
    result = route_report(_text("CR-008"))
    assert result["urgency"] == "critical"
    assert result["specialty"] == "cardio"


def test_wellness_routes_routine_general():
    result = route_report(_text("CR-005"))
    assert result["urgency"] == "routine"
    assert result["specialty"] == "general"


def test_diabetes_routes_endocrine():
    result = route_report(_text("CR-001"))
    assert result["specialty"] == "endocrine"
    assert result["urgency"] == "routine"


def test_negated_chest_pain_does_not_force_critical():
    result = route_report(_text("CR-001"))
    assert result["urgency"] == "routine"
