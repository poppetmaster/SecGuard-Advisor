"""Configuración de la aplicación."""

import re
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from secguard_advisor import __version__

# Slug de instancia: estable, opaco y sin rutas. Compartido con retrieval.instance.
INSTANCE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{2,39}$")


class Settings(BaseSettings):
    """Configuración resuelta desde entorno y ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
        case_sensitive=False,
    )

    app_env: str = Field(default="development", validation_alias="APP_ENV")
    app_version: str = __version__
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    storage_dir: Path = Field(default=Path("./storage"), validation_alias="SECGUARD_STORAGE_DIR")
    corpus_dir: Path = Field(default=Path("data/corpus"), validation_alias="SECGUARD_CORPUS_DIR")

    # Identidad de instancia para el namespace de Qdrant. Opcional mientras Chroma
    # siga siendo el backend documental; obligatoria para usar Qdrant.
    instance_id: str | None = Field(default=None, validation_alias="SECGUARD_INSTANCE_ID")
    qdrant_url: str = Field(default="http://127.0.0.1:6333", validation_alias="SECGUARD_QDRANT_URL")
    qdrant_timeout_seconds: float = Field(
        default=5.0, validation_alias="SECGUARD_QDRANT_TIMEOUT_SECONDS"
    )

    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434", validation_alias="OLLAMA_BASE_URL"
    )
    ollama_model: str = Field(default="qwen3.5:9b", validation_alias="OLLAMA_MODEL")
    ollama_embedding_model: str = Field(
        default="embeddinggemma", validation_alias="OLLAMA_EMBEDDING_MODEL"
    )
    embedding_dim: int = 768
    embedding_context_tokens: int = 2048

    # Selección explícita del generador (005). Compatibilidad: para Ollama, los
    # nombres nuevos tienen precedencia sobre los anteriores:
    #   SECGUARD_GENERATION_MODEL > OLLAMA_MODEL
    #   SECGUARD_GENERATION_MAX_OUTPUT_TOKENS > generator_num_predict
    #   SECGUARD_GENERATION_TIMEOUT_SECONDS > llm_timeout_seconds
    generation_provider: Literal["ollama", "deepseek", "anthropic"] = Field(
        default="ollama", validation_alias="SECGUARD_GENERATION_PROVIDER"
    )
    generation_model: str | None = Field(default=None, validation_alias="SECGUARD_GENERATION_MODEL")
    generation_max_output_tokens: int | None = Field(
        default=None, validation_alias="SECGUARD_GENERATION_MAX_OUTPUT_TOKENS"
    )
    generation_timeout_seconds: float | None = Field(
        default=None, validation_alias="SECGUARD_GENERATION_TIMEOUT_SECONDS"
    )
    generation_reasoning: Literal["off", "low", "high"] = Field(
        default="off", validation_alias="SECGUARD_GENERATION_REASONING"
    )
    deepseek_api_key: SecretStr | None = Field(default=None, validation_alias="DEEPSEEK_API_KEY")
    anthropic_api_key: SecretStr | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    external_budget_usd: Decimal = Field(
        default=Decimal("0"), validation_alias="SECGUARD_EXTERNAL_BUDGET_USD"
    )
    external_run_budget_usd: Decimal = Field(
        default=Decimal("0"), validation_alias="SECGUARD_EXTERNAL_RUN_BUDGET_USD"
    )
    external_tariff_version: str = Field(
        default="2026-11-22", validation_alias="SECGUARD_EXTERNAL_TARIFF_VERSION"
    )
    external_context_window_tokens: int = Field(
        default=128_000, validation_alias="SECGUARD_EXTERNAL_CONTEXT_WINDOW_TOKENS"
    )
    external_estimate_chars_per_token: float = Field(
        default=2.0, validation_alias="SECGUARD_EXTERNAL_ESTIMATE_CHARS_PER_TOKEN"
    )
    external_estimate_overhead_tokens: int = Field(
        default=64, validation_alias="SECGUARD_EXTERNAL_ESTIMATE_OVERHEAD_TOKENS"
    )
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com", validation_alias="DEEPSEEK_BASE_URL"
    )
    anthropic_base_url: str = Field(
        default="https://api.anthropic.com", validation_alias="ANTHROPIC_BASE_URL"
    )
    anthropic_version: str = Field(default="2026-10-21", validation_alias="ANTHROPIC_VERSION")

    generator_num_ctx: int = 8192
    generator_num_predict: int = 1200
    # Margen de seguridad del presupuesto de contexto previo a cada llamada.
    context_safety_margin_tokens: int = 320
    generator_temperature: float = 0.1
    generator_seed: int = 42
    llm_timeout_seconds: float = 90.0
    run_timeout_seconds: float = 120.0
    max_graph_steps: int = 8
    max_tool_calls: int = 2
    tool_timeout_seconds: float = 5.0

    retrieval_top_k: int = 6
    # Presupuesto de evidencia por turno: tokens exactos medidos al ingerir.
    retrieval_token_budget: int = 3500
    # Calibrado con Qdrant servidor + EmbeddingGemma (2026-11-22, iteración 2):
    # pertinentes >= 0.5033; no pertinentes <= 0.2785. Es un filtro de candidatos
    # débiles, no una prueba de ausencia de evidencia.
    retrieval_min_score: float = 0.5033
    # Historial acotado: turnos completos, del más nuevo al más viejo.
    history_max_messages: int = 8
    history_max_chars: int = 6000

    generation_queue_timeout_seconds: float = Field(
        default=5.0,
        validation_alias="SECGUARD_GENERATION_QUEUE_TIMEOUT_SECONDS",
    )
    reviewer_name: str | None = Field(default=None, validation_alias="SECGUARD_REVIEWER_NAME")

    max_upload_mb: int = 20

    qualys_max_bytes: int = Field(
        default=10 * 1024 * 1024, validation_alias="SECGUARD_QUALYS_MAX_BYTES"
    )
    qualys_max_rows: int = Field(default=10_000, validation_alias="SECGUARD_QUALYS_MAX_ROWS")
    qualys_max_field_chars: int = Field(
        default=20_000, validation_alias="SECGUARD_QUALYS_MAX_FIELD_CHARS"
    )
    qualys_max_cves: int = Field(default=1_000, validation_alias="SECGUARD_QUALYS_MAX_CVES")
    qualys_staging_ttl_seconds: int = Field(
        default=86_400, validation_alias="SECGUARD_QUALYS_STAGING_TTL_SECONDS"
    )

    telegram_bot_token: SecretStr | None = Field(
        default=None, validation_alias="TELEGRAM_BOT_TOKEN"
    )
    telegram_transport: Literal["stub", "real"] = Field(
        default="stub", validation_alias="SECGUARD_TELEGRAM_TRANSPORT"
    )
    telegram_api_base_url: str = Field(
        default="https://api.telegram.org", validation_alias="TELEGRAM_API_BASE_URL"
    )

    langsmith_tracing: bool = Field(default=False, validation_alias="LANGSMITH_TRACING")
    langsmith_endpoint: str = Field(
        default="https://api.smith.langchain.com",
        validation_alias="LANGSMITH_ENDPOINT",
    )
    langsmith_api_key: SecretStr | None = Field(default=None, validation_alias="LANGSMITH_API_KEY")
    langsmith_project: str = Field(
        default="secguard-advisor-dev", validation_alias="LANGSMITH_PROJECT"
    )

    @field_validator(
        "reviewer_name",
        "langsmith_api_key",
        "telegram_bot_token",
        "instance_id",
        "generation_model",
        "deepseek_api_key",
        "anthropic_api_key",
        mode="before",
    )
    @classmethod
    def _empty_string_is_none(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("instance_id")
    @classmethod
    def _validate_instance_id(cls, value: str | None) -> str | None:
        if value is not None and not INSTANCE_ID_PATTERN.fullmatch(value):
            raise ValueError(
                "SECGUARD_INSTANCE_ID debe ser un slug de 3 a 40 caracteres "
                "en minusculas, digitos o guiones."
            )
        return value

    @field_validator("generation_max_output_tokens")
    @classmethod
    def _validate_generation_max_output(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("SECGUARD_GENERATION_MAX_OUTPUT_TOKENS debe ser mayor que cero.")
        return value

    @field_validator("generation_timeout_seconds")
    @classmethod
    def _validate_generation_timeout(cls, value: float | None) -> float | None:
        if value is not None and value <= 0:
            raise ValueError("SECGUARD_GENERATION_TIMEOUT_SECONDS debe ser mayor que cero.")
        return value

    @field_validator("external_context_window_tokens")
    @classmethod
    def _validate_external_context_window(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("SECGUARD_EXTERNAL_CONTEXT_WINDOW_TOKENS debe ser mayor que cero.")
        return value

    @field_validator("external_estimate_chars_per_token")
    @classmethod
    def _validate_estimate_ratio(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("SECGUARD_EXTERNAL_ESTIMATE_CHARS_PER_TOKEN debe ser mayor que cero.")
        return value

    @field_validator("external_estimate_overhead_tokens")
    @classmethod
    def _validate_estimate_overhead(cls, value: int) -> int:
        if value < 0:
            raise ValueError("SECGUARD_EXTERNAL_ESTIMATE_OVERHEAD_TOKENS no puede ser negativo.")
        return value

    @field_validator("external_budget_usd", "external_run_budget_usd")
    @classmethod
    def _validate_budget(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("El presupuesto externo no puede ser negativo.")
        return value

    @model_validator(mode="after")
    def _validate_provider_credentials(self) -> Settings:
        if self.generation_provider == "deepseek" and self.deepseek_api_key is None:
            raise ValueError(
                "DEEPSEEK_API_KEY es obligatoria cuando SECGUARD_GENERATION_PROVIDER=deepseek."
            )
        if self.generation_provider == "anthropic" and self.anthropic_api_key is None:
            raise ValueError(
                "ANTHROPIC_API_KEY es obligatoria cuando SECGUARD_GENERATION_PROVIDER=anthropic."
            )
        return self

    @field_validator("qdrant_url")
    @classmethod
    def _validate_qdrant_url(cls, value: str) -> str:
        parts = urlsplit(value)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise ValueError("SECGUARD_QDRANT_URL debe ser una URL http(s) con host.")
        return value

    @property
    def provider_model(self) -> str:
        """Modelo efectivo del proveedor activo, con compatibilidad Ollama."""
        if self.generation_model:
            return self.generation_model
        if self.generation_provider == "ollama":
            return self.ollama_model
        return {"deepseek": "deepseek-flash", "anthropic": "claude-haiku-5-5"}[
            self.generation_provider
        ]

    @property
    def provider_context_window(self) -> int:
        """Ventana de contexto efectiva del proveedor activo."""
        if self.generation_provider == "ollama":
            return self.generator_num_ctx
        return self.external_context_window_tokens

    @property
    def provider_max_output_tokens(self) -> int:
        """Límite de salida efectivo del proveedor activo."""
        if self.generation_max_output_tokens is not None:
            return self.generation_max_output_tokens
        return self.generator_num_predict

    @property
    def provider_timeout_seconds(self) -> float:
        """Timeout efectivo por llamada del proveedor activo."""
        if self.generation_timeout_seconds is not None:
            return self.generation_timeout_seconds
        return self.llm_timeout_seconds

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.storage_dir / 'secguard.sqlite3'}"

    @property
    def checkpoints_path(self) -> Path:
        return self.storage_dir / "checkpoints.sqlite"

    @property
    def originals_dir(self) -> Path:
        return self.storage_dir / "originals"

    @property
    def reports_dir(self) -> Path:
        return self.storage_dir / "reports"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    def ensure_directories(self) -> None:
        """Crea los directorios locales de almacenamiento."""
        for path in (self.storage_dir, self.originals_dir, self.reports_dir):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Devuelve la configuración cacheada del proceso."""
    return Settings()
