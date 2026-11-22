# Corte 6 — Retiro de Chroma, calibración, evaluación y aceptación (T070–T082)

**Fecha de cierre**: 2026-11-22 (America/Bogota, `-05`)
**Rama**: `004-qdrant-vector-index`
**Alcance**: Corte 6, T070–T082. Este documento es autocontenido: estado, comandos,
resultados observados, reportes, capturas, limitaciones y commits.

## Estado

| Tarea | Estado | Evidencia |
|---|---|---|
| T070–T073 retiro de Chroma | Completada | Sin `ChromaIndex`, `chroma_dir`, `chromadb` ni `langchain-chroma`; `storage/chroma` intacto. |
| T074–T076 calibración y umbral | Completada | Servidor Qdrant real + EmbeddingGemma; umbral **0.5033** aplicado en `config.py`. |
| T077–T078 evaluación funcional | Completada | Evaluación final con umbral congelado: **6/6**, sin fugas, versiones y cita histórica válidas, Qualys separado. |
| T079 aceptación de interfaz | Completada | ASGI `tests/acceptance/test_qdrant_ui.py` (4 pruebas) y recorrido Playwright MCP con servidor real. |
| T080 documentación operativa | Completada | README, AGENTS, quickstart, contratos y documentos vigentes alineados con Qdrant. |
| T081 regresión final | Completada | `make check` 562 passed; `make test-integration` 36 passed, 0 failed, 0 skipped. |
| T082 cierre de constitución | Completada | «Implementado y aceptado localmente»; Chroma y datos intactos. |

## Entorno observado

- Qdrant servidor **1.20.0** en `http://127.0.0.1:6333` (Docker Compose local, volumen persistente).
- Cliente `qdrant-client==1.20.0`; métrica **cosine**.
- Embeddings locales `embeddinggemma`, **768** dimensiones.
- Generador local `qwen3.5:9b`, razonamiento desactivado; prompt `chat-v8`.
- `LANGSMITH_TRACING=false`; sin llamadas pagadas ni envíos externos.
- Almacenamiento temporal propio por ejecución; no se modificó `storage/` ni `storage/demo`.

## Retiro de Chroma (T070–T073)

- `ChromaIndex`, `chroma_dir`, el import de `chromadb` y las dependencias `langchain-chroma`/`chromadb`
  se retiraron con `uv lock`/`uv sync --locked`.
- Fixtures y pruebas usan `tests/fixtures/qdrant.py` (Qdrant embebido o servidor).
- `grep` no encuentra referencias ejecutables a Chroma en `src/`, `scripts/` ni `pyproject.toml`.
- `storage/chroma` y sus archivos permanecen; no se borró ningún dato.
- La constitución se actualizó a «backend sustituido; aceptación pendiente» durante el corte y se
  cerró en T082 con la evidencia de T081.

## Calibración y evaluación

### Iteración 1 — histórica, Qdrant embebido

Ejecutada con `QdrantClient(path=...)` (embebido) y EmbeddingGemma real. Se conserva como
antecedente y no se presenta como ejecución contra servidor. Informes: `calibration.json` y
`evaluation.json`.

- Umbral propuesto y observado: **0.4956**.
- Evaluación: **3/4** recuperaciones; el caso A obtuvo 0.4359 < 0.4956.
- **No se ajustó** el umbral ni los criterios con ese resultado.

### Corrección del evaluador

Hallazgos corregidos antes de la iteración 2:

- Modalidad explícita (`--backend server|embedded`); el servidor es el valor por defecto.
- Aislamiento medido comparando documentos recuperados con los prohibidos de cada caso; el corpus
  público compartido no cuenta como fuga. Prueba unitaria que inyecta una fuga y la detecta.
- Qualys medido con una importación ficticia y conteos antes/después de documentos, fragmentos, puntos
  y citas; sin constantes.
- Resultado global `outcome.passed` y un criterio por requisito; el comando termina con código 1 si
  algo falla y conserva el reporte.
- Pruebas unitarias del evaluador: recuperación incompleta, no pertinente aceptada, fuga, versión
  superada, cita inválida y Qualys alterado.

### Iteración 2 — servidor real

```text
Calibración (CAL2, Qdrant 1.20.0): umbral 0.5033, satisfecho.
  relevantes: 0.5300, 0.5197, 0.6290, 0.5033, 0.6184, 0.5411
  no pertinentes: máximo 0.2785
Evaluación final (FINAL, umbral congelado 0.5033):
  6/6 recuperadas; 0 no pertinentes aceptadas; 0 fugas;
  versión vigente sin fuga de la superada; cita histórica válida;
  Qualys sin cambios (documentos, fragmentos, puntos y citas).
```

- Identidad del conjunto final: `da9b64efe877c63c…` (SHA-256 completo en `evaluation-final.json`).
- Informes: `calibration-iter2.json` y `evaluation-final.json` (modalidad `server`, versión, modelo,
  dimensión, métrica, `top_k`, umbral, fecha y hash del conjunto).
- Prueba de integración: `tests/integration/test_qdrant_functional_eval.py` exige `outcome.passed` y
  todos los criterios; usa una instancia única por ejecución.

## T079 — Aceptación de interfaz

### ASGI

`tests/acceptance/test_qdrant_ui.py` (4 pruebas, índice Qdrant embebido y dobles rápidos):

1. Navegación y secciones (`/cases`, resumen, documentos, vulnerabilidades, chat), menú móvil y
   recursos JS.
2. Carga de documento, consulta con cita válida, apertura del fragmento y evidencia de ejecución.
3. Indicador de carga (`data-pending-indicator`), error de formulario y protección contra doble envío
   (`forms.js`, `htmx:beforeRequest`, `setPending`).
4. Fallo de índice visible: `503` con «El índice documental no está disponible.», sin abstención falsa.

### Playwright MCP contra servidor real

Servidor local con almacenamiento temporal, Qdrant 1.20.0, EmbeddingGemma y `qwen3.5:9b`:

1. Crear el caso ficticio «Caso de aceptación Cut 6».
2. Cargar «Política de respaldo» (Markdown ficticio); estado **Disponible**.
3. Preguntar «¿Cada cuánto se prueba la restauración del respaldo?».
4. Indicador de carga visible y botón deshabilitado durante la consulta.
5. Respuesta: «La organización prueba la restauración trimestralmente.» con cita, control automático
   **válida** y `similarity 0.6493`.
6. Abrir el fragmento: la oración citada queda resaltada (`<mark>`).
7. Abrir «Ver ejecución»: intento 1, finalizada, 17409 ms, decisión 9653 ms, generación 7682 ms,
   recuperación 51 ms, `qwen3.5:9b`, `embeddinggemma` 768, presupuesto y citas.
8. Sección Vulnerabilidades: renderiza sin importaciones confirmadas.
9. Móvil 390×844: menú lateral como diálogo, foco en «Cerrar menú», `aria-expanded=true`, Escape
   cierra; sin desbordamiento horizontal (`scrollWidth == clientWidth`).
10. Consola sin mensajes; recursos locales (`app.css`, HTMX, Flowbite, navigation.js, forms.js) `200`.

Capturas versionadas (solo datos ficticios):

- `ui-documents.png`
- `ui-loading.png`
- `ui-chat-citation.png`
- `ui-fragment.png`
- `ui-run-evidence.png`
- `ui-vulnerabilities.png`
- `ui-mobile-menu.png`

## T080 — Documentación operativa

- `README.md`: Qdrant como índice derivado y reconstruible; SQLite como fuente de verdad; comandos
  `make qdrant-up|qdrant-health|qdrant-rebuild` y `--status`; papel limitado del modo embebido;
  diagrama y tabla de stack actualizados.
- `AGENTS.md`: backend documental, comandos operativos y modo embebido solo para pruebas.
- `specs/004-qdrant-vector-index/quickstart.md`: estado implementado, comandos vigentes y sección de
  calibración/evaluación con `--dataset`/`--backend`.
- `contracts/retrieval.md`: umbral 0.5033 y criterios de la evaluación final.
- `docs/arquitectura/diagrama-arquitectura.html` y `docs/presentacion/Guia_Estudio_y_Demo_SecGuard_Advisor.md`:
  referencias activas a Qdrant.
- Evidencias de los cortes 1–5 anotadas como **registro histórico**.
- Referencias a Chroma que permanecen están etiquetadas como «sin migrar», «sin retorno», «no fallback»
  o «retirado del código».

## T081 — Regresión final

```text
make check              → 562 passed, 36 deselected, 17 warnings (13.16 s)
make test-integration   → 36 passed, 0 failed, 0 skipped, 562 deselected (1225.16 s)
pre-commit --all-files  → Passed
```

- 36 integraciones: regresión de 001 y 002, recuperación, citas, memoria, aislamiento, reconstrucción,
  errores explícitos y separación de Qualys del índice documental.
- Omitidas: 0 en integración. `make check` deselecciona las 36 de integración por marcador.
- SC-001 y SC-003 de 001 no se ejecutaron; son recomendadas y no bloqueantes.

### Correcciones dentro de T081

1. `tests/fixtures/qdrant.py`: instancia derivada por ruta de almacenamiento en lugar del ID fijo
   `test-integration`, para no colisionar con un volumen Qdrant persistente.
2. `test_memory_restart_isolation`: reabre el índice embebido sembrado, no un namespace de servidor.
3. `test_qdrant_functional_eval`: instancia única por ejecución.

El umbral 0.5033, el conjunto final y los criterios no cambiaron.

### Tiempos de espera ampliados

`test_answer_real.py` y `test_journey_real.py` usan `run_timeout_seconds=600` y
`llm_timeout_seconds=300` solo en el arnés. Verifican funcionalidad bajo carga, no el tiempo de
respuesta de producción. Los límites de 120 s por turno y 90 s por llamada conservan sus pruebas en
`tests/unit/test_limits.py`, `tests/unit/test_llm_client.py` y `tests/contract/test_chat_routes.py`.

Demora observada: un turno real superó los 120 s y el producto devolvió `timeout` explícito; la suite
completa tardó 1225 s. Se registra como limitación del modelo local.

## T082 — Cierre de constitución

- `.specify/memory/constitution.md` → «implementado y aceptado localmente»; `CONSTITUTION.md` sigue
  siendo el enlace simbólico.
- `storage/chroma/chroma.sqlite3` y su colección siguen presentes; sin cambios en `storage/` ni
  `storage/demo`; sin borrado de volúmenes.
- 82/82 tareas marcadas. Sin push ni publicación.

## Reproducción

```bash
make qdrant-up
# Calibración (histórica, ya ejecutada)
uv run python scripts/qdrant_threshold.py --mode calibrate --dataset cal2 --backend server \
  --output docs/evidencia/004-corte-6/calibration-iter2.json
# Evaluación final con el umbral congelado
uv run python scripts/qdrant_threshold.py --mode evaluate --dataset final --backend server \
  --threshold 0.5033 --output docs/evidencia/004-corte-6/evaluation-final.json
# Pruebas afectadas
uv run pytest tests/acceptance/test_qdrant_ui.py -q
uv run pytest tests/integration/test_qdrant_functional_eval.py -q
make check
make test-integration
make qdrant-down
```

## Limitaciones observadas

- El modelo local `qwen3.5:9b` puede superar el presupuesto de producción de 120 s bajo carga
  concurrente. La respuesta correcta del producto es `timeout` explícito; las pruebas de integración
  que miden citas y memoria amplían su propio presupuesto para no confundir latencia con un defecto
  funcional (ver §T081).
- La aceptación de navegador se ejecutó en Chromium; otros navegadores siguen pendientes.
- SC-001 y SC-003 de 001 son validaciones humanas recomendadas y no bloqueantes; no se ejecutaron y no
  se presentan como aprobadas.
- La CI remota no se ejecutó.

## Commits

- `e7ecc79` — retiro de Chroma y Qdrant como único índice.
- `4bd84d3` — calibración, evaluación y documentación del corte.
- `5951189` — evaluador con aislamiento y Qualys medidos.
- `71bdadd` — prueba de integración alineada con el contrato vigente.
- Commits de T079–T082: ver la sección de cierre al final de este documento.
