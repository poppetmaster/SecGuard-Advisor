# Paquete de evidencia — Funcionalidad 001

**Fecha de aceptación local**: 2026-11-09
**Alcance**: T001–T095 del primer incremento. No incluye CSV de Qualys, clasificación,
entrenamiento, exportaciones ni otras funciones posteriores.
**Naturaleza de los datos**: escenario educativo sintético y corpus público. No es una validación
empresarial ni una certificación de cumplimiento.

## 1. Alcance terminado

- US1: creación, listado, detalle y recuperación de casos.
- US2: documentos PDF/Markdown, corpus público, versiones, fragmentos, embeddings e índice.
- US3: consulta en español, citas localizables, control automático, abstención y revisión humana.
- US4: memoria por caso y navegación multipágina.
- US5: `findings_query` con alcance por clausura, conteos en SQLite y presentación sintética.
- US6: evidencia de ejecución, intentos, límites, trazas y redacción de secretos.
- T088–T095: integración final, aceptación con dobles, aceptación real, confirmación de traza,
  validación del quickstart, coherencia documental, comprobaciones finales y este paquete.

## 2. Preparación de la demostración

Requisitos:

- Python 3.14.6 y `uv` 0.13.0.
- Ollama con `qwen3.5:9b` (digest `56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90`)
  y `embeddinggemma`.
- Node.js 26.11.1 solo para regenerar CSS.
- `SECGUARD_REVIEWER_NAME` si se va a registrar revisión humana. Es una identidad declarada, no
  autenticación.
- `LANGSMITH_*` si se quiere traza externa. Sin credenciales, la consulta funciona y la traza queda
  `disabled`.

Comandos mínimos:

```bash
make install
make assets
uv run alembic upgrade head
make corpus
make corpus-ingest
make seed-demo
make demo          # storage/demo + seed + servidor en 127.0.0.1:8000
```

`make demo` no toca `storage/`: usa `storage/demo`. La aceptación real usó un directorio temporal
separado (`SECGUARD_ACCEPTANCE_DIR`), nunca los casos del usuario.

## 3. Recorrido breve de demostración

1. Abrir `/cases` y mostrar los dos casos de aceptación. Comprobar la marca «Escenario educativo».
2. Abrir el caso de demostración y revisar el resumen con activos.
3. Entrar en **Documentos**: «Política de respaldo» está `Disponible`; el corpus público se consulta
   desde la recuperación.
4. En **Consulta documental**, preguntar: «¿Cada cuánto se prueba la restauración de las copias de
   seguridad?». Abrir la cita y comprobar el fragmento exacto, la procedencia y el control automático.
5. Preguntar: «¿Cuáles son las seis funciones centrales del NIST Cybersecurity Framework 2.0?».
   Comprobar cita del corpus, página y fragmento.
6. Preguntar el seguimiento: «¿Y cómo se relaciona eso con la gestión de riesgos de IA?». Comprobar
   que la conversación conserva ambos turnos.
7. Preguntar: «¿Cuántos hallazgos de severidad High están registrados? Agrúpalos por activo.».
   Comprobar `findings_query`, Total 4, los tres activos, la etiqueta sintética y la procedencia.
8. Abrir **Ver ejecución** de la primera respuesta: modelo, digest, duración, pasos, presupuesto,
   fuentes, citas, control automático y revisión humana separados, y traza confirmada.
9. Mostrar el caso aislado: una ejecución del caso principal devuelve 404 bajo el otro caso; una
   consulta de hallazgos devuelve Total 0 y la nota de que no demuestra ausencia de vulnerabilidades.
10. Reiniciar el servidor y recargar: casos, documentos, conversación, citas, revisiones y ejecuciones
    siguen presentes.

Preguntas sugeridas y qué comprueba cada una:

| Pregunta | Comprueba |
|---|---|
| ¿Cada cuánto se prueba la restauración de las copias de seguridad? | Evidencia del caso, cita literal y control automático |
| ¿Cuáles son las seis funciones centrales del CSF 2.0? | Corpus público, cita con página y fragmento |
| ¿Y cómo se relaciona eso con la gestión de riesgos de IA? | Memoria y continuidad conversacional |
| ¿Cuántos hallazgos High hay por activo? | Herramienta, conteos y procedencia sintética |
| ¿Cuál es la capital de Francia? | Abstención sin citas inventadas |

## 4. Resultados observados en la aceptación real

Entorno: macOS 27.0.1, Python 3.14.6, Ollama 0.34.4, modelo `qwen3.5:9b`, embeddings
`embeddinggemma` (768 dimensiones).

Corpus ingerido: cuatro fuentes oficiales verificadas.

| Fuente | Versión |
|---|---|
| `csf2` | NIST CSWP 29 |
| `airmf` | NIST AI 100-1 |
| `ai6001` | NIST AI 600-1 |
| `owasp-llm-2025` | OWASP Top 10 for LLM Applications 2025 |

Caso sintético: 12 hallazgos, 3 activos, checksum
`e4ba2e5e099f0ddaac2b77961da90bfb215057a1d3a7512f3a84ba618dd32c20`.

Turnos reales:

| Pregunta | Resultado | Duración | Traza |
|---|---|---:|---|
| Restauración de copias | `answered`, cita del caso | 16.363 s | `submitted` → confirmada |
| Seis funciones del CSF 2.0 | `answered`, cita del corpus página 8 | 62.488 s | `submitted` |
| Seguimiento de riesgos de IA | `answered`, varias citas | 102.519 s | `submitted` |
| Hallazgos High por activo | `answered` con `findings_query` | 55.984 s | `submitted` |
| Capital de Francia | `insufficient_evidence`, sin citas | 22.635 s | `submitted` |

Cita del caso:

> «La organización realiza copias de seguridad cifradas cada 24 horas y prueba la restauración
> trimestralmente.»

Respuesta: «La organización prueba la restauración de las copias de seguridad trimestralmente.»
Control automático: válida. Revisión humana registrada: respaldada por `Aceptación de prueba` el
2026-11-09, con la observación «El fragmento sostiene la afirmación.». Esa identidad es declarada de
prueba, no una persona ni autenticación.

Hallazgos contrastados con SQLite:

```text
total: 4
api-gateway: 2
customer-portal: 1
internal-wiki: 1
```

La ejecución registró dos invocaciones de `findings_query` con los mismos argumentos
(`severity=High`, `group_by=asset`), ambas dentro del máximo de dos; los conteos coinciden con SQLite.

Memoria y reinicio: se abrieron y cerraron la base y el checkpointer tres veces consecutivas; el
historial del caso conservó 12 mensajes en los tres intentos. La conversación incluye las cinco
preguntas, la abstención y el reintento.

Aislamiento: el caso `a1294de2044e441ba51c1a28883c715f` devolvió Total 0 para hallazgos y una
ejecución del caso principal respondió 404 bajo ese caso.

Reintento: la ejecución fallida `fefcaf34a6a444fda7b2939c39e124da` se reintentó como
`ab380b063ab7418ca4b826adc9c5f89f`, intento 2, con la misma pregunta y `retry_of_run_id`; terminó
`answered`.

## 5. Traza confirmada

- Proyecto: `secguard-advisor-dev`.
- Ejecución local: `6f33353e3a264ad593156c4fd04d8c9d`.
- Traza: `01a1bf0c-961c-7672-ae65-ceef31b5f66e`.
- Confirmación: `scripts/confirm_trace.py` verificó por API de lectura que la traza existe, pertenece
  al proyecto y sus metadatos coinciden con `run_id`, `case_id` y `attempt_no`.
- Identidad declarada: `Aceptación de prueba`.
- Fecha: `2026-11-09T06:49:26.239214+00:00`.
- Salida completa: [`trace-confirmation.json`](demo-001/trace-confirmation.json).
- Antes de confirmar, una traza ajena a la ejecución fue rechazada con `trace_mismatch` y no modificó
  el estado local.

## 6. Requisitos y criterios

Los artefactos mantienen **68 requisitos funcionales** y **15 criterios medibles**. La evidencia por
rango:

| Requisitos | Cobertura localizable |
|---|---|
| FR-001..FR-007 | `tests/unit/test_cases_service.py`, `tests/contract/test_cases_routes.py`, `tests/integration/test_case_persistence.py` |
| FR-008..FR-023 | pruebas de documentos, corpus, versiones, reimportación, aislamiento e ingesta real |
| FR-024..FR-035 | `tests/integration/test_answer_real.py`, citas, abstención, presupuesto y prompt injection |
| FR-036..FR-040 | `tests/unit/test_memory.py`, `test_memory_followup.py`, `test_memory_restart_isolation.py`, aceptación real |
| FR-041..FR-050 | `tests/unit/test_findings_tool.py`, `test_tool_binding.py`, `tests/integration/test_findings_real.py` |
| FR-051..FR-057 | `tests/unit/test_run_states.py`, `test_limits.py`, `test_tracing_status.py`, `tests/contract/test_runs_routes.py` |
| FR-058..FR-064 | pruebas de alcance, archivos, credenciales, redacción y navegación |
| FR-065..FR-068 | `test_citation_review.py`, `test_turn_retry.py`, `test_concurrency_guard.py`, aceptación |

Criterios medibles:

| Criterio | Estado | Evidencia |
|---|---|---|
| SC-001 | Parcial | Recorrido automatizado completo en 333,89 s; no se cronometró a una persona |
| SC-002 | Cumplido | Todas las citas reales resolvieron a fragmento y página/sección; pruebas de citas |
| SC-003 | Pendiente | Una revisión declarada de prueba; faltan 10 revisiones humanas reales |
| SC-004 | Cumplido | Total 4 y grupos idénticos a SQLite |
| SC-005 | Cumplido | Aislamiento real y pruebas 404 entre casos |
| SC-006 | Cumplido | Tres reinicios consecutivos con 12 mensajes cada uno |
| SC-007 | Cumplido | Pruebas de reimportación idéntica sin nuevos fragmentos |
| SC-008 | Cumplido | Toda ejecución real tiene estado y duración |
| SC-009 | Cumplido | `test_trace_and_fallback.py`: LangSmith caído, consulta local completa |
| SC-010 | Cumplido | La página de ejecución muestra `findings_query`, argumentos y resumen |
| SC-011 | Cumplido | Pruebas de validación y estados de documentos |
| SC-012 | Cumplido | Pregunta fuera de alcance real: `insufficient_evidence` sin citas |
| SC-013 | Cumplido | Reintento real: intento 2, misma pregunta, sin duplicar usuario |
| SC-014 | Cumplido | Aceptación rápida: 409 con ejecución activa; pruebas de concurrencia |
| SC-015 | Cumplido | Aceptación rápida: 429 con permiso global ocupado; pruebas de concurrencia |

## 7. Comprobaciones finales

```text
make check            → 343 passed, 25 deselected
make test-integration → 25 passed in 881.19s (14m41s)
```

La suite de integración incluye `tests/acceptance/test_journey_real.py` con Ollama, EmbeddingGemma,
corpus oficial, caso sintético, `findings_query`, reinicio, aislamiento y reintento. La suite rápida
incluye `tests/acceptance/test_journey.py` con dobles.

Migraciones: `alembic upgrade head` sobre almacenamiento vacío aplicó `d2fac73b7c90` →
`8a1c2f3d4e5f` → `9c3e4f5a6b7d`, con `trace_url` y la auditoría de confirmación.

`make install`, `make assets`, `make corpus`, `make corpus-ingest` y `make demo` se ejecutaron sin
error. `make demo` sirvió `/healthz` con base y Ollama disponibles y el caso sintético de 12 hallazgos.

## 8. Evidencia visual

En [`docs/evidencia/demo-001/`](demo-001/):

- `casos.png`, `resumen.png`, `documentos.png`.
- `cita.png`: fragmento exacto y «Volver a la consulta».
- `ejecucion-confirmada.png`: traza verificada, control automático y revisión humana separados.
- `herramienta.png`: `findings_query`, Total 4 y procedencia sintética.
- `fallida.png`: error comprensible y acceso al reintento.
- `aislamiento-404.png`: ejecución de otro caso no encontrada.
- `carga.png`: indicador, botón deshabilitado y un solo POST ante doble clic.
- `menu.png`, `movil-390.png`, `movil-320.png`: menú, foco y ausencia de desbordamiento.
- `acceptance-summary.json`: hechos observados de la aceptación real.
- `trace-confirmation.json`: salida de la confirmación por API de lectura.

Navegador: Chromium vía Playwright MCP. Página de ejecución correcta: 0 errores de consola y todos
los recursos locales con estado 200. En escenarios fallidos hay un 404/503 esperado de la petición,
no un defecto de la interfaz.

## 9. Limitaciones y pendientes

- **SC-003**: faltan diez revisiones humanas reales de afirmaciones normativas. La revisión registrada
  con `Aceptación de prueba` es una identidad declarada de prueba, no una persona.
- **SC-001**: el recorrido automatizado se completó en 333,89 s, pero no se cronometró a una persona
  que conozca el producto.
- Revisión visual en navegadores distintos de Chromium pendiente.
- Cuatro vulnerabilidades bajas de npm en la cadena de Flowbite; no afectan al servidor y no se aplicó
  una corrección que degrade Flowbite.
- CI remota no ejecutada: no hay remoto. No se declara CI en verde.
- La confirmación de traza no es una revisión semántica de la respuesta ni una aprobación del informe.
- El tokenizador y la plantilla dependen del modelo instalado; un cambio de modelo o de Ollama exige
  recalibrar el presupuesto.
- Los hallazgos son educativos y sintéticos; no son el conjunto final de evaluación ni una importación
  de Qualys.
- No se implementaron funciones de incrementos posteriores.

## 10. Distribución sugerida de la demostración

Propuesta, no medida: 2 minutos para casos y documentos; 3 minutos para las preguntas documental y de
seguimiento; 2 minutos para hallazgos y ejecución; 1 minuto para aislamiento, reintento y cierre. No se
presenta como una duración cronometrada.
