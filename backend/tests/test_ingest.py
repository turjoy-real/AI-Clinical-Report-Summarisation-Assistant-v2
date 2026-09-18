from app.config import get_settings
from app.graph.workflow import ingest_node


def test_garbled_case_fails_closed():
    text = (get_settings().data_dir / "reports" / "CR-011.md").read_text(encoding="utf-8")
    result = ingest_node({"raw_text": text, "report_type": "text"})
    assert result["status"] == "ingest_failed"
    assert "paste" in result["ingest_error"].lower()


def test_uploaded_pdf_filename_does_not_reopen_missing_path():
    text = (get_settings().data_dir / "reports" / "CR-001.md").read_text(encoding="utf-8")
    result = ingest_node({"raw_text": text, "report_type": "CR-001.pdf"})
    assert result["status"] == "ingested"
    assert "9.2" in result["extracted_text"]


def test_empty_note_fails_closed():
    result = ingest_node({"raw_text": "", "report_type": "text"})
    assert result["status"] == "ingest_failed"
    assert "Paste the note as text." in result["ingest_error"]
