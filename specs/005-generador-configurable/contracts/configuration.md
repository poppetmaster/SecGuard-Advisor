# Contract: Configuration (005)

**Fecha**: 2026-11-22

## Precedencia

1. Variables de entorno.
2. Archivo local `.env` (ignorado por Git).
3. Valores predeterminados del código.

No se aceptan credenciales por argumentos de línea de comandos, URL, SQLite ni formulario web.

## Variables

| Variable | Requerida | Predeterminado | Regla |
|---|---|---|---|
| `SECGUARD_GENERATION_PROVIDER` | No | `ollama` | `ollama`, `deepseek` o `anthropic` |
| `SECGUARD_GENERATION_MODEL` | No | según proveedor | Identificador validado contra la tabla de modelos |
| `SECGUARD_GENERATION_MAX_OUTPUT_TOKENS` | No | `1200` | > 0 y ≤ máximo del modelo |
| `SECGUARD_GENERATION_TIMEOUT_SECONDS` | No | `90` | > 0; no reemplaza el límite del turno |
| `SECGUARD_GENERATION_TEMPERATURE` | No | `0.1` | Solo Ollama/DeepSeek sin razonamiento; Anthropic lo omite |
| `SECGUARD_GENERATION_REASONING` | No | `off` | `off`, `low`, `high`; se registra |
| `DEEPSEEK_API_KEY` | Sí si `deepseek` | vacío | `SecretStr`; nunca se imprime |
| `ANTHROPIC_API_KEY` | Sí si `anthropic` | vacío | `SecretStr`; nunca se imprime |
| `SECGUARD_EXTERNAL_BUDGET_USD` | No | `0` | ≥ 0; 0 bloquea llamadas externas |
| `SECGUARD_EXTERNAL_RUN_BUDGET_USD` | No | `0` | ≥ 0; límite por turno |
| `SECGUARD_EXTERNAL_TARIFF_VERSION` | No | fecha de la tabla | Debe existir en la tabla de tarifas |
| `SECGUARD_QDRANT_URL` | No | `http://127.0.0.1:6333` | Sin cambio |
| `SECGUARD_INSTANCE_ID` | Sí para Qdrant | — | Sin cambio |

## Validación al arrancar

- Proveedor desconocido → `invalid_provider_configuration`.
- Credencial requerida ausente o vacía → `missing_provider_credential`, indicando el nombre de la
  variable, nunca el valor.
- Modelo desconocido o límite inválido → `invalid_provider_configuration`.
- Presupuesto negativo → `invalid_provider_configuration`.
- `ollama` no requiere credencial externa y conserva su validación actual.
- La validación no realiza llamadas de red ni pagadas. Una comprobación opcional de modelos queda
  deshabilitada por defecto.

## Plantilla

`.env.example` incluye:

```text
SECGUARD_GENERATION_PROVIDER=ollama
SECGUARD_GENERATION_MODEL=
SECGUARD_GENERATION_MAX_OUTPUT_TOKENS=1200
SECGUARD_GENERATION_TIMEOUT_SECONDS=90
SECGUARD_GENERATION_REASONING=off
DEEPSEEK_API_KEY=
ANTHROPIC_API_KEY=
SECGUARD_EXTERNAL_BUDGET_USD=0
SECGUARD_EXTERNAL_RUN_BUDGET_USD=0
```

Sin claves reales. `.env` no se versiona.

## Registro

Cada ejecución registra proveedor, modelo, identidad/digest, límites, modo de razonamiento, versión
de tarifa y si la credencial estuvo presente, sin registrar su valor.
