"""Settings loaded from the environment / `.env` (template: `.env.example`)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM provider
    llm_provider: Literal["azure", "openai"] = "azure"
    azure_openai_endpoint: str = ""
    azure_openai_api_key: SecretStr = SecretStr("")
    azure_openai_api_version: str = ""
    openai_api_key: SecretStr = SecretStr("")

    # Deployments per role (SPEC §7.1)
    azure_openai_deployment: str = "gpt-4.1-mini"
    azure_openai_fallback_deployment: str = "gpt-5.4-mini"
    azure_openai_repair_deployment: str = "gpt-5-mini"
    azure_openai_cheap_deployment: str = "gpt-5.4-nano"
    azure_openai_embed_deployment: str = "text-embedding-3-small"
    azure_openai_deployment_version: str = ""
    azure_openai_fallback_deployment_version: str = ""
    azure_openai_repair_deployment_version: str = ""
    azure_openai_cheap_deployment_version: str = ""
    pilot_deployments: str = "gpt-4.1-mini,gpt-5.4-mini,gpt-5.4-nano"

    # Limits and budget
    tier1_tpm: int = 500_000
    repair_tpm: int = 375_000
    cheap_tpm: int = 200_000
    tier1_max_tokens: int = 800
    llm_max_concurrency: int = Field(default=16, ge=1)
    max_llm_usd: float = Field(default=20.0, ge=0)
    llm_cache_dir: str = "artifacts/llm_cache"

    # Local models
    embed_base_model: str = "BAAI/bge-small-en-v1.5"
    # search / RAG encoder: the fine-tuned serving model (M9 passed its use rule) or empty = the base model; the
    # verifier agent always uses the base model. The model is private (MODEL_STORE), never in the repository.
    search_embed_model: str = "./models/serving/model"
    # sentence points carry the predicted-label prefix (M8 comparison rows only; default plain sentences, SPEC §6.3)
    index_sentence_prefix: bool = False
    reranker_model: str = "BAAI/bge-reranker-base"
    device: Literal["auto", "cpu", "cuda"] = "auto"
    model_store: str = "./models"

    # Services
    database_url: str = "postgresql://radlabel:radlabel@postgres:5432/radlabel"
    qdrant_url: str = "http://qdrant:6333"
    redis_url: str = "redis://redis:6379/0"

    # Tracing
    tracing_backend: Literal["phoenix", "langfuse", "none"] = "phoenix"
    phoenix_collector_endpoint: str = "http://phoenix:6006"
    langfuse_public_key: str = ""
    langfuse_secret_key: SecretStr = SecretStr("")
    langfuse_host: str = ""

    # App
    seed: int = 13
    api_rate_limit: str = "30/minute"  # per client IP, website API
    log_level: str = "INFO"

    # Website session API (M10a): uploads live in memory only
    web_daily_cap_usd: float = Field(default=1.0, ge=0)  # LLM spend per day, on top of the global stop
    web_max_reports: int = Field(default=50, ge=1)  # per session
    web_max_text_chars: int = Field(default=20_000, ge=100)  # per report
    web_max_file_bytes: int = Field(default=2_000_000, ge=1_000)
    web_session_ttl_minutes: int = Field(default=60, ge=1)  # idle expiry
    web_cors_origins: str = "http://localhost:5173"  # comma-separated (the Vercel URL in deployment)

    @property
    def pilot_list(self) -> list[str]:
        return [d.strip() for d in self.pilot_deployments.split(",") if d.strip()]

    def missing_llm_settings(self) -> list[str]:
        """Names of settings a fresh (uncached) LLM call needs but that are empty."""
        if self.llm_provider == "openai":
            return [] if self.openai_api_key.get_secret_value() else ["OPENAI_API_KEY"]
        # AZURE_OPENAI_API_VERSION is optional: empty -> Azure's GA v1 API (no api-version parameter)
        need = {
            "AZURE_OPENAI_ENDPOINT": self.azure_openai_endpoint,
            "AZURE_OPENAI_API_KEY": self.azure_openai_api_key.get_secret_value(),
        }
        return [k for k, v in need.items() if not v or "<your-resource>" in v]

    def require_llm(self) -> None:
        missing = self.missing_llm_settings()
        if missing:
            raise RuntimeError(
                f"LLM call needs settings that are empty in .env: {', '.join(missing)}. "
                "Fill them in, or run offline (cache / FakeLLM)."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
