# Quickstart — validación de la funcionalidad 001

Guía de ejecución y validación. Los comandos descritos existen y se ejecutaron en almacenamiento
separado; los resultados observados están en `docs/evidencia/demo-001.md`.

## 1. Prerrequisitos

- Python 3.14.6 y `uv`.
- Ollama con `qwen3.5:9b` y `embeddinggemma` descargados.
- Node.js solo para regenerar CSS; no se necesita para ejecutar.
- `LANGSMITH_*` en `.env` si se quiere traza real. Sin credenciales, la aplicación funciona y
  declara la traza como no configurada.
- `SECGUARD_REVIEWER_NAME` en `.env` para poder registrar la revisión humana del respaldo. Sin ese
  valor, la revisión se rechaza; no es autenticación.
- **Un solo proceso y un worker.** Los comandos de ejecución fijan `--workers 1`; el semáforo
  global y la reconciliación de arranque lo asumen.

## 2. Comandos

| Comando | Efecto |
|---|---|
| `make install` | `uv sync`, hooks de pre-commit y dependencias de CSS |
| `make corpus` | Descarga y verifica las fuentes del corpus; escribe el manifiesto |
| `make seed-demo` | Carga el caso de demostración y los hallazgos sintéticos deterministas |
| `make assets` | Compila Tailwind y verifica los recursos vendorizados |
| `make dev` | Servidor local en `127.0.0.1` con recarga |
| `make demo-prepare` | Prepara `storage/demo`: migraciones, corpus público ingerido y dataset sintético |
| `make demo` | Ejecuta `demo-prepare` y arranca el servidor con un worker sobre `storage/demo` |
| `make test` | Pruebas unitarias y de contrato (sin Ollama, para CI) |
| `make test-integration` | Pruebas reales con Ollama, embeddings, recuperación y herramienta |
| `make check` | Lint, formato y pruebas rápidas |
| `make clean` | Limpia cachés y artefactos locales |

`make demo` no toca `storage/`: usa `storage/demo`. `make corpus-ingest` y `make seed-demo` operan
sobre el `SECGUARD_STORAGE_DIR` configurado; no preparan `storage/demo` por sí solos. `make dev` usa
el almacenamiento configurado por `SECGUARD_STORAGE_DIR` (por defecto `storage/`). Para la aceptación
se usó un directorio temporal separado, nunca los casos del usuario.

Preparación explícita de la demo (la preparación queda fuera del cronómetro de SC-001):

```bash
make corpus          # una vez; requiere red y deja data/corpus verificado
make demo-prepare    # storage/demo: migraciones + corpus + seed
make demo            # arranca storage/demo en 127.0.0.1:8000
```

## 3. Matriz de verificación

| Historia | Requisitos | Verificación |
|---|---|---|
| H1 Caso | FR-001..FR-007 | Unitarias de servicio; contrato de rutas; reinicio con base real |
| H2 Documentos | FR-008..FR-023 | Unitarias de validación, extracción y deduplicación; integración de ingesta |
| H3 Consulta y citas | FR-024..FR-035 | Integración con generador real; validación de citas; abstención |
| H4 Memoria | FR-036..FR-040 | Integración de dos turnos; reinicio; dos casos |
| H5 Hallazgos | FR-041..FR-050 | Unitarias de herramienta y recálculo; integración de uso por el modelo |
| H6 Ejecución | FR-051..FR-057 | Integración; inspección de `runs`; traza real en LangSmith |
| Seguridad | FR-058..FR-064 | Pruebas de alcance, archivos y credenciales |

## 4. Recorrido de aceptación

Cada paso indica el resultado observable esperado. No se declara un paso cumplido por inspección
visual solamente.

### Paso 1 — Crear un caso

Abrir `/cases/new`, crear «Evaluación de un asistente interno de IA» dejando vacíos «datos
tratados» y «restricciones».

**Esperado**: el caso aparece en `/cases` con fecha y marca de escenario educativo; los campos
vacíos se muestran como desconocidos y no se completan.

### Paso 2 — Incorporar documentos

Cargar un PDF textual, un Markdown, un PDF escaneado y un archivo corrupto.

**Esperado**: los dos primeros pasan a «disponible» y son consultables; el escaneado queda «sin
texto utilizable» con explicación; el corrupto se rechaza con motivo. Ninguno de los dos últimos
se muestra como completado.

### Paso 3 — Reimportación

Subir otra vez el mismo PDF y luego una versión modificada.

**Esperado**: la reimportación responde «ya existe» y el conteo de fragmentos no cambia. La versión
modificada crea una versión nueva; la anterior queda como superada y sigue siendo localizable.

### Paso 4 — Pregunta con cita

Preguntar algo cubierto por el corpus, por ejemplo sobre las funciones del CSF 2.0.

**Esperado**: respuesta en español, con al menos una cita que abre el fragmento exacto y muestra
documento, página o sección. La respuesta se marca como borrador y separa hechos de
recomendaciones.

### Paso 5 — Seguimiento con memoria

Preguntar «¿y cómo se relaciona eso con la gestión de riesgos de IA?».

**Esperado**: la respuesta aprovecha el contexto anterior sin exigir repetición. La conversación
muestra ambos turnos con sus citas.

### Paso 6 — Hallazgos con herramienta

Preguntar «¿cuántos hallazgos críticos hay por activo?».

**Esperado**: conteo por activo calculado sobre los registros. Recalcular de forma independiente
con una consulta a la base y comparar: debe coincidir. La ejecución muestra
`findings_query` con `origin=model_requested`.

### Paso 7 — Pregunta sin evidencia

Preguntar por un tema fuera del corpus, por ejemplo una norma que no está cargada.

**Esperado**: el sistema declara información insuficiente; no inventa una cita ni responde como si
tuviera respaldo.

### Paso 8 — Reinicio

Detener el servidor, volver a iniciarlo y abrir el caso.

**Esperado**: caso, documentos, conversación y ejecuciones intactos. Ninguna versión queda
«procesando».

### Paso 9 — Aislamiento entre casos

Crear un segundo caso sin documentos ni hallazgos, abrirlo y preguntar por documentos y hallazgos.

**Esperado**: no aparece ningún dato del primer caso; la pregunta sobre hallazgos devuelve
«sin hallazgos». Una petición directa a un `document_id` del primer caso devuelve `404`.

### Paso 10 — Evidencia de ejecución

Abrir «Ver ejecución» en la última respuesta.

**Esperado**: modelo con digest, duración, estado, fuentes recuperadas, herramienta usada y estado
de la traza. Si LangSmith está configurado, el identificador aparece, el estado local es
`submitted`; `confirmed` se registra con `scripts/confirm_trace.py` solo después de verificar la
traza por API de lectura. La página distingue «Enviada (no verificada)» de «Verificada». Si no está
configurado, se declara y la consulta funciona igual.

### Paso 11 — Reintentar un turno fallido

Detener Ollama, formular una pregunta y comprobar el estado `failed`. Volver a iniciar Ollama y
reintentar la ejecución.

**Esperado**: el reintento reutiliza la misma pregunta; el historial no gana un segundo mensaje de
usuario; la ejecución nueva queda como intento 2 con referencia al intento anterior; la respuesta
del intento exitoso es la única que aparece. Si la ejecución ya tuviera una respuesta persistida, el
reintento se rechaza.

### Paso 12 — Revisar el respaldo semántico

Con `SECGUARD_REVIEWER_NAME` configurado, abrir una cita de una respuesta y registrar la revisión
como «respaldada» con una observación.

**Esperado**: la cita pasa de «pendiente» a «respaldada», con autor y fecha del servidor. La
revisión no adjudica P1–P4 ni aprueba el informe, y no cambia el control automático de la cita. Sin
`SECGUARD_REVIEWER_NAME`, la operación se rechaza con `409` y no se guarda nada.

## 5. Escenarios negativos

| Escenario | Cómo provocarlo | Esperado |
|---|---|---|
| PDF sin texto | Cargar un escaneo | «Sin texto utilizable», no consultable |
| Archivo falso | Renombrar un `.zip` a `.pdf` | Rechazo por contenido real |
| Archivo grande | Superar el límite | `413` con el límite aplicado |
| Instrucción incrustada | Documento con «ignora las instrucciones» | Se trata como dato; sin acciones externas |
| Pregunta sin fuentes | Tema fuera del corpus | Abstención explícita |
| Pregunta de hallazgos sin documentos | Preguntar un conteo sin coincidencia documental | La herramienta responde; no se abstiene |
| Consulta cruzada | Pedir un documento de otro caso | `404`, sin confirmar existencia |
| Modelo caído | Detener Ollama | Mensaje claro, ejecución `failed`, conversación utilizable |
| Tiempo agotado | Forzar un turno largo | `timeout` registrado, mensaje comprensible |
| Traza caída | Invalidar la clave o cortar la red | Consulta exitosa, traza `failed` |
| Reinicio en ingesta | Reiniciar durante el procesamiento | Documento no disponible, estado interrumpido, reintento posible |
| Reintento de turno fallido | Fallar por Ollama y reintentar | Sin mensaje duplicado; intento 2 identificado |
| Dos consultas simultáneas | Enviar dos preguntas al mismo caso | La segunda se rechaza; no se mezclan respuestas |
| Generación en otro caso | Dos casos, dos preguntas a la vez | Solo una genera; la otra espera `SECGUARD_GENERATION_QUEUE_TIMEOUT_SECONDS` (segundos; 5 por defecto) o recibe `429` |
| Envío duplicado | Doble clic con una ejecución activa | `409`, sin mensaje ni ejecución nuevos |
| Revisor sin configurar | Revisar sin `SECGUARD_REVIEWER_NAME` | `409`; no se guarda la revisión |

## 6. Verificación de citas

1. Abrir la cita y comprobar que el fragmento mostrado contiene la cita textual.
2. Comprobar que la página o sección coincide con el original descargado.
3. Revisar que el fragmento sostiene la afirmación. Este paso es humano y se registra; el sistema
   no lo declara.

## 7. Verificación de la traza real

1. Ejecutar una consulta con `LANGSMITH_TRACING=true` y clave válida.
2. Abrir el proyecto `secguard-advisor-dev` en LangSmith.
3. Confirmar que la ejecución existe y que su metadato `run_id` coincide con el de la aplicación.
4. Ejecutar `uv run python scripts/confirm_trace.py --run-id <local> --trace-id <observado> --reviewer "<identidad declarada>"`:
   solo si la traza existe, pertenece al proyecto y sus metadatos coinciden con la ejecución local se
   registra `confirmed`. Guardar la salida como evidencia.
5. La confirmación es responsabilidad de la persona que ejecuta la aceptación. Debe registrar su
   identidad, la fecha y la evidencia de la traza observada en el reporte de aceptación.
6. Sin credenciales: confirmar que la aplicación responde, que `trace_status=disabled` y que no se
   presenta ninguna traza como real.
7. La identidad de confirmación es declarada, no autenticación. En la aceptación automatizada se usó
   `Aceptación de prueba`; si la cátedra exige una persona, repetir el comando con ese nombre.

## 8. Lo que no debe declararse

- Métricas de calidad, latencia o precisión antes de medirlas.
- Estado de CI en verde sin ejecutarlo.
- Corpus completo si alguna fuente falló.
- Traza verificada sin verla en LangSmith.
- Acreditación de la rúbrica por el hecho de tener esta guía.

## 9. Validación ejecutada

La validación del 2026-11-09 se hizo con almacenamiento temporal separado y datos sintéticos. La
instancia de demostración (`storage/demo`) se prepara aparte y no contiene la traza confirmada de la
aceptación:

- `make install`, `make assets` y migraciones: sin error.
- `make corpus` verificó las cuatro fuentes oficiales y `make corpus-ingest` las ingirió con
  EmbeddingGemma en la base temporal.
- `make seed-demo` cargó el caso sintético con 12 hallazgos.
- El recorrido real está automatizado en `tests/acceptance/test_journey_real.py` y el recorrido con
  dobles en `tests/acceptance/test_journey.py`.
- La traza de la pregunta sobre la evidencia sintética del caso se confirmó por lectura externa con
  `scripts/confirm_trace.py` en la instancia temporal de aceptación; la salida y la identidad declarada
  están en el reporte de evidencia. Esa traza no se copió a `storage/demo`.

Los modelos deben estar instalados previamente. Las credenciales de LangSmith son opcionales: sin
ellas la consulta funciona y la traza queda `disabled`.
