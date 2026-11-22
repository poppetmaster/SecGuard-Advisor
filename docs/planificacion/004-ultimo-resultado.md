# 004 — Último resultado (Corte 2 completado)

**Fecha**: 2026-11-22 10:10–11:35 (America/Bogota, `-05`)
**Rama**: `004-qdrant-vector-index`
**Alcance**: Corte 2, T010–T042. **42 de 42 tareas completadas.**
**Backend**: Qdrant es el índice documental de la aplicación; Chroma se conserva (código, datos y
dependencias) hasta el Corte 6. SQLite sigue siendo la fuente de verdad.

## Tareas y evidencia

- **T010–T017**: adaptador Qdrant, colecciones/alias con namespace, UUIDv5, payload sin texto, seis
  códigos 503/409 y fábrica de aplicación.
- **T018–T020**: ingesta del corpus público y demo con Qdrant y lock por documento; targets sin rutas
  de Chroma.
- **T021–T025**: reconstrucción desde SQLite con generación nueva, validación, cambio de alias,
  retención de la anterior, reporte JSON y estados terminales.
- **T023/T024/T026/T027**: resolvedor único y `--status` de solo lectura con los tres errores.
- **T028–T033**: fallos, parciales, metadatos obsoletos, fragmentos incompatibles, puntos huérfanos,
  target `qdrant-rebuild` y verificación conjunta.
- **T034–T039**: recuperación público/caso con score coseno, aislamiento entre casos, lock de
  escritura en el servicio y errores clasificados en rutas.
- **T040–T042**: el turno se detiene con el código clasificado; sin generación, sin abstención y con
  la ejecución registrada.

RED observados directamente en T010/T011/T016/T023/T026 (imports/códigos/script ausentes). El resto
se validó con GREEN y pruebas de integración; no se fabricaron fallos.

## Comandos y resultados observados

```text
uv run pytest (13 archivos del corte) → 53 passed
uv run pytest test_qdrant_rebuild.py test_qdrant_rebuild_failures.py test_qdrant_status.py → 12 passed
uv run pytest test_qdrant_retrieval.py test_qdrant_routes.py → 5 passed
uv run pytest test_qdrant_corpus_targets.py → 2 passed
make check → 502 passed, 35 deselected
uv run pre-commit run --all-files → Passed
make -n qdrant-rebuild → uv run python scripts/rebuild_qdrant.py
make help → qdrant-rebuild listado
```

### Integración real (servidor Qdrant + EmbeddingGemma)

Con `SECGUARD_INSTANCE_ID=cut2-smoke`, storage y corpus temporales, `sample.pdf` ficticio y
`embeddinggemma` (768):

```text
ingest público: created, 1 chunk; count = 1
ingest de caso: created, 1 chunk
rebuild: partial — public 1/1/0/1/0; case 1/1/0/0/0
search: ok, 2 hits, orígenes case_evidence + public_corpus, top score 0.1389
```

El alcance público quedó `partial` porque el volumen del servidor conservaba una generación de un
smoke anterior con otros `chunk_id`: el punto sobrante se reportó como huérfano y el alias anterior se
conservó, justo el comportamiento exigido. El caso se validó y publicó su alias. El servicio se
detuvo con `make qdrant-down` (sin `-v`); el volumen se conservó.

## Archivos principales

- `retrieval/index.py` (QdrantIndex), `collections.py`, `errors.py`, `status.py`, `rebuild.py`.
- `corpus/ingest.py`, `documents/service.py`, `web/app.py`, `web/errors.py`, `search.py`, `turn.py`.
- `scripts/ingest_corpus.py`, `scripts/prepare_demo.py`, `scripts/rebuild_qdrant.py`, `Makefile`.
- Pruebas: 13 archivos nuevos entre unit, contract e integration.
- `specs/004-qdrant-vector-index/tasks.md`: T001–T042 marcadas.

## Limitaciones vigentes

- Un caso sin documentos privados todavía produce `case_index_unavailable` al consultar; la
  distinción de alcance esperado pertenece a T053 (Corte 4).
- No hay calibración del umbral: se usa el valor por defecto existente y no se declara calibrado.
- No se retiraron dependencias ni datos de Chroma.
- En el volumen local de Qdrant quedan colecciones del smoke con instancia `cut2-smoke`; no afectan a
  las pruebas, que usan almacenamiento temporal o modo embebido.
- No se declara aceptación de 004.

## Commits de esta pasada

`12d6e51` corpus con lock · `5be439b` reconstrucción · `83f2fc4` lock y mapeo de conflictos ·
`373b136` pruebas de recuperación y fallo de turno · `270bf26` avance parcial previo.

## Siguiente paso

Corte 3 (T043–T053): citas/evidencia y reinicio/disponibilidad. No se inició T043.
