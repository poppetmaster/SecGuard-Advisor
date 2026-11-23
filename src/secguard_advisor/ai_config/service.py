"""Perfiles de IA administrables desde la interfaz (005).

La selección guardada en SQLite es la configuración activa. Si no existe, se
usan los valores iniciales de Settings/.env. Las claves, endpoints y
presupuestos siguen en .env y nunca se persisten aquí.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from secguard_advisor.config import Settings
from secguard_advisor.db.models import AIConfiguration, AIProviderProfile

PROVIDERS = ("ollama", "deepseek", "anthropic")
PROVIDER_LABELS = {
    "ollama": "Local — Ollama",
    "deepseek": "DeepSeek",
    "anthropic": "Claude — Anthropic",
}
DEFAULT_MODELS = {
    "ollama": "qwen3.5:9b",
    "deepseek": "deepseek-flash",
    "anthropic": "claude-haiku-5-5",
}
MODEL_CATALOG = {
    "ollama": {
        "qwen3.5:9b": {
            "confirmed": True,
            "source": "Modelo local configurado por el proyecto",
            "date": "2026-11-22",
        }
    },
    "deepseek": {
        "deepseek-flash": {
            "confirmed": True,
            "source": "https://api-docs.deepseek.com/quick_start/pricing",
            "date": "2026-11-22",
        }
    },
    "anthropic": {
        "claude-haiku-5-5": {
            "confirmed": True,
            "source": "https://platform.claude.com/docs/en/models/haiku-5-5/overview",
            "date": "2026-11-22",
        }
    },
}
_ALL_MODELS = {model for catalog in MODEL_CATALOG.values() for model in catalog}
_MODEL_OWNERS = {
    model: provider for provider, catalog in MODEL_CATALOG.items() for model in catalog
}


class AIConfigurationError(ValueError):
    """Configuración inválida o incompleta, con mensaje para el usuario."""


@dataclass(frozen=True, slots=True)
class ProviderProfile:
    provider: str
    model: str
    max_output_tokens: int
    timeout_seconds: float
    source: str
    model_status: str
    model_source: str | None
    model_date: str | None
    credential_status: str


@dataclass(frozen=True, slots=True)
class AIConfigurationView:
    active_provider: str
    active_profile: ProviderProfile
    profiles: dict[str, ProviderProfile]
    saved: bool
    global_budget_usd: Decimal
    run_budget_usd: Decimal
    currency: str
    external_blocked: bool
    connection_status: str


def credential_status(settings: Settings, provider: str) -> str:
    if provider == "ollama":
        return "not_required"
    key = settings.deepseek_api_key if provider == "deepseek" else settings.anthropic_api_key
    return "configured" if key is not None else "missing"


def _default_model(settings: Settings, provider: str) -> str:
    if provider == "ollama":
        return settings.ollama_model
    return DEFAULT_MODELS[provider]


def _environment_profile(settings: Settings, provider: str) -> ProviderProfile:
    model = (
        settings.provider_model
        if provider == settings.generation_provider
        else _default_model(settings, provider)
    )
    catalog = MODEL_CATALOG.get(provider, {}).get(model)
    return ProviderProfile(
        provider=provider,
        model=model,
        max_output_tokens=settings.provider_max_output_tokens,
        timeout_seconds=settings.provider_timeout_seconds,
        source=("environment" if provider == settings.generation_provider else "default"),
        model_status="confirmed" if catalog and catalog["confirmed"] else "unconfirmed",
        model_source=catalog["source"] if catalog else None,
        model_date=catalog["date"] if catalog else None,
        credential_status=credential_status(settings, provider),
    )


def _saved_profile(row: AIProviderProfile, settings: Settings) -> ProviderProfile:
    catalog = MODEL_CATALOG.get(row.provider, {}).get(row.model)
    return ProviderProfile(
        provider=row.provider,
        model=row.model,
        max_output_tokens=row.max_output_tokens,
        timeout_seconds=row.timeout_seconds,
        source="saved",
        model_status="confirmed" if catalog and catalog["confirmed"] else "unconfirmed",
        model_source=catalog["source"] if catalog else None,
        model_date=catalog["date"] if catalog else None,
        credential_status=credential_status(settings, row.provider),
    )


def load_view(session: Session, settings: Settings) -> AIConfigurationView:
    configuration = session.get(AIConfiguration, 1)
    saved = configuration is not None
    active_provider = (
        configuration.active_provider if configuration else settings.generation_provider
    )
    rows = {row.provider: row for row in session.query(AIProviderProfile).all()}
    profiles = {}
    for provider in PROVIDERS:
        row = rows.get(provider)
        profiles[provider] = (
            _saved_profile(row, settings) if row else _environment_profile(settings, provider)
        )
    active_profile = profiles[active_provider]
    external_blocked = active_provider != "ollama" and (
        settings.external_budget_usd <= 0 or settings.external_run_budget_usd <= 0
    )
    return AIConfigurationView(
        active_provider=active_provider,
        active_profile=active_profile,
        profiles=profiles,
        saved=saved,
        global_budget_usd=settings.external_budget_usd,
        run_budget_usd=settings.external_run_budget_usd,
        currency="USD",
        external_blocked=external_blocked,
        connection_status="not_verified",
    )


def resolve_turn_settings(session: Session, settings: Settings) -> Settings:
    """Instantánea coherente del perfil activo para un turno nuevo."""
    view = load_view(session, settings)
    active = view.active_profile
    return settings.model_copy(
        update={
            "generation_provider": active.provider,
            "generation_model": active.model,
            "generation_max_output_tokens": active.max_output_tokens,
            "generation_timeout_seconds": active.timeout_seconds,
        }
    )


def _max_output_limit(settings: Settings) -> int:
    return min(128_000, settings.provider_context_window - settings.context_safety_margin_tokens)


def save_configuration(
    session: Session,
    settings: Settings,
    *,
    provider: str,
    model: str,
    max_output_tokens: int,
    timeout_seconds: float,
) -> AIConfigurationView:
    if provider not in PROVIDERS:
        raise AIConfigurationError("El proveedor seleccionado no es válido.")
    if credential_status(settings, provider) == "missing":
        variable = "DEEPSEEK_API_KEY" if provider == "deepseek" else "ANTHROPIC_API_KEY"
        raise AIConfigurationError(
            f"Falta {variable} en .env. Configurá la credencial antes de guardar este proveedor."
        )
    normalized_model = (model or "").strip() or DEFAULT_MODELS[provider]
    owner = _MODEL_OWNERS.get(normalized_model)
    if owner is not None and owner != provider:
        raise AIConfigurationError(
            f"El modelo «{normalized_model}» pertenece a otro proveedor. "
            f"Elegí un identificador compatible con {PROVIDER_LABELS[provider]}."
        )
    limit = _max_output_limit(settings)
    if not isinstance(max_output_tokens, int) or not 1 <= max_output_tokens <= limit:
        raise AIConfigurationError(f"El máximo de tokens de salida debe estar entre 1 y {limit}.")
    if not 0 < timeout_seconds <= settings.run_timeout_seconds:
        raise AIConfigurationError(
            f"El tiempo máximo por llamada debe ser mayor que 0 y no superar "
            f"{settings.run_timeout_seconds:g} s."
        )

    now = datetime.now(UTC).isoformat()
    profile = session.get(AIProviderProfile, provider)
    if profile is None:
        profile = AIProviderProfile(
            provider=provider,
            model=normalized_model,
            max_output_tokens=max_output_tokens,
            timeout_seconds=timeout_seconds,
            updated_at=now,
        )
        session.add(profile)
    else:
        profile.model = normalized_model
        profile.max_output_tokens = max_output_tokens
        profile.timeout_seconds = timeout_seconds
        profile.updated_at = now
    configuration = session.get(AIConfiguration, 1)
    if configuration is None:
        configuration = AIConfiguration(active_provider=provider, updated_at=now)
        session.add(configuration)
    else:
        configuration.active_provider = provider
        configuration.updated_at = now
    session.flush()
    return load_view(session, settings)
