from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    app_env: str = "development"
    mock_llm: bool = True
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    enable_pubmed: bool = False
    enable_openfda: bool = False
    data_dir: Path = ROOT / "data"
    chroma_dir: Path = ROOT / "data" / "chroma"
    checkpoint_dir: Path = BACKEND_ROOT / ".checkpoints"
    log_dir: Path = BACKEND_ROOT / ".runs"
    runs_dir: Path = BACKEND_ROOT / ".runs" / "records"
    frontend_origin: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def use_live_llm(self) -> bool:
        return (not self.mock_llm) and (self.has_openai or self.has_gemini)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    return settings
