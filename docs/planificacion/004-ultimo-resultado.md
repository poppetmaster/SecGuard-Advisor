# 004 — Último resultado (Corte 6)

**Fecha**: 2026-11-22 (America/Bogota, `-05`)
**Rama**: `004-qdrant-vector-index`
**Alcance**: Corte 6, T070–T082.

## Estado actual

- **Implementación**: Qdrant es el único backend documental; Chroma fue retirado del código y sus
  archivos se conservan. Embeddings locales `embeddinggemma` (768) y métrica coseno.
- **Calibración**: umbral **0.5033**, fijado con servidor Qdrant 1.20.0 y EmbeddingGemma, antes de la
  evaluación final.
- **Evaluación final**: **6/6** recuperaciones, 0 no pertinentes aceptadas, 0 fugas entre casos,
  versión vigente sin fuga de la superada, cita histórica válida y Qualys sin cambios en documentos,
  fragmentos, puntos y citas.
- **Aceptación de interfaz**: ASGI (4 pruebas) y recorrido Playwright MCP con servidor real; cita
  válida, fragmento resaltado, evidencia de ejecución, Vulnerabilidades, móvil y consola limpia.
- **Regresión final**: `make check` → **562 passed**, 36 deselected; `make test-integration` →
  **36 passed, 0 failed, 0 skipped**; `pre-commit` verde.
- **Cierre**: 004 está **implementado y aceptado localmente** (Corte 6). `CONSTITUTION.md` sigue
  siendo el enlace simbólico.

No se inició 005 ni se retomó 003.

## Resultado por tarea

| Tarea | Estado | Evidencia |
|---|---|---|
| T070 pruebas de ausencia de Chroma | Completada | `tests/unit/test_qdrant_no_chroma.py`. |
| T071 adaptación de fixtures/pruebas | Completada | `tests/fixtures/qdrant.py`; Qdrant embebido o servidor. |
| T072 retiro de Chroma y constitución | Completada | Código y dependencias retirados; constitución actualizada. |
| T073 verificación del retiro | Completada | `make check`; sin imports ejecutables; `storage/chroma` intacto. |
| T074 guion de calibración | Completada | `retrieval/calibration.py` y `scripts/qdrant_threshold.py`. |
| T075 calibración | Completada | Iteración 2 con servidor: 0.5033, satisfecha. |
| T076 umbral aplicado | Completada | `config.py` con 0.5033 y procedencia. |
| T077 conjunto de evaluación | Completada | `tests/fixtures/qdrant_eval.py`, separado de calibración. |
| T078 evaluación independiente | Completada | `evaluation-final.json`: `outcome.passed=true`. |
| T079 aceptación ASGI/Playwright | Completada | `tests/acceptance/test_qdrant_ui.py` y capturas `ui-*.png`. |
| T080 documentación operativa | Completada | README, AGENTS, quickstart, contratos y documentos vigentes. |
| T081 regresión final | Completada | `make check` 562 passed; `make test-integration` 36 passed, 0 failed, 0 skipped. |
| T082 cierre de constitución | Completada | Constitución actualizada a «implementado y aceptado localmente»; Chroma y datos intactos. |

## Calibración y evaluación

### Antecedente histórico: iteración 1 (Qdrant embebido)

Los reportes `calibration.json` y `evaluation.json` se conservan. Se ejecutaron con
`QdrantClient(path=...)` (embebido) y EmbeddingGemma real; **no** son una ejecución contra servidor.
El umbral fue 0.4956 y la evaluación obtuvo **3/4**, con el caso A en 0.4359. No se ajustó el umbral
ni los criterios con ese resultado. Esta iteración queda como antecedente y regresión histórica.

### Corrección del evaluador

- `--backend server|embedded` (servidor por defecto) y metadatos completos: modalidad, versión de
  Qdrant, modelo, dimensión, métrica, `top_k`, umbral, fecha y SHA-256 del conjunto.
- Aislamiento real por caso; el público compartido no cuenta como fuga; prueba unitaria que inyecta
  una fuga y la detecta.
- Qualys medido con importación ficticia y conteos antes/después; sin constantes.
- `outcome.passed` y un criterio por requisito; el comando falla con código 1 y conserva el reporte.

### Iteración 2 (servidor real) y evaluación final

- Calibración `cal2`: umbral **0.5033**; relevantes ≥ 0.5033; no pertinentes ≤ 0.2785.
- Evaluación `final` (umbral congelado 0.5033, hash `da9b64efe877c63c…`): 6/6, 0 no pertinentes,
  0 fugas, versión vigente, cita histórica válida, Qualys sin cambios.
- Reportes: `calibration-iter2.json` y `evaluation-final.json`.
- Prueba: `tests/integration/test_qdrant_functional_eval.py` exige todos los criterios y usa una
  instancia única por ejecución.

## Aceptación de interfaz (T079)

- `tests/acceptance/test_qdrant_ui.py`: navegación y secciones; carga y consulta con cita; fragmento y
  evidencia; indicador de carga y doble envío; fallo de índice visible (503, sin abstención falsa).
- Playwright MCP contra servidor real: caso y documento ficticios, consulta con cita válida
  (`similarity 0.6493`), fragmento resaltado, ejecución de 17409 ms (recuperación 51 ms), sección
  Vulnerabilidades, menú móvil con foco y Escape, sin desbordamiento ni errores de consola.
- Capturas: `docs/evidencia/004-corte-6/ui-*.png`, solo con datos ficticios.

## Documentación (T080)

`README.md`, `AGENTS.md`, `specs/004-qdrant-vector-index/quickstart.md` y `contracts/retrieval.md`
describen Qdrant como backend documental, SQLite como fuente de verdad, embeddings locales, los
comandos `make qdrant-up|qdrant-health|qdrant-rebuild`, la consulta `--status` y el alcance limitado
del modo embebido. Las evidencias de los cortes 1–5 quedaron marcadas como históricas.

## Regresión final (T081)

### Resultado definitivo

```text
make check
  → 562 passed, 36 deselected, 17 warnings (13.16 s)
make test-integration
  → 36 passed, 0 failed, 0 skipped, 562 deselected, 14 warnings
    (1225.16 s = 20 min 25 s, Qdrant 1.20.0 + Ollama locales)
pre-commit run --all-files
  → Passed
```

- Las 36 pruebas de integración incluyen la regresión de 001 y 002, recuperación, citas, memoria,
  aislamiento entre casos e instancias, reconstrucción, errores explícitos, Límites y separación de
  Qualys del índice documental.
- **Omitidas**: 0 en integración. `make check` deselecciona las 36 de integración por marcador; no son
  omisiones de criterio.
- Las validaciones humanas recomendadas de 001 (SC-001 y SC-003) siguen sin ejecutarse y no son
  bloqueantes; no se presentan como aprobadas.
- La CI remota no se ejecutó.

### Defectos corregidos durante T081

1. **Namespace compartido en pruebas de integración**: `tests/fixtures/qdrant.py` usaba el ID fijo
   `test-integration`. Con un volumen Qdrant persistente y un `tmp_path` nuevo por ejecución, el
   índice fallaba cerrado (`InstanceNamespaceMismatch`) o reutilizaba datos de otra prueba. Se derivó
   un ID estable por ruta de almacenamiento (`test-<sha256[0:10]>`), conservando el aislamiento.
2. **Prueba de memoria con backend incoherente**: `test_memory_restart_isolation` sembraba el índice
   embebido y consultaba un namespace de servidor distinto. Pasaba por filtración entre pruebas. Ahora
   reabre el mismo índice embebido tras el reinicio simulado.
3. **Prueba del evaluador con instancia fija**: `test_qdrant_functional_eval` reutilizaba
   `cut6-test-final`; ahora genera una instancia única por ejecución.

Ninguno de estos cambios alteró el umbral 0.5033, el conjunto final ni los criterios de evaluación.

### Tiempos de espera ampliados en las pruebas

`tests/integration/test_answer_real.py` y `tests/acceptance/test_journey_real.py` configuran
`run_timeout_seconds=600` y `llm_timeout_seconds=300` **solo en el arnés de prueba**. Estos recorridos
verifican funcionalidad (citas, memoria, herramientas) bajo carga real y no el cumplimiento del tiempo
de respuesta de producción.

- Los límites normales siguen siendo **120 s de turno y 90 s por llamada** y conservan sus pruebas:
  `tests/unit/test_limits.py` (timeout por llamada y por turno), `tests/unit/test_llm_client.py`
  (`model_timeout`) y `tests/contract/test_chat_routes.py` (504 visible).
- Demora real observada: una ejecución completa del turno real superó los 120 s y el producto la
  clasificó correctamente como `timeout`; la prueba de integración completa tardó **1225 s**. Se
  registra como limitación de latencia del modelo local, no como fallo de recuperación.

## Cierre (T082)

- 82/82 tareas marcadas.
- `.specify/memory/constitution.md` actualizada a «implementado y aceptado localmente» en las
  secciones de arquitectura y en la tabla de parámetros, con una fila de estado fechada 2026-11-22.
- `CONSTITUTION.md` sigue siendo el enlace simbólico a `.specify/memory/constitution.md`; no hay copia.
- Verificación de datos: `storage/chroma/chroma.sqlite3` y su directorio de colección siguen
  presentes; `git status` no reporta cambios en `storage/` ni `storage/demo`; no se borraron volúmenes.
- No se inició 005 ni se retomó 003. Sin push ni publicación.

## Reproducción

```bash
make qdrant-up
uv run python scripts/qdrant_threshold.py --mode calibrate --dataset cal2 --backend server \
  --output docs/evidencia/004-corte-6/calibration-iter2.json
uv run python scripts/qdrant_threshold.py --mode evaluate --dataset final --backend server \
  --threshold 0.5033 --output docs/evidencia/004-corte-6/evaluation-final.json
uv run pytest tests/acceptance/test_qdrant_ui.py -q
uv run pytest tests/integration/test_qdrant_functional_eval.py -q
make check
make test-integration
make qdrant-down
```

## Limitaciones

- El modelo local `qwen3.5:9b` puede superar el presupuesto de producción de 120 s bajo carga. La
  respuesta correcta es `timeout` explícito; las pruebas reales que miden citas y memoria amplían su
  propio presupuesto para no confundir latencia con un defecto funcional. El límite de producción
  conserva su prueba.
- Navegador verificado: Chromium. Otros navegadores siguen pendientes.
- SC-001 y SC-003 de 001 siguen siendo validaciones humanas recomendadas y no bloqueantes; no se
  ejecutaron.
- La CI remota no se ejecutó.
