"""Conteo de tokens compatible con el tokenizador del generador.

El vocabulario y las fusiones BPE se leen del GGUF ya instalado por Ollama; no se
descargan modelos ni se hacen llamadas adicionales. La plantilla de conversación
reproduce el renderizador Qwen3.5 de Ollama, verificado contra `prompt_eval_count`.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from gguf import GGUFReader
from tokenizers import Tokenizer
from tokenizers.models import BPE
from tokenizers.pre_tokenizers import ByteLevel

# Renderizador Qwen3.5 de Ollama: system + user + turno de asistente sin razonamiento.
# Verificado contra `prompt_eval_count` (coincidencia exacta con un prompt mínimo).
CHAT_TEMPLATE = (
    "<|im_start|>system\n{system}<|im_end|>\n"
    "<|im_start|>user\n{user}<|im_end|>\n"
    "<|im_start|>assistant\n<think>\n\n</think>\n\n"
)
_SPECIAL_EXTRA = {"<think>", "</think>"}


class TokenizerUnavailable(RuntimeError):
    """No se pudo cargar el tokenizador del modelo instalado."""


def _models_root() -> Path:
    configured = os.environ.get("OLLAMA_MODELS")
    if configured:
        return Path(configured)
    return Path.home() / ".ollama" / "models"


def _manifest_candidates(models_root: Path, model: str) -> list[Path]:
    name, _, tag = model.rpartition(":")
    if not name:
        name, tag = model, "latest"
    parts = name.split("/")
    if len(parts) == 1:
        return [models_root / "manifests" / "registry.ollama.ai" / "library" / name / tag]
    namespace = "/".join(parts[:-1])
    model_name = parts[-1]
    return [
        models_root / "manifests" / "registry.ollama.ai" / namespace / model_name / tag,
        models_root / "manifests" / namespace / model_name / tag,
    ]


def model_gguf_path(model: str) -> Path:
    """Localiza el GGUF del modelo instalado a partir del manifiesto de Ollama."""
    models_root = _models_root()
    for manifest in _manifest_candidates(models_root, model):
        if not manifest.exists():
            continue
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        for layer in payload.get("layers", []):
            media_type = layer.get("mediaType", "")
            digest = layer.get("digest", "")
            if media_type.endswith("image.model") and digest.startswith("sha256:"):
                return models_root / "blobs" / digest.replace(":", "-")
    raise TokenizerUnavailable(f"No se encontró el GGUF instalado para «{model}» en {models_root}.")


@dataclass(frozen=True, slots=True)
class PromptCounter:
    """Conteo del prompt completo con la plantilla del generador."""

    tokenizer: Tokenizer
    model: str
    template: str = "qwen35-chat"

    def render(self, system: str, user: str) -> str:
        return CHAT_TEMPLATE.format(system=system, user=user)

    def count(self, system: str, user: str) -> int:
        rendered = self.render(system, user)
        return len(self.tokenizer.encode(rendered, add_special_tokens=False).ids)

    def count_text(self, text: str) -> int:
        """Conteo del tokenizador sin plantilla; solo para diagnóstico."""
        return len(self.tokenizer.encode(text, add_special_tokens=False).ids)

    def describe(self) -> dict:
        return {
            "method": "tokenizer",
            "model": self.model,
            "template": self.template,
        }


def build_tokenizer(tokens: list[str], merges: list[tuple[str, str]]) -> Tokenizer:
    """Reconstruye el BPE del modelo y registra sus tokens especiales."""
    tokenizer = Tokenizer(BPE({token: index for index, token in enumerate(tokens)}, merges))
    tokenizer.pre_tokenizer = ByteLevel(add_prefix_space=False, use_regex=True)
    special = [
        token
        for token in tokens
        if (token.startswith("<|") and token.endswith("|>")) or token in _SPECIAL_EXTRA
    ]
    if special:
        tokenizer.add_special_tokens(special)
    return tokenizer


@lru_cache(maxsize=2)
def load_prompt_counter(model: str) -> PromptCounter:
    """Carga el tokenizador una vez por proceso desde el GGUF instalado."""
    path = model_gguf_path(model)
    try:
        reader = GGUFReader(str(path))
        tokens = [str(token) for token in reader.get_field("tokenizer.ggml.tokens").contents()]
        merges = [
            tuple(str(merge).split(" "))
            for merge in reader.get_field("tokenizer.ggml.merges").contents()
        ]
    except Exception as exc:
        raise TokenizerUnavailable(f"No se pudo leer el tokenizador de «{model}»: {exc}") from exc
    if not tokens or not merges:
        raise TokenizerUnavailable(f"El GGUF de «{model}» no contiene tokenizador.")
    return PromptCounter(tokenizer=build_tokenizer(tokens, merges), model=model)


class LazyPromptCounter:
    """Carga diferida: la aplicación arranca aunque el modelo se instale después."""

    def __init__(self, model: str) -> None:
        self._model = model

    def count(self, system: str, user: str) -> int:
        return load_prompt_counter(self._model).count(system, user)

    def describe(self) -> dict:
        return {"method": "tokenizer", "model": self._model, "template": "qwen35-chat"}
