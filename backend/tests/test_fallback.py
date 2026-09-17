from app.llm.provider import LLMResult, complete_text


def test_openai_failure_falls_back_to_gemini(monkeypatch):
    from app.llm import provider

    class DummySettings:
        mock_llm = False
        has_openai = True
        has_gemini = True
        use_live_llm = True

    def boom(*_args, **_kwargs):
        raise RuntimeError("429 rate limit")

    def gemini(*_args, **_kwargs):
        return LLMResult(text="gemini-ok", model="gemini-2.0-flash", provider="gemini")

    monkeypatch.setattr(provider, "get_settings", lambda: DummySettings())
    monkeypatch.setattr(provider, "_call", lambda fn: fn())
    monkeypatch.setattr(provider, "_openai_complete", boom)
    monkeypatch.setattr(provider, "_gemini_complete", gemini)
    result = complete_text("sys", "user", "mock")
    assert result.provider == "gemini"
    assert result.fallback is True
    assert result.text == "gemini-ok"
