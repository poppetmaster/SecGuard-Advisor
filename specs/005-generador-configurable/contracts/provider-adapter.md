# Contract: Provider adapter (005)

**Fecha**: 2026-11-22

## Protocolo común

Todo generador implementa:

```python
class Generator(Protocol):
    provider: str  # "ollama" | "deepseek" | "anthropic"
    model: str
    identity: str | None  # digest local o identificador/versión externa observada
    last_usage: dict | None

    def decide(
        self, *, system: str, user: str, timeout_seconds: float | None = None
    ) -> ToolDecision: ...
    def generate(
        self, *, system: str, user: str, timeout_seconds: float | None = None
    ) -> AnswerPayload: ...
    def close(self) -> None: ...
```

- El grafo no conoce el proveedor; recibe el generador por inyección.
- `provider` y `model` son inmutables durante la ejecución.
- `last_usage` se llena después de cada llamada con `input_tokens`, `output_tokens`,
  `cached_tokens`, `source` y `cost` cuando corresponda.
- No hay fallback: un error se propaga clasificado y termina el turno.

## Esquemas

`AnswerPayload` y `ToolDecision` se conservan. `ToolDecision.arguments` se sustituye por un modelo
tipado compatible con `findings_query`:

```text
origin, snapshot_id, asset, severity, severity_level, status_group,
priority, exploitability, malware, qid, cve, group_by, detail, limit
```

- `extra="forbid"`; sin `case_id`.
- Los valores inválidos se rechazan antes de ejecutar la herramienta.
- Un proveedor que no pueda emitir el esquema debe fallar con `invalid_model_output`, no inventar
  argumentos.

## Traducción por proveedor

| Proveedor | Decisión y respuesta | Contexto |
|---|---|---|
| Ollama | `with_structured_output(..., method="json_schema")` | Tokenizador GGUF |
| Anthropic | `output_config.format` con `json_schema`; validación local | `POST /v1/messages/count_tokens` |
| DeepSeek | `response_format={"type":"json_object"}` + esquema en prompt; contenido vacío = inválido | Estimador conservador + uso observado |

## Errores normalizados

| Condición | Código | HTTP | Reintento |
|---|---|---|---|
| Proveedor no responde | `model_unavailable` | 503 | Sí, acotado |
| Timeout de llamada | `model_timeout` | 504 | Sí, acotado |
| Timeout de turno | `run_timeout` | 504 | No |
| Credencial inválida/revocada | `provider_auth_error` | 502 | No |
| Límite de tasa | `provider_rate_limited` | 503 | Sí, respetando `Retry-After` |
| Salida inválida o vacía | `invalid_model_output` | 500 | Una reparación |
| Contexto excedido | `context_budget_exceeded` | 500 | No |
| Presupuesto agotado | `budget_exceeded` | 402 | No |
| Sin autorización externa | `external_processing_blocked` | 403 | No |
| Herramienta importada/mixta con proveedor externo | `external_tool_blocked` | 403 | No |

Los mensajes al usuario no incluyen claves, cabeceras, cuerpos del proveedor ni rutas locales.

## Paridad funcional

- Misma recuperación, historial acotado, decisión, reparación y abstención.
- Mismos límites de operaciones, herramientas y tiempo.
- Mismas citas verificables y misma revisión humana.
- Solo cambia el transporte y la medición de contexto/uso/costo.
