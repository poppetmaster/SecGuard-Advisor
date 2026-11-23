# Reevaluación externa 005 — perfiles con 4096 tokens

**Fecha**: 2026-11-23
**Alcance**: pasada focalizada autorizada, separada de las evaluaciones anteriores.
**Tope adicional**: 0,10 USD. **No se aumentaron presupuestos ni tiempos.**

## 1. Configuración aplicada

- Perfiles externos DeepSeek y Claude configurados con **4096 tokens de salida** mediante el perfil
  existente y el formulario `/settings/ai`.
- Ollama conserva su reserva automática de 1200 tokens.
- Migración aditiva `c1d2e3f4a5b6`: eleva perfiles externos guardados por debajo de 4096; no toca
  Ollama.
- La admisión de contexto usa el límite efectivo del perfil (4096); la reserva de presupuesto usa
  ese mismo límite. No se modificaron presupuestos ni timeouts.

## 2. Admisión de gasto

- Escenarios autorizados: DeepSeek S03/S04; Claude S02/S03/S04/S07/S10.
- Estimación con 4000 tokens de entrada, 4096 de salida y 4 llamadas posibles por escenario:
  **0,085656 USD**, por debajo del tope de 0,10 USD.
- Costo conocido autorizado: **0,013628 USD**; solicitudes autorizadas: 17.
- Llamada adicional no solicitada: DeepSeek S10 (2 solicitudes, **0,000532 USD**). Se conserva y se
  identifica aparte; no forma parte de la muestra autorizada.
- Ledger total de la pasada: **0,014512 USD**; todas las solicitudes con uso observado y costo
  conocido (**0 desconocidas**). No se agotó el tope.

## 3. Resultados autorizados

| Proveedor | Escenario | Resultado | Salida | Error/criterio | ms | Solicitudes | Tokens E/S/C | Costo | Citas |
|---|---|---|---|---|---|---|---|---|---|
| DeepSeek | S03 | fallido | answered | criterio de palabras clave no cumplido | 6 316 | 2 | 6 739 / 925 / 1 792 | 0,001303 USD | 8 |
| DeepSeek | S04 | aprobado | answered | — | 14 554 | 3 (incluye reparación) | 10 335 / 2 387 / 7 040 | 0,001948 USD | 6 |
| Claude | S02 | fallido | abstained_invalid_citations | citas rechazadas | 14 179 | 3 (incluye reparación) | 17 948 / 2 756 / 0 | 0,003173 USD | 2 rechazadas |
| Claude | S03 | fallido | answered | criterio de palabras clave no cumplido | 12 525 | 2 | 11 069 / 2 493 / 0 | 0,002354 USD | 5 |
| Claude | S04 | aprobado | answered | — | 7 901 | 2 | 10 077 / 1 636 / 0 | 0,001826 USD | 7 |
| Claude | S07 | fallido | insufficient_evidence | `findings_query` ok, respuesta no sostenida | 11 453 | 3 (incluye reparación) | 11 785 / 1 493 / 0 | 0,001573 USD | 0 |
| Claude | S10 | aprobado | answered | — | 8 165 | 2 | 5 904 / 1 721 / 0 | 0,001451 USD | 6 |

Fuera de la muestra autorizada: DeepSeek S10, aprobado, 4 858 ms, 3 520/728/2 944 tokens,
0,000532 USD, 7 citas. Se conserva en `resultados-extra-deepseek-s10.json`.

## 4. Diagnóstico

- **Límite 4096:** eliminó el truncamiento observado a 1200. DeepSeek S04 y Claude S02/S07 usaron
  reparación; DeepSeek S04 quedó aprobado. No se aprobó ningún escenario por aumentar la salida.
- **Claude S02:** la respuesta y reparación produjeron dos citas rechazadas; el resultado correcto
  es abstained_invalid_citations, no una aprobación.
- **Claude S03:** respondió con 5 citas válidas sobre riesgos OWASP, pero el criterio existente exige
  palabras clave en inglés; no se cambió el criterio. Es un fallo de criterio de evaluación, no una
  invención de citas.
- **Claude S07:** esta vez **sí seleccionó `findings_query`** (tool ok, total/grupos correctos) y
  hubo una generación y reparación. Aun así el modelo terminó en `insufficient_evidence`; falta
  preservar/responder con el resultado estructurado sin depender de un claim documental. Es un
  defecto pendiente, no una aprobación.
- **DeepSeek S03:** respuesta y citas válidas, pero no cumple las palabras clave existentes; fallo de
  criterio, no de transporte.
- No se repitieron escenarios fallidos ni se cambió el criterio para aprobar S03/S07.

## 5. Separación y panel

- Evaluación `005-reevaluation-4096-v1`, importable con:

```bash
uv run python scripts/import_evaluation_005.py \
  --evidence-dir docs/evidencia/005-estabilizacion/reevaluacion-externa-4096 \
  --storage-dir <almacenamiento>
```

- La muestra autorizada contiene 7 escenarios; DeepSeek S10 queda en el archivo extra y no se
  presenta como parte de la comparación solicitada.
- No se mezcla con `005-evaluation-v1` ni con la pasada `005-reevaluation-v1`.

## 6. Pruebas y estado

- Pruebas de configuración, migración, contexto y herramienta antes de las llamadas.
- `make check`: **738 passed**, 38 deselected.
- Integraciones afectadas: **8 passed**.
- Externas de pytest: **1 skipped**, 775 deselected.
- Sin Qualys privado, claves, prompts ni contenido privado en esta evidencia.

**Dictamen:** no se avanza a 006. T039 y la aceptación externa siguen pendientes; S03 conserva su
criterio fallido, S07 requiere una corrección de respuesta con herramienta y la muestra focalizada
no es una comparación completa.
