"""Adaptadores de generación y selección explícita de proveedor."""

from secguard_advisor.conversation.providers.base import (
    GeneratorProtocol,
    ProviderNotImplemented,
)
from secguard_advisor.conversation.providers.registry import ProviderRegistry

__all__ = ["GeneratorProtocol", "ProviderNotImplemented", "ProviderRegistry"]
