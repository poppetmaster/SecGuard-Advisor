# Contract: Budget and usage (005)

**Fecha**: 2026-11-22

## Unidades

- Tokens: enteros reportados por el proveedor.
- Dinero: USD con 6 decimales; se persiste `Numeric(12,6)`.
- Tarifa: USD por millón de tokens (MTok), versionada y fechada.

## Reserva antes de la llamada

Para cada llamada externa:

1. Calcular el costo máximo:

   ```text
   max_input  = prompt_admitido (medido o estimado con margen)
   max_output = generation_max_output_tokens
   reserva    = max_input  * tarifa_entrada
              + max_output * tarifa_salida
   ```

2. Comprobar `gasto_liquidado + reservas_abiertas + reserva ≤ external_budget_usd` y, si aplica,
   `≤ external_run_budget_usd`.
3. Si no cabe, no se envía la llamada y el turno falla con `budget_exceeded` (HTTP 402).
4. Crear una fila `reserved` en `provider_budget_ledger` antes de enviar.
5. Tras la respuesta, liquidar con el uso observado (`settled`) o liberar si no se envió.

La reserva incluye reintentos: cada intento tiene su propia reserva. Un reintento no recibe saldo
nuevo si el turno ya lo agotó.

## Costo observado

```text
costo_entrada = input_miss * tarifa_entrada_miss
              + input_hit  * tarifa_entrada_hit
costo_salida  = output     * tarifa_salida
costo         = costo_entrada + costo_salida
```

- Anthropic: tramo ≤100k o >100k tokens de prompt.
- DeepSeek: peak u off-peak según la hora UTC de la llamada; cache hit/miss.
- Ollama: `cost_status=not_applicable`.

Si falta el uso o la tarifa, `cost_status=unknown` y `cost_usd=NULL`. No se escribe cero.

## Reconciliación

Al arrancar:

- Reserva `reserved` sin ejecución terminal y sin evidencia de envío → `released`.
- Reserva `reserved` con ejecución terminal y uso persistido → `settled` con el uso observado.
- Reserva `reserved` con ejecución terminal sin uso → `reconciled` y costo `unknown`.
- Nunca se cuenta dos veces el mismo intento.

## Límites y comportamiento

- `external_budget_usd=0` bloquea toda llamada externa.
- El presupuesto es un límite local; no se presenta como garantía del proveedor.
- Un 429 respeta `Retry-After` si existe y no excede el saldo.
- Una diferencia entre reserva y liquidación se registra; no se oculta.
- El libro de presupuesto no contiene secretos ni contenido del caso.

## Evidencia

La página de ejecución muestra proveedor, modelo, operación, tokens de entrada/salida/caché,
duración, tarifa, costo y estado (`calculated`, `unknown`, `not_applicable`). No muestra claves.
