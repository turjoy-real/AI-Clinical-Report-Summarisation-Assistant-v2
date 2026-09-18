from app.tools.pdf import PdfExtractError, extract_pdf_text


def test_flaky_pdf_extract_succeeds_on_retry(monkeypatch):
    attempts = {"n": 0}

    class FakePage:
        def extract_text(self):
            return "Synthetic readable clinical note with enough characters for ingest."

    class FakeReader:
        pages = [FakePage()]

        def __init__(self, _source):
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise OSError("temporary parse failure")

    monkeypatch.setattr("app.tools.pdf.PdfReader", FakeReader)
    text = extract_pdf_text(b"%PDF-fake")
    assert "Synthetic readable" in text
    assert attempts["n"] == 3


def test_exhausted_retries_surface_error(monkeypatch):
    class FakeReader:
        def __init__(self, _source):
            raise OSError("permanent failure")

    monkeypatch.setattr("app.tools.pdf.PdfReader", FakeReader)
    try:
        extract_pdf_text(b"%PDF-fake")
        assert False, "should have failed"
    except OSError as exc:
        assert "permanent failure" in str(exc)


def test_empty_pdf_is_pdf_extract_error(monkeypatch):
    class FakePage:
        def extract_text(self):
            return "??"

    class FakeReader:
        pages = [FakePage()]

        def __init__(self, _source):
            pass

    monkeypatch.setattr("app.tools.pdf.PdfReader", FakeReader)
    try:
        extract_pdf_text(b"%PDF-fake")
        assert False, "should have failed"
    except PdfExtractError:
        pass
