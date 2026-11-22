"""Errores clasificados del índice documental.

Los códigos coinciden con la taxonomía de `web/errors.py` y con la evidencia.
"""

from __future__ import annotations


class IndexError(Exception):
    """Fallo del índice derivado con código clasificado."""

    code = "index_error"
    status = 503


class QdrantUnavailable(IndexError):
    code = "qdrant_unavailable"
    status = 503


class CaseIndexUnavailable(IndexError):
    code = "case_index_unavailable"
    status = 503


class PublicIndexUnavailable(IndexError):
    code = "public_index_unavailable"
    status = 503


class IndexConfigurationError(IndexError):
    code = "instance_namespace_mismatch"
    status = 503
