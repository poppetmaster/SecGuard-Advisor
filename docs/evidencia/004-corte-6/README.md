# Corte 6 — Retiro de Chroma, calibración y evaluación (parcial)

**Fecha**: 2026-11-22 12:35–13:05 (America/Bogota, `-05`)
**Rama**: `004-qdrant-vector-index`
**Estado**: T070–T078 completadas; T079–T082 pendientes. Acumulado 78/82. **No se declara
aceptación de 004.**

## Retiro de Chroma (T070–T073)

- `ChromaIndex`, `chroma_dir`, el import de `chromadb` y las dependencias `langchain-chroma`/`chromadb`
  fueron retirados con `uv lock`/`uv sync --locked`.
- Fixtures y pruebas usan `tests/fixtures/qdrant.py` (Qdrant embebido o servidor).
- `make check`: **550 passed, 35 deselected**.
- `grep` no encuentra referencias ejecutables a Chroma en `src/`, `scripts/` ni `pyproject.toml`.
- `storage/chroma` y sus archivos permanecen; no se borró ningún dato.
- Constitución actualizada a «backend sustituido; aceptación pendiente»; `CONSTITUTION.md` sigue siendo
  el enlace simbólico.

## Calibración (T074–T076)

Procedimiento: `scripts/qdrant_threshold.py --mode calibrate` contra servidor Qdrant real y
`embeddinggemma` (768), con documentos ficticios y criterios fijados antes de medir.

```json
{
  "relevant": [0.4956, 0.4988, 0.6408],
  "non_relevant": [0.0204, 0.0861, 0.0372],
  "proposed_threshold": 0.4956,
  "observed": {"threshold": 0.4956, "satisfied": true}
}
```

Umbral aplicado en `config.py`: **0.4956**, documentado como filtro de candidatos débiles.

## Evaluación independiente (T077–T078)

Conjunto distinto (`tests/fixtures/qdrant_eval.py`), umbral congelado 0.4956:

```json
{
  "retrieval_ok": 3,
  "retrieval_total": 4,
  "non_relevant_accepted": 0,
  "isolation": {"violations": 0, "crossed": false},
  "versions": {"current_only": true, "superseded_leaked": false,
               "historical_citation": "valid"},
  "qualys": {"documents": 0, "points": 0, "citations": 0}
}
```

**Fallo**: la consulta de caso A («¿Cómo se respaldan los datos del caso?») obtuvo 0.4359, por debajo
del umbral. No se ajustó el umbral ni los criterios. Informes completos:
`calibration.json` y `evaluation.json`.

## Conservación de datos

Antes y después del retiro se comprobó que `storage/chroma` existe y conserva sus archivos
(`chroma.sqlite3` y colecciones). No se modificó `storage/` ni `storage/demo`, no se borraron volúmenes
y no se usó el CSV privado de Qualys.

## Pendiente

- T079: aceptación ASGI y Playwright (crear caso, documento, consulta, cita, ejecución,
  vulnerabilidades, memoria, móvil, consola).
- T080: completar quickstart/contratos y documentación operativa.
- T081: `make test-integration` y regresión completa.
- T082: aceptación final y constitución «implementado y aceptado localmente» solo si T081 demuestra
  los criterios; hoy no se cumple.

## Reproducción

```bash
make qdrant-up
uv run python scripts/qdrant_threshold.py --mode calibrate --output docs/evidencia/004-corte-6/calibration.json
uv run python scripts/qdrant_threshold.py --mode evaluate --threshold 0.4956 \
  --output docs/evidencia/004-corte-6/evaluation.json
make qdrant-down
make check
```

`LANGSMITH_TRACING=false`; servidor y storage temporales.
