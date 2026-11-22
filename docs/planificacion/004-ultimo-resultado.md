# 004 — Último resultado (Corte 3 completado)

**Fecha**: 2026-11-22 11:36–11:52 (America/Bogota, `-05`)
**Rama**: `004-qdrant-vector-index`
**Alcance**: Corte 3, T043–T053 (11 tareas). **Acumulado: T001–T053 = 53 de 82 tareas.**
**Backend**: Qdrant es el índice de la aplicación; Chroma se conserva hasta el Corte 6. SQLite sigue
siendo la fuente de verdad. No se declara aceptación de 004.

## Estado por tarea

| Tarea | Estado | Evidencia |
|---|---|---|
| T043 versiones/citas/aislamiento | Completada | `test_qdrant_citations.py` (2 pruebas): versión superada excluida, cita histórica válida, casos aislados. |
| T044 adaptación de selección vigente | Completada | El filtro existente de `search.py` se conserva; no se tocó `citations.py`. |
| T045 contrato de evidencia | Completada | RED observado (test falla sin los campos); GREEN con 1 prueba. |
| T046 evidencia del paso retrieve | Completada | `nodes.py` registra instancia, backend, versión, modelo, dimensión, alias, generación, `score_metric` y `error_code`. |
| T047 verificación citas/evidencia | Completada | 3 pruebas en verde. |
| T048 Qualys fuera del RAG | Completada | 2 pruebas: la importación no crea documentos, fragmentos ni puntos Qdrant. |
| T049 reinicio persistente | Completada | `test_qdrant_restart.py`: cliente cerrado y reabierto conserva alias, conteo y resultados. |
| T050 readiness y validación | Completada | `/healthz` informa `qdrant`; validación de instancia y errores claros. |
| T051 caída/config incompatible | Completada | `test_qdrant_availability.py` (4 pruebas). |
| T052 errores explícitos | Completada | `qdrant_unavailable` e `instance_namespace_mismatch` sin fallback a Chroma. |
| T053 verificación US4 | Completada | 4 pruebas; smoke real con reinicio y caída. |

## Cambios realizados

- `retrieval/index.py`: `describe()` para evidencia (sin escrituras), validación del marcador de
  instancia por almacenamiento y `ping()` para readiness.
- `web/app.py`: sonda de Qdrant y campo `qdrant` en `/healthz` (`ok`, `unavailable`,
  `not_configured`); la fábrica pasa `storage_dir` al índice.
- `conversation/nodes.py`: evidencia del paso `retrieve` con identidad del índice, sin rutas ni texto.
- `conversation/turn.py`: el detalle del paso de fallo incluye `error_code`.
- Pruebas nuevas: citas/versiones, evidencia, reinicio, disponibilidad y Qualys con Qdrant.
- `test_app_shell.py`: el contrato de `/healthz` incluye `qdrant` (adaptación mínima documentada).

## Comandos y resultados

```text
T047: uv run pytest test_qdrant_citations.py test_qdrant_evidence.py → 3 passed
T048: uv run pytest test_qualys_not_rag.py → 2 passed
T053: uv run pytest test_qdrant_restart.py test_qdrant_availability.py → 4 passed
make check → 514 passed, 35 deselected
pre-commit → todas las comprobaciones Passed
```

RED capturado en T045 al restaurar temporalmente el `nodes.py` previo (test falla; luego GREEN). Las
capacidades de T043/T049/T051 ya existían en parte; se verificaron sin introducir fallos artificiales.

## Pruebas embebidas frente a servidor real

- **Embebidas (automatizadas)**: citas/versiones, evidencia, reinicio por reapertura del cliente,
  caída por puerto cerrado y configuración incompatible con marcador copiado.
- **Servidor real** (instancia `cut3-smoke`, storage temporal, Qdrant 1.20.0 + EmbeddingGemma):
  - Dos reconstrucciones `completed` (público 2 fragmentos, dos casos con 1 cada uno).
  - Recuperación con orígenes público y de caso, sin cruces entre casos.
  - Versión superada excluida; cita histórica `valid` desde SQLite.
  - Reinicio con `make qdrant-down/up`: conteo y búsqueda conservados.
  - Caída: `qdrant_unavailable`; marcador copiado: `instance_namespace_mismatch`.
  - Sin generación ni “información insuficiente”: el fallo se propaga como error (pruebas de rutas).

## Revisión visual

La página de ejecución muestra `step.detail` como JSON y ahora incluye los campos nuevos. Se validó con
Playwright MCP sobre una ejecución sembrada: el detalle expandido muestra `vector_backend`,
`qdrant_version`, alias, generación y `score_metric`. Captura:
`docs/evidencia/004-corte-3/run-detail.png`. Los mensajes de error no cambiaron de plantilla; su texto
se verifica en las pruebas de contrato.

## Limitaciones

- Un caso sin documentos privados sigue devolviendo `case_index_unavailable` (T054–T059, Corte 4).
- Sin calibración de umbral.
- Chroma y sus datos permanecen.
- El volumen local de Qdrant conserva colecciones de smokes propios (`cut2-*`, `cut3-smoke`).
- No se declara aceptación de 004.

## Commits

`149e499` evidencia y readiness · `1ab8a07` identidad en retrieve · `9c18966` pruebas de versiones,
reinicio y disponibilidad · `0b864ab` correcciones del Corte 2 (previo).

## Siguiente paso

Corte 4 (T054–T064): primer documento, alcance vacío, recuperación y parciales. No se inició T054.

## Corrección de trazabilidad de generación (2026-11-22 11:51)

**Causa**: `nodes.retrieve` llamaba a `index.describe()` después de `search_documents`. Si una
reconstrucción publicaba una generación nueva entre la consulta y `describe()`, la evidencia registraba
la generación nueva aunque la búsqueda hubiera usado la anterior (`mismatch=True` reproducido).

**Solución**:

- `QdrantIndex.query_with_identity()` resuelve el alias una sola vez, consulta la colección concreta y
  devuelve los hits junto con la identidad de esa colección, incluso con cero coincidencias.
- `search_documents` conserva `public_evidence` y `case_evidence` en `RetrievalResult`, por alcance.
- `nodes._index_evidence(result)` usa esa identidad capturada; no vuelve a resolver aliases.
- Si la identidad no está disponible, el campo queda ausente o nulo; no se inventan valores.

**Regresión añadida** (`tests/contract/test_qdrant_evidence.py`):

- Consulta generación A, cambia el alias a B antes de construir la evidencia y comprueba que sigue
  identificando A, para público y caso.
- Alcance público con cero coincidencias: conserva la generación consultada tras cambiar el alias.
- `nodes.retrieve` con un índice cuyos `describe` devuelve B y cuya consulta devolvió A: la evidencia
  registra A.

**Comandos**: recuperación, evidencia, citas y disponibilidad → 11 passed; `make check` y
`pre-commit` se ejecutan al cierre. Avance: **53/82**, sin marcar tareas posteriores.

Contratos sincronizados: `contracts/evidence.md` y `data-model.md` indican que la identidad se captura
en la consulta y no se re-resuelve; `public_alias` y `public_generation` quedan documentados.
