# 004 — Último resultado (Corte 2 corregido)

**Fecha**: 2026-11-22 10:10–11:40 (America/Bogota, `-05`)
**Rama**: `004-qdrant-vector-index`
**Alcance**: Corte 2, **T010–T042 = 33 tareas**. Acumulado del proyecto: **T001–T042 = 42 tareas**
completadas.
**Backend**: Qdrant es el índice de la aplicación; Chroma se conserva hasta el Corte 6. SQLite sigue
siendo la fuente de verdad. No se declara aceptación de 004.

## Correcciones aplicadas

### 1. La candidata decide la publicación; la generación anterior es diagnóstico

Antes, un huérfano en la generación anterior impedía activar una candidata correcta y los reintentos
quedaban en `partial`. Ahora:

- `missing_chunks`, `extra_chunks` y `skipped_chunks` describen la **candidata** y deciden su
  publicación.
- `previous_missing_chunks` y `previous_extra_chunks` describen la generación activa anterior y son
  **diagnóstico**. Un índice anterior desactualizado no bloquea una candidata completa.
- Siguen bloqueando la publicación: faltantes o sobrantes de la candidata, fragmentos incompatibles y
  errores de escritura.
- La generación anterior se conserva; no se borra nada.
- Los huérfanos se siguen detectando y reportando; nunca se resuelven como cita.

Contratos y diseño sincronizados: `contracts/rebuild.md`, `data-model.md` (esquema del reporte) y
`plan.md` §Rebuild workflow. La constitución no cambia: no se altera una decisión de diseño, solo se
precisa la validación ya prevista.

### 2. El reporte terminal se publica dentro del lock

`rebuild()` construye y escribe `latest.json` dentro de la sección protegida; el context manager
libera el lock incluso si la escritura falla. Una ejecución anterior no puede sobrescribir el reporte
después de otra operación.

### 3. Conteo del corte

El Corte 2 son 33 tareas (T010–T042); las 42 completadas corresponden al acumulado T001–T042.

## Pruebas ejecutadas

```text
uv run pytest test_qdrant_rebuild.py test_qdrant_rebuild_failures.py \
  test_qdrant_status.py test_qdrant_retrieval.py → 17 passed
make check → 505 passed, 35 deselected
uv run pre-commit run --all-files → Passed
```

Regresiones nuevas (en `test_qdrant_rebuild_failures.py`):

- Índice anterior con huérfano → candidata válida → `completed`, `previous_extra_chunks=1`, alias
  nuevo y recuperación sin el huérfano.
- Versión anterior sustituida por la vigente → `completed` y solo los `chunk_id` de la versión actual.
- Reconstrucción repetida → `completed`, nueva generación, mismo conteo, sin duplicados.
- Candidata defectuosa (punto extra inyectado en la candidata) → `partial` y alias anterior conservado.
- Publicación del reporte con el lock adquirido (sonda `inspect_lock` durante `_write_report`).

## Prueba real: Qdrant servidor + EmbeddingGemma

Instancia `cut2-fix-smoke`, storage y corpus temporales, `sample.pdf` ficticio, 768 dimensiones.

```text
rebuild 1: completed  public(extra=0, prev_extra=0, skipped=0) case(0,0,0)
rebuild 2: completed  public(0,0) case(0,0)
huérfano inyectado en la generación pública activa
rebuild 3: completed  public(extra=0, prev_extra=1) case(0,0)
search: ok, 2 hits, orígenes case_evidence + public_corpus, huérfano ausente
```

La tercera reconstrucción diagnostica el índice anterior desactualizado y publica la candidata. El
servicio se detuvo con `make qdrant-down` (sin `-v`) y el volumen se conservó.

## Limitaciones vigentes

- Un caso sin documentos privados sigue devolviendo `case_index_unavailable`; el alcance esperado es
  T053 (Corte 4).
- Sin calibración de umbral.
- Chroma y sus datos permanecen.
- En el volumen local de Qdrant quedan colecciones de smokes propios (`cut2-smoke`, `cut2-fix-smoke`).
- No se declara aceptación de 004.

## Commits de esta pasada

- `12d6e51` corpus con lock · `5be439b` reconstrucción · `83f2fc4` lock y mapeo de conflictos ·
  `373b136` pruebas de recuperación y turno · `6fc5e84` evidencia del corte.
- `c1ccf0c` validación de la candidata y reporte bajo lock.

## Siguiente paso

Corte 3 (T043–T053): citas/evidencia y reinicio/disponibilidad. No se inició T043.
