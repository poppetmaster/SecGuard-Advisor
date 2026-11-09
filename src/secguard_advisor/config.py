"""Configuración de la aplicación."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from secguard_advisor import __version__


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

    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434", validation_alias="OLLAMA_BASE_URL"
    )
    ollama_model: str = Field(default="qwen3.5:9b", validation_alias="OLLAMA_MODEL")
    ollama_embedding_model: str = Field(
        default="embeddinggemma", validation_alias="OLLAMA_EMBEDDING_MODEL"
    )
    embedding_dim: int = 768
    embedding_context_tokens: int = 2048

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
    # Calibrado con datos de humo: preguntas pertinentes >= 0.58, fuera de dominio <= 0.05.
    # Es un filtro de candidatos débiles, no una prueba de ausencia de evidencia.
    retrieval_min_score: float = 0.35
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

    langsmith_tracing: bool = Field(default=False, validation_alias="LANGSMITH_TRACING")
    langsmith_endpoint: str = Field(
        default="https://api.smith.langchain.com",
        validation_alias="LANGSMITH_ENDPOINT",
    )
    langsmith_api_key: SecretStr | None = Field(default=None, validation_alias="LANGSMITH_API_KEY")
    langsmith_project: str = Field(
        default="secguard-advisor-dev", validation_alias="LANGSMITH_PROJECT"
    )

    @field_validator("reviewer_name", "langsmith_api_key", mode="before")
    @classmethod
    def _empty_string_is_none(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.storage_dir / 'secguard.sqlite3'}"

    @property
    def checkpoints_path(self) -> Path:
        return self.storage_dir / "checkpoints.sqlite"

    @property
    def chroma_dir(self) -> Path:
        return self.storage_dir / "chroma"

    @property
    def originals_dir(self) -> Path:
        return self.storage_dir / "originals"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    def ensure_directories(self) -> None:
        """Crea los directorios locales de almacenamiento."""
        for path in (self.storage_dir, self.chroma_dir, self.originals_dir):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Devuelve la configuración cacheada del proceso."""
    return Settings()
