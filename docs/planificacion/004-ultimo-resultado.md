# 004 — Último resultado (Corte 2, avance parcial)

**Fecha**: 2026-11-22 10:10–10:55 (America/Bogota, `-05`)
**Rama**: `004-qdrant-vector-index`
**Alcance intentado**: Corte 2, T010–T042. **No se completó**: 12 tareas cerradas, 21 pendientes.
**Backend**: la fábrica de aplicación ya construye Qdrant por defecto, pero la ingesta del corpus y la
reconstrucción todavía no están migradas. Es un estado intermedio de rama de funcionalidad, no una
aceptación.

## Tareas completadas (12)

| Tarea | Evidencia |
|---|---|
| T010 pruebas del adaptador | RED capturado (`ImportError` al restaurar el código previo); 12 pruebas unitarias en verde. |
| T011 contrato de colecciones/alias | RED capturado; 5 pruebas de contrato en verde. |
| T012 colecciones con namespace | `instance_collection_name`, `instance_alias_name`, `new_generation_id`, validación. |
| T013 `QdrantIndex` | UUIDv5, payload sin texto, upsert/count/query/delete, alias y errores clasificados. |
| T014 fábrica Qdrant | `app.py` construye `QdrantIndex` desde settings; sin conexión al construir. |
| T015 contrato de fábrica | 3 pruebas: construcción, ID ausente, ID inválido en configuración. |
| T016 pruebas de códigos | RED observado (2 fallos) antes de registrar. |
| T017 códigos de error | Seis códigos con 503/409 y mensajes en español; no se degradan a `internal_error`. |
| T023 pruebas del resolvedor | RED observado (`ModuleNotFoundError`); 10 pruebas en verde. |
| T024 resolvedor único | `retrieval/status.py`: lock, propietario, reporte terminal, errores tipados. |
| T026 pruebas de `--status` | RED observado (5 fallos sin el script); 5 pruebas de integración en verde, sin escrituras. |
| T027 `--status` | Salida JSON, salida 0/2, errores `instance_configuration_invalid`, `lock_unreadable`, `status_report_unreadable`. |

## Tareas pendientes (21)

T018–T022, T025, T028–T042. No hay bloqueo técnico registrado: es trabajo no ejecutado en esta
sesión. Consecuencias concretas del estado intermedio:

- **T018–T020**: `scripts/ingest_corpus.py` y `prepare_demo.py` siguen usando Chroma. Con la fábrica
  ya en Qdrant, `make corpus-ingest` no alimenta el índice que consulta la aplicación.
- **T021/T022/T025/T028–T033**: no existe reconstrucción desde SQLite, ni validación de generación,
  ni reporte de reconstrucción, ni manejo de parciales, ni `qdrant-rebuild`.
- **T034–T039**: la recuperación usa `score` de Qdrant y los errores clasificados ya llegan a las
  rutas, pero faltan las pruebas de recuperación, aislamiento y mapeo de rutas.
- **T040–T042**: el turno detiene la respuesta con el código clasificado (cambio aplicado), pero
  faltan las pruebas de los tres escenarios de fallo.

## Cambios de coherencia sin tarea cerrada

Se adaptaron para que el backend por defecto no quede inoperante:

- `retrieval/search.py` usa `score` cuando existe y conserva `1 - distance` para Chroma.
- `web/app.py` mapea `retrieval.errors.IndexError` a la taxonomía HTTP.
- `conversation/turn.py` detiene el turno con el código del fallo de índice.

Estos cambios pertenecen a T035/T038/T041 y **no** se marcan como completados sin sus pruebas.

## Archivos modificados o creados

- `src/secguard_advisor/retrieval/collections.py` (nombres/alias de Qdrant; Chroma intacto).
- `src/secguard_advisor/retrieval/index.py` (`QdrantIndex`, `QueryHit.score`, payload sin texto).
- `src/secguard_advisor/retrieval/errors.py`, `src/secguard_advisor/retrieval/status.py`.
- `src/secguard_advisor/web/errors.py`, `web/app.py`, `retrieval/search.py`,
  `conversation/turn.py`.
- `scripts/rebuild_qdrant.py` (solo `--status`).
- `tests/unit/test_qdrant_index.py`, `test_qdrant_state.py`, `test_error_messages.py`;
  `tests/contract/test_qdrant_index_contract.py`, `test_qdrant_app.py`;
  `tests/integration/test_qdrant_status.py`.
- `specs/004-qdrant-vector-index/tasks.md` (12 marcas).

## Comandos y resultados observados

```text
uv run pytest tests/unit/test_qdrant_index.py tests/contract/test_qdrant_index_contract.py → 13 passed
uv run pytest tests/unit/test_error_messages.py → 5 passed
uv run pytest tests/contract/test_qdrant_app.py → 3 passed
uv run pytest tests/unit/test_qdrant_state.py → 10 passed
uv run pytest tests/integration/test_qdrant_status.py → 5 passed
make check → 485 passed, 35 deselected
uv run pre-commit run --all-files → todas las comprobaciones Passed
```

RED capturados: imports ausentes del adaptador, códigos sin registrar y script `--status` ausente.
Las pruebas del adaptador y del resolvedor usan Qdrant en modo embebido; el servidor Qdrant estaba
disponible pero no se usó para ingesta real en este avance.

## Limitaciones vigentes

- La aplicación usa Qdrant por defecto mientras la ingesta del corpus sigue en Chroma.
- No hay reconstrucción del índice ni generación/alias validada desde SQLite.
- La ausencia de alias produce `public_index_unavailable`/`case_index_unavailable` sin la lógica de
  alcance esperado (pertenece al Corte 4).
- No se ejecutaron pruebas contra el servidor Qdrant para ingesta/recuperación, ni calibración.
- No se retiraron dependencias ni archivos de Chroma.

## Commits de esta pasada

`a532a91 feat(web): register qdrant index error codes` ·
`cc92007 feat(retrieval): add qdrant collections and index adapter` ·
`86de5c8 feat(app): build qdrant index and classify index failures` ·
`a41f4fe feat(conversation): stop turns on classified index failures` ·
`7f2dec7 feat(retrieval): add rebuild status resolver and status command`

## Siguiente paso

Continuar el Corte 2 en este orden: T018–T020 (corpus y demo con lock), T021/T022/T025 (reconstrucción
y reporte), T028–T033 (fallos, parciales, huérfanos, target y verificación), T034–T039 (recuperación,
servicio, rutas) y T040–T042 (fallo de índice en el turno). No se inició T043.
