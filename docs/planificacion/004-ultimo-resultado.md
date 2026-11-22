# 004 — Último resultado (Corte 6 parcial)

**Fecha**: 2026-11-22 12:35–13:05 (America/Bogota, `-05`)
**Rama**: `004-qdrant-vector-index`
**Alcance**: Corte 6, T070–T082. **Completadas: T070–T078 (9). Pendientes: T079–T082.**
**Acumulado: 78/82.** No se declara aceptación de 004.

## Dictamen

La sustitución de Chroma por Qdrant está **implementada y verificada en pruebas rápidas**, pero la
**evaluación funcional independiente no cumple**: 3 de 4 escenarios de recuperación superan el umbral
calibrado. No se ajustó el umbral ni los criterios con los resultados de evaluación. Por tanto
T079–T082 quedan abiertos y la constitución permanece en «backend sustituido; aceptación pendiente».

## Estado por tarea

| Tarea | Estado | Evidencia |
|---|---|---|
| T070 pruebas de ausencia de Chroma | Completada | RED observado; `tests/unit/test_qdrant_no_chroma.py` en verde. |
| T071 adaptación de fixtures/pruebas | Completada | `tests/fixtures/qdrant.py`; todas las pruebas usan Qdrant embebido o servidor. |
| T072 retiro de Chroma y constitución | Completada | `ChromaIndex`, `chroma_dir`, `chromadb` y `langchain-chroma` retirados; constitución actualizada a «backend sustituido; aceptación pendiente». |
| T073 verificación del retiro | Completada | `make check` 550 passed; sin imports ejecutables; `storage/chroma` intacto. |
| T074 guion de calibración | Completada | `src/retrieval/calibration.py` y `scripts/qdrant_threshold.py`; prueba unitaria del criterio. |
| T075 calibración | Completada | Servidor real + EmbeddingGemma; umbral 0.4956, cumplido (relevantes ≥ 0.4956; no pertinentes ≤ 0.0861). |
| T076 umbral aplicado | Completada | `config.py` con 0.4956 y procedencia documentada. |
| T077 conjunto de evaluación | Completada | `tests/fixtures/qdrant_eval.py`, separado de calibración. |
| T078 evaluación independiente | Completada (con fallo) | 3/4 escenarios; caso A 0.4359 < 0.4956. Fallo registrado; sin recalibrar. |
| T079 aceptación ASGI/Playwright | **Pendiente** | No ejecutada en esta pasada. |
| T080 documentación operativa | **Pendiente** | README/AGENTS actualizados; faltan quickstart/contratos y la verificación de T079. |
| T081 regresión completa | **Pendiente** | `make check` en verde; `make test-integration` no ejecutado. |
| T082 aceptación final y constitución | **Pendiente** | Bloqueada por T078/T079/T081. |

## Cambios y comandos

```text
make check → 550 passed, 35 deselected
calibración real: proposed=0.4956 observed=0.4956 satisfied=true
evaluación real: retrieval_ok=3/4; non_relevant_accepted=0;
  isolation.violations=0; versions.current_only=true;
  historical_citation=valid; qualys=0
```

Retiro: `langchain-chroma` y `chromadb` eliminados con `uv lock`; `storage/chroma` y sus archivos
permanecen. `CONSTITUTION.md` sigue siendo el enlace simbólico.

## Causa del fallo de evaluación

La consulta de caso A («¿Cómo se respaldan los datos del caso?») obtiene 0.4359, por debajo del
umbral congelado 0.4956. La calibración se hizo con un conjunto pequeño y separado; ajustar ahora el
umbral con este resultado invalidaría la evaluación. Acción necesaria: revisar el conjunto de
calibración (más consultas por escenario) y repetir calibración y evaluación con criterios fijados de
antemano, o aceptar el fallo y documentar la limitación. No se modificó el umbral.

## Limitaciones

- `make test-integration` no ejecutado (pendiente T081).
- Aceptación ASGI/Playwright de T079 no repetida en esta pasada.
- Sin aceptación integral; constitución en «aceptación pendiente».
- El volumen local de Qdrant conserva colecciones de smokes propios.

## Commits

`e7ecc79` retiro de Chroma · (pendiente) calibración/evaluación y documentación.

## Siguiente paso

Cerrar T079–T082: repetir calibración con un conjunto representativo (sin usar la evaluación),
reevaluar, ejecutar aceptación ASGI/Playwright y regresión completa. Solo entonces actualizar la
constitución a «implementado y aceptado localmente».

## Corrección de la validación del Corte 6 (2026-11-22 13:12)

**Causa de los hallazgos**: el script usaba `QdrantClient(path=...)` (embebido) aunque la documentación
lo presentaba como servidor; el aislamiento se calculaba sobre una lista vacía; Qualys se escribía como
constantes; y la prueba de evaluación no exigía todos los criterios.

**Correcciones**:

- `qdrant_threshold.py` acepta `--backend server|embedded` (servidor por defecto) y registra modalidad,
  versión, modelo, dimensión, métrica, `top_k`, umbral, fecha y hash del conjunto.
- Aislamiento calculado comparando documentos recuperados con los prohibidos de cada caso; el público
  no se cuenta como fuga. Con prueba unitaria que inyecta una fuga y la detecta.
- Qualys se mide con una importación ficticia y conteos antes/después de documentos, fragmentos, puntos
  y citas; no hay constantes.
- `retrieval/evaluation.py` define criterios y resultado global; el comando falla (exit 1) si no se
  cumplen y conserva el reporte.
- Pruebas unitarias del evaluador: recuperación incompleta, no pertinente aceptada, fuga, versión
  superada y cita inválida.

**Ejecución corregida (servidor real)**:

```text
Calibración iteración 2 (CAL2, server 1.20.0): umbral 0.5033, relevante mínimo 0.5033,
no pertinente máximo 0.2785, satisfecho=true.
Evaluación final (conjunto nuevo, hash da9b64ef…): 6/6 recuperadas, 0 no pertinentes aceptadas,
0 fugas, versión vigente y cita histórica válida, Qualys sin cambios → resultado passed.
```

Los reportes `calibration.json` y `evaluation.json` se conservan como iteración 1 y se anotan como
**embebidos**. Los nuevos son `calibration-iter2.json` y `evaluation-final.json`.

**Estado de tareas**: T074–T078 siguen completadas (procedimiento implementado y ejecutado; la
iteración 1 falló 3/4 y se conserva como historial; la evaluación final corregida pasa). **T079–T082
siguen pendientes**: aceptación ASGI/Playwright, documentación operativa completa, regresión
`make test-integration` y cierre de constitución. Avance: **78/82**. No se declara aceptación.
