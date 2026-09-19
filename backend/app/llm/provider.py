from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.logging.observability import metrics


@dataclass
class LLMResult:
    text: str
    model: str
    tokens: int = 0
    provider: str = "mock"
    fallback: bool = False


class ProviderError(RuntimeError):
    pass


def _openai_complete(system: str, user: str) -> LLMResult:
    settings = get_settings()
    if not settings.has_openai:
        raise ProviderError("OpenAI key missing")
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key, timeout=20.0)
    response = client.chat.completions.create(
        model=settings.openai_model,
        temperature=0.1,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    choice = response.choices[0].message.content or ""
    tokens = response.usage.total_tokens if response.usage else 0
    return LLMResult(text=choice, model=settings.openai_model, tokens=tokens, provider="openai")


def _gemini_complete(system: str, user: str) -> LLMResult:
    settings = get_settings()
    if not settings.has_gemini:
        raise ProviderError("Gemini key missing")
    import google.generativeai as genai

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(settings.gemini_model, system_instruction=system)
    response = model.generate_content(user, request_options={"timeout": 20})
    text = response.text or ""
    return LLMResult(text=text, model=settings.gemini_model, tokens=0, provider="gemini")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.4, min=0.4, max=4), reraise=True)
def _call(fn: Callable[[], LLMResult]) -> LLMResult:
    return fn()


def complete_text(system: str, user: str, mock: str) -> LLMResult:
    settings = get_settings()
    if not settings.use_live_llm:
        return LLMResult(text=mock, model="mock-heuristic", provider="mock")
    errors: list[str] = []
    if settings.has_openai:
        try:
            return _call(lambda: _openai_complete(system, user))
        except Exception as exc:
            errors.append(f"openai:{exc}")
            metrics.fallbacks += 1
    if settings.has_gemini:
        try:
            result = _call(lambda: _gemini_complete(system, user))
            result.fallback = bool(errors)
            return result
        except Exception as exc:
            errors.append(f"gemini:{exc}")
            metrics.fallbacks += 1
    return LLMResult(text=mock, model="mock-heuristic", provider="mock", fallback=True)


def complete_json(system: str, user: str, mock: dict[str, Any]) -> LLMResult:
    result = complete_text(system + "\nReturn valid JSON only.", user, json.dumps(mock))
    try:
        json.loads(result.text)
        return result
    except json.JSONDecodeError:
        return LLMResult(text=json.dumps(mock), model=result.model, provider=result.provider, fallback=True)
