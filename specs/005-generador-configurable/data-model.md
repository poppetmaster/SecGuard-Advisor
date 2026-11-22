# Data Model: Generador configurable (005)

**Fecha**: 2026-11-22
**Alcance**: diseño de datos. No se crean tablas ni migraciones en esta preparación.

## Configuración (runtime, no tabla)

`ProviderProfile` se resuelve desde `Settings` y no se persiste con secretos.

| Campo | Tipo | Regla |
|---|---|---|
| `generation_provider` | `Literal["ollama","deepseek","anthropic"]` | Predeterminado `ollama`; explícito; sin fallback |
| `generation_model` | `str` | Identificador de API o modelo local; validado |
| `generation_max_output_tokens` | `int` | > 0 y ≤ máximo documentado del proveedor |
| `generation_timeout_seconds` | `float` | > 0; no reemplaza el límite del turno |
| `generation_temperature` | `float \| None` | Solo Ollama/DeepSeek sin razonamiento; Anthropic lo omite |
| `generation_reasoning` | `Literal["off","low","high"]` | `off` por defecto en externos; se registra |
| `deepseek_api_key` | `SecretStr \| None` | Requerida si el proveedor es `deepseek` |
| `anthropic_api_key` | `SecretStr \| None` | Requerida si el proveedor es `anthropic` |
| `external_budget_usd` | `Decimal` | ≥ 0; 0 bloquea llamadas externas |
| `external_run_budget_usd` | `Decimal` | ≥ 0; límite por turno |
| `external_cost_tariff_version` | `str` | Fecha/versión de la tarifa aplicada |

Precedencia: variables de entorno > `.env` > predeterminados. Ningún secreto se escribe en SQLite,
logs, trazas ni plantillas.

## Tablas nuevas y columnas

### `runs` (columnas aditivas)

| Columna | Tipo | Nulo | Regla |
|---|---|---|---|
| `generator_provider` | `String(20)` | No | `ollama`, `deepseek`, `anthropic`; filas previas = `ollama` |
| `generator_identity` | `String(200)` | Sí | Digest local o identificador/versión externa observada |
| `usage_input_tokens` | `Integer` | Sí | Uso reportado o estimado admitido |
| `usage_output_tokens` | `Integer` | Sí | Uso reportado |
| `usage_cached_tokens` | `Integer` | Sí | Cache hit reportado |
| `usage_source` | `String(20)` | Sí | `observed`, `estimated`, `unknown` |
| `cost_usd` | `Numeric(12,6)` | Sí | `NULL` si es desconocido; nunca 0 inventado |
| `cost_status` | `String(20)` | No | `calculated`, `unknown`, `not_applicable` |
| `cost_tariff_version` | `String(40)` | Sí | Versión/fecha de tarifa usada |
| `external_authorization_id` | `String(32)` | Sí | Autorización vigente aplicada, si existe |

Invariantes:

- `generator_provider` no cambia después de crear la ejecución.
- `cost_status=calculated` exige `cost_usd` no nulo y `usage_source=observed`.
- `cost_status=unknown` exige `cost_usd` nulo.
- `cost_status=not_applicable` solo para Ollama local.

### `provider_usage`

Una fila por llamada facturable (decisión, generación, reparación) y por proveedor externo.

| Columna | Tipo | Regla |
|---|---|---|
| `id` | `String(32)` PK | Identificador opaco |
| `run_id` | `String(32)` FK `runs.id` | Ejecución |
| `attempt_no` | `Integer` | Intento de la ejecución |
| `operation` | `String(20)` | `decide`, `generate`, `repair` |
| `provider` | `String(20)` | Proveedor |
| `model` | `String(100)` | Identificador |
| `input_tokens` | `Integer` | Observado o estimado |
| `output_tokens` | `Integer` | Observado |
| `cached_tokens` | `Integer` | Observado |
| `usage_source` | `String(20)` | `observed`, `estimated`, `unknown` |
| `duration_ms` | `Integer` | Medido |
| `cost_usd` | `Numeric(12,6)` | Calculado o nulo |
| `cost_status` | `String(20)` | `calculated`, `unknown` |
| `tariff_version` | `String(40)` | Fecha/versión |
| `created_at` | `String(40)` | UTC ISO 8601 |

### `provider_budget_ledger`

Libro de reservas y liquidaciones. Una fila por intento de llamada externa.

| Columna | Tipo | Regla |
|---|---|---|
| `id` | `String(32)` PK | Identificador opaco |
| `run_id` | `String(32)` FK `runs.id` | Ejecución |
| `attempt_no` | `Integer` | Intento |
| `provider` | `String(20)` | Proveedor |
| `model` | `String(100)` | Modelo |
| `state` | `String(20)` | `reserved`, `settled`, `released`, `reconciled` |
| `reserved_usd` | `Numeric(12,6)` | Costo máximo reservado |
| `settled_usd` | `Numeric(12,6)` | Costo observado |
| `created_at` | `String(40)` | UTC |
| `updated_at` | `String(40)` | UTC |

Invariantes:

- Una reserva se crea antes del envío y se liquida o libera exactamente una vez.
- La suma de reservas abiertas + gasto liquidado no supera `external_budget_usd`.
- Al arrancar, una reserva abierta sin ejecución terminal se reconcilia: se libera si la llamada no
  se envió; se liquida con el uso persistido si se envió.

### `external_processing_authorizations`

| Columna | Tipo | Regla |
|---|---|---|
| `id` | `String(32)` PK | Identificador opaco |
| `case_id` | `String(32)` FK `cases.id` | Caso autorizado |
| `scope` | `String(40)` | `public_corpus`, `fictional_case`; no `private_case` en 005 |
| `policy_version` | `String(40)` | Política aplicada |
| `authorized_by` | `String(200)` | Identidad declarada; no autenticación |
| `authorized_at` | `String(40)` | UTC |
| `revoked_at` | `String(40)` | Nulo si vigente |
| `note` | `Text` | Motivo acotado, sin secretos |

Invariantes:

- Sin fila vigente (`revoked_at IS NULL`) no se permite ninguna llamada externa para el caso.
- `scope` no puede ser `private_case` en 005.
- La autorización no se infiere de una credencial ni de una configuración global.

### `provider_tariffs` (código, no tabla)

La tarifa se versiona en código con fecha, moneda, fuente y precio por MTok:

```text
provider, model, tariff_version, effective_from,
input_usd_per_mtok, output_usd_per_mtok,
cached_input_usd_per_mtok, peak_multiplier, peak_windows_utc
```

Anthropic: tramo ≤100k y >100k. DeepSeek: peak/off-peak y cache hit/miss. Si falta la tarifa, el
costo es `unknown`.

## Relaciones

```text
Case 1 ── N ExternalProcessingAuthorization
Case 1 ── N Run
Run 1 ── N ProviderUsage
Run 1 ── N ProviderBudgetLedger
ProviderProfile (runtime) ── selecciona ── ProviderAdapter
```

## Migración

- `alembic upgrade head` crea columnas y tablas de forma aditiva.
- Relleno de `generator_provider='ollama'` y `cost_status='not_applicable'` para filas previas.
- No se borran ni reescriben documentos, fragmentos, vectores, Qualys, mensajes ni citas.
- Reversión: las columnas nuevas se eliminan; las tablas nuevas se eliminan; ningún dato de negocio
  depende de ellas para reconstruirse.
