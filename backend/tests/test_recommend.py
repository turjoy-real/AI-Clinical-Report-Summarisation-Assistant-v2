from __future__ import annotations

import inspect
import json
from pathlib import Path

from app.contracts import LabFlag, MedicalData, PatientData, Recommendation, RetrievedDoc
from app.summarize import recommend as recommend_mod
from app.summarize.recommend import create_recommendations, lock_citations, main
from app.summarize.recommend_heuristics import build_heuristic_recommendations

REPO = Path(__file__).resolve().parents[2]


DISCLAIMER = "Educational prototype. Not for clinical use."


def _cr001_patient() -> PatientData:
    return PatientData(
        name="Jordan Hale (synthetic)",
        age=58,
        setting="clinic",
        source_case_id="CR-001",
    )


def _cr001_medical() -> MedicalData:
    return MedicalData(
        chief_concern="Review of type 2 diabetes after home glucose readings in the 200s.",
        problems=["type 2 diabetes"],
        medications=["metformin"],
        labs=[LabFlag(analyte="HbA1c", value="9.2", unit="%", flag="high")],
        assessment="Uncontrolled type 2 diabetes with HbA1c 9.2 % on metformin monotherapy.",
    )


def _diabetes_doc() -> RetrievedDoc:
    return RetrievedDoc(
        id="g-diabetes",
        title="Type 2 diabetes teaching card",
        topic="diabetes",
        source="diabetes.md",
        text="HbA1c above an educational teaching target. Discuss glycemic follow-up, not orders.",
        score=1.4,
        citation="Educational diabetes teaching card",
    )


def test_lk5_cr001_citations_are_subset_of_diabetes_doc():
    """CR-001-like inputs + diabetes RetrievedDoc (no network)."""
    docs = [_diabetes_doc()]
    allowed = {docs[0].title, docs[0].citation}
    recs = create_recommendations(_cr001_patient(), _cr001_medical(), docs)

    assert isinstance(recs, list)
    assert recs
    assert all(isinstance(item, Recommendation) for item in recs)
    assert all(len(item.citations) >= 1 for item in recs)
    for item in recs:
        assert set(item.citations) <= allowed
    joined = " ".join(f"{item.title} {item.detail}" for item in recs).lower()
    assert "glycemic" in joined or "hba1c" in joined
    assert 3 <= len(recs) <= 6
    diabetes_cites = {"Type 2 diabetes teaching card", "Educational diabetes teaching card"}
    assert any(
        ("glycemic" in f"{item.title} {item.detail}".lower() or "hba1c" in f"{item.title} {item.detail}".lower())
        and set(item.citations) & diabetes_cites
        for item in recs
    )
    assert not isinstance(recs, str)


def test_lk5_empty_retrieved_docs_does_not_invent_nice_ng28():
    recs = create_recommendations(_cr001_patient(), _cr001_medical(), [])
    blob = json.dumps([item.model_dump() for item in recs])
    assert "NICE NG28" not in blob
    assert "NICE" not in blob
    assert "UpToDate" not in blob
    assert recs
    assert recs[0].citations == []
    assert "not retrieved" in recs[0].title.lower() or "not retrieved" in recs[0].detail.lower()


def test_lk5_return_type_is_recommendation_list_not_soap_string():
    recs = create_recommendations(_cr001_patient(), _cr001_medical(), [_diabetes_doc()])
    assert type(recs) is list
    assert not isinstance(recs, str)
    assert all(isinstance(item, Recommendation) for item in recs)
    soap_markers = ("subjective:", "objective:", "assessment:", "plan:")
    for item in recs:
        lowered = item.detail.lower()
        assert not all(marker in lowered for marker in soap_markers)


def test_critical_findings_lead_with_immediate_discussion():
    medical = MedicalData(
        chief_concern="Fever and possible sepsis",
        problems=["suspected sepsis"],
        labs=[LabFlag(analyte="lactate", value="4.2", unit="mmol/L", flag="critical_high")],
    )
    recs = create_recommendations(_cr001_patient(), medical, [_diabetes_doc()])
    assert recs[0].title.lower() == "discuss immediately with a clinician"
    assert "order" not in recs[0].detail.lower() or "not an order" in recs[0].detail.lower()
    assert "test" not in recs[0].title.lower()


def test_acs_problem_leads_with_immediate_discussion():
    medical = MedicalData(
        problems=["possible ACS", "chest pain"],
        labs=[LabFlag(analyte="troponin", value="0.4", unit="ng/mL", flag="high")],
    )
    recs = create_recommendations(_cr001_patient(), medical, [_diabetes_doc()])
    assert recs[0].title.lower() == "discuss immediately with a clinician"


def test_unlisted_medication_is_dropped_unless_teaching_in_retrieved_text():
    from app.summarize.recommend_rules import apply_lk3_rules

    patient = _cr001_patient()
    medical = _cr001_medical()
    docs = [_diabetes_doc()]
    recs = apply_lk3_rules(
        [
            Recommendation(
                title="Start insulin tonight",
                detail=f"{DISCLAIMER} Prescribe insulin now.",
                citations=["Educational diabetes teaching card"],
            ),
            Recommendation(
                title="Discuss glycemic follow-up and HbA1c trend",
                detail=f"{DISCLAIMER} Consider glycemic follow-up and HbA1c.",
                citations=["Educational diabetes teaching card"],
            ),
            Recommendation(
                title="Consider teaching points from Type 2 diabetes teaching card",
                detail=f"{DISCLAIMER} Discuss the retrieved diabetes card.",
                citations=["Type 2 diabetes teaching card"],
            ),
            Recommendation(
                title="Discuss currently listed medications",
                detail=f"{DISCLAIMER} Consider reviewing metformin only.",
                citations=["Educational diabetes teaching card"],
            ),
        ],
        patient,
        medical,
        docs,
    )
    blob = " ".join(f"{item.title} {item.detail}" for item in recs).lower()
    assert "insulin" not in blob
    assert 3 <= len(recs) <= 6


def test_teaching_class_in_retrieved_text_may_be_discussed():
    from app.summarize.recommend_rules import apply_lk3_rules

    docs = [
        RetrievedDoc(
            id="g-diabetes",
            title="Type 2 diabetes teaching card",
            topic="diabetes",
            source="diabetes.md",
            text="HbA1c follow-up. Insulin class may be discussed as teaching, not a prescription.",
            score=1.4,
            citation="Educational diabetes teaching card",
        )
    ]
    recs = apply_lk3_rules(
        [
            Recommendation(
                title="Consider insulin class as teaching",
                detail=f"{DISCLAIMER} Discuss insulin class mentioned in the teaching card; not a prescription.",
                citations=["Educational diabetes teaching card"],
            )
        ],
        _cr001_patient(),
        _cr001_medical(),
        docs,
        pad_with=build_heuristic_recommendations(_cr001_patient(), _cr001_medical(), docs),
    )
    assert any("insulin" in f"{item.title} {item.detail}".lower() for item in recs)


def test_patient_name_allowed_but_mrn_stripped():
    from app.summarize.recommend_rules import apply_lk3_rules

    patient = PatientData(name="Jordan Hale (synthetic)", mrn="SYN-1001", source_case_id="CR-001")
    recs = apply_lk3_rules(
        [
            Recommendation(
                title="Discuss glycemic follow-up and HbA1c trend",
                detail=f"{DISCLAIMER} Consider follow-up for Jordan Hale (synthetic), MRN SYN-1001 CR-001.",
                citations=["Educational diabetes teaching card"],
            )
        ],
        patient,
        _cr001_medical(),
        [_diabetes_doc()],
        pad_with=build_heuristic_recommendations(patient, _cr001_medical(), [_diabetes_doc()]),
    )
    blob = " ".join(f"{item.title} {item.detail}" for item in recs)
    assert "Jordan Hale (synthetic)" in blob
    assert "SYN-1001" not in blob
    assert "CR-001" not in blob
    assert "MRN" not in blob


def test_citation_lock_strips_unknown_titles_and_reattaches_top_doc():
    recs = [
        Recommendation(
            title="Discuss glycemic follow-up",
            detail=f"{DISCLAIMER} Consider HbA1c trend.",
            citations=["NICE NG28", "Educational diabetes teaching card"],
        ),
        Recommendation(
            title="Invented source",
            detail=f"{DISCLAIMER} Consider follow-up.",
            citations=["UpToDate"],
        ),
    ]
    locked = lock_citations(recs, [_diabetes_doc()])
    assert "NICE NG28" not in locked[0].citations
    assert locked[0].citations == ["Educational diabetes teaching card"]
    assert locked[1].citations == ["Type 2 diabetes teaching card"]


def test_empty_citations_attach_top_scoring_doc_title():
    low = RetrievedDoc(
        id="low",
        title="Lower scoring card",
        topic="general",
        source="other.md",
        text="General teaching.",
        score=0.1,
        citation="General teaching citation",
    )
    high = RetrievedDoc(
        id="high",
        title="Highest scoring diabetes card",
        topic="diabetes",
        source="diabetes.md",
        text="HbA1c teaching.",
        score=9.0,
        citation="Diabetes citation string",
    )
    locked = lock_citations(
        [Recommendation(title="Discuss follow-up", detail=DISCLAIMER, citations=["NICE NG28"])],
        [low, high],
    )
    assert locked[0].citations == ["Highest scoring diabetes card"]


def test_live_path_uses_langchain_output_then_locks_citations(monkeypatch):
    from app.config import get_settings
    from app.summarize import recommend as recommend_mod

    monkeypatch.setenv("MOCK_LLM", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    get_settings.cache_clear()

    class FakeLLM:
        def invoke(self, _messages):
            class Response:
                content = json.dumps(
                    [
                        {
                            "title": "Discuss glycemic follow-up and HbA1c trend",
                            "detail": f"{DISCLAIMER} Consider reviewing HbA1c 9.2 % for Jordan Hale (synthetic).",
                            "citations": ["NICE NG28", "Educational diabetes teaching card"],
                        },
                        {
                            "title": "Consider metformin adherence discussion",
                            "detail": f"{DISCLAIMER} Discuss documented metformin only.",
                            "citations": ["Educational diabetes teaching card"],
                        },
                        {
                            "title": "Consider teaching points from Type 2 diabetes teaching card",
                            "detail": f"{DISCLAIMER} Discuss the retrieved diabetes card.",
                            "citations": ["Type 2 diabetes teaching card"],
                        },
                    ]
                )

            return Response()

    monkeypatch.setattr(recommend_mod, "_build_langchain_llm", lambda: FakeLLM())
    recs = create_recommendations(_cr001_patient(), _cr001_medical(), [_diabetes_doc()])
    get_settings.cache_clear()

    allowed = {"Type 2 diabetes teaching card", "Educational diabetes teaching card"}
    assert 3 <= len(recs) <= 6
    assert all(set(item.citations) <= allowed for item in recs)
    assert all("NICE" not in c for item in recs for c in item.citations)


def test_lk5_cli_prints_json_recs(tmp_path: Path, capsys):
    patient_path = tmp_path / "patient.json"
    medical_path = tmp_path / "medical.json"
    docs_path = tmp_path / "docs.json"
    patient_path.write_text((REPO / "data" / "expected" / "patient-CR-001.json").read_text(encoding="utf-8"))
    medical_path.write_text((REPO / "data" / "expected" / "medical-CR-001.json").read_text(encoding="utf-8"))
    docs_path.write_text(json.dumps([_diabetes_doc().model_dump()]), encoding="utf-8")

    assert main([str(patient_path), str(medical_path), str(docs_path)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list)
    assert payload[0]["title"]
    assert "citations" in payload[0]
    assert isinstance(payload[0]["citations"], list)


def test_lk5_recommend_does_not_import_teammate_functions():
    source = inspect.getsource(recommend_mod)
    assert "retrieve_guidelines" not in source
    assert "create_indepth_summary" not in source
    assert "ingest_guideline_corpus" not in source


def test_heuristic_one_rec_per_doc_cites_doc_title():
    second = RetrievedDoc(
        id="g-lipids",
        title="Lipid teaching card",
        topic="lipids",
        source="lipids.md",
        text="Discuss lipid follow-up as teaching only.",
        score=0.4,
        citation="Educational lipid card",
    )
    recs = build_heuristic_recommendations(_cr001_patient(), _cr001_medical(), [_diabetes_doc(), second])
    cited_titles = {c for rec in recs for c in rec.citations}
    assert "Type 2 diabetes teaching card" in cited_titles
    assert "Lipid teaching card" in cited_titles
    assert any(rec.citations == ["Type 2 diabetes teaching card"] for rec in recs)
    assert any(rec.citations == ["Lipid teaching card"] for rec in recs)


def test_heuristic_mentions_high_and_critical_labs():
    medical = MedicalData(
        problems=["type 2 diabetes"],
        labs=[
            LabFlag(analyte="HbA1c", value="9.2", unit="%", flag="high"),
            LabFlag(analyte="lactate", value="4.1", unit="mmol/L", flag="critical_high"),
        ],
    )
    recs = build_heuristic_recommendations(_cr001_patient(), medical, [_diabetes_doc()])
    blob = " ".join(f"{item.title} {item.detail}" for item in recs).lower()
    assert "hba1c" in blob
    assert "9.2" in blob
    assert "lactate" in blob
    assert "critical_high" in blob or "critical" in blob


def test_heuristic_empty_docs_exact_title_empty_citations():
    recs = build_heuristic_recommendations(_cr001_patient(), _cr001_medical(), [])
    assert len(recs) == 1
    assert recs[0].title == "Guideline evidence was not retrieved; clinician review required."
    assert recs[0].citations == []
    blob = json.dumps(recs[0].model_dump())
    assert "NICE" not in blob
    assert "UpToDate" not in blob


def test_heuristic_does_not_emit_sources_absent_from_docs():
    recs = build_heuristic_recommendations(_cr001_patient(), _cr001_medical(), [_diabetes_doc()])
    blob = json.dumps([item.model_dump() for item in recs])
    assert "NICE" not in blob
    assert "UpToDate" not in blob


def test_live_error_falls_back_to_heuristics(monkeypatch):
    from app.config import get_settings
    from app.summarize import recommend as recommend_mod

    monkeypatch.setenv("MOCK_LLM", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    get_settings.cache_clear()

    def boom() -> object:
        raise RuntimeError("gemini unavailable")

    monkeypatch.setattr(recommend_mod, "_build_langchain_llm", boom)
    recs = create_recommendations(_cr001_patient(), _cr001_medical(), [_diabetes_doc()])
    get_settings.cache_clear()

    assert recs
    assert any("Type 2 diabetes teaching card" in rec.citations for rec in recs)
    assert all("NICE" not in c for rec in recs for c in rec.citations)
