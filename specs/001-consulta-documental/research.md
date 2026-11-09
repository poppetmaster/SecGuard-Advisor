# Research — Funcionalidad 001

Decisiones técnicas con su justificación y las alternativas evaluadas. Todas las ambigüedades
iniciales quedaron resueltas.

## R1. Conteo exacto de tokens para EmbeddingGemma

**Decisión**: usar la propia API de Ollama como oráculo. En la ingesta se llama a
`POST /api/embed` con `truncate: false`; si el texto excede el contexto, la API devuelve error en
lugar de recortar. La respuesta incluye `prompt_eval_count`, que se guarda como `token_count` del
fragmento.

**Cada fragmento se mide en una petición individual.** `prompt_eval_count` es el conteo de la
entrada procesada en esa petición: en una petición por lotes es un agregado y **no** prueba que
cada elemento quepa por separado. Por eso la ingesta no embebe en lote: mide, guarda el vector y
usa ese mismo vector para el índice. El costo es una petición por fragmento; con unos cientos de
fragmentos y un modelo de 300M es aceptable frente al riesgo de truncamiento silencioso.
`token_count_source` registra `ollama_prompt_eval_count_single`.

**Rationale**: el tokenizer de EmbeddingGemma no está disponible localmente sin aceptar la
licencia Gemma en Hugging Face, y el modelo está bajo esa licencia. La API documentada de Ollama
ofrece exactamente lo necesario: error ante exceso y conteo real de tokens procesados.

**Alternativas consideradas**:
- `transformers`/`tokenizers` con el tokenizer oficial: requiere aceptar la licencia, descargar
  pesos y añadir dependencias pesadas; `torch` no es viable hoy en Python 3.14.
- Estimación por relación caracteres/token: incumple la constitución («medirse en tokens del
  modelo de embeddings»).
- `OllamaEmbeddings` de LangChain: no expone `truncate` ni `prompt_eval_count`; truncaría en
  silencio.

## R2. Adaptador propio de embeddings sobre la interfaz de LangChain

**Decisión**: `documents/embedding.py` define un `Embeddings` compatible con LangChain
(`embed_documents`, `embed_query`) cuya implementación usa `httpx` contra `/api/embed`. LangChain
y Chroma lo consumen sin saber que hay HTTP debajo.

**Rationale**: conserva LangChain en el pipeline (constitución, principio III) y a la vez permite
controlar truncamiento, conteo de tokens y prefijos.

**Alternativas consideradas**: usar `OllamaEmbeddings` y verificar después con una segunda
llamada; duplica costo y no evita el truncamiento silencioso.

## R3. Ruta de petición síncrona

**Decisión**: manejadores `def` de FastAPI, SQLAlchemy síncrono, `SqliteSaver` síncrono y
`httpx.Client`. FastAPI ejecuta los manejadores en su pool de hilos.

**Rationale**: no hay streaming en este incremento; la latencia dominante es la inferencia. El
camino síncrono elimina la mezcla de drivers async y sesiones de base, que es la principal fuente
de errores en este tipo de aplicación.

**Alternativas consideradas**: `AsyncSqliteSaver` + `aiosqlite` + SQLAlchemy async; más piezas
móviles sin beneficio medible para un usuario local.

## R4. Una colección de Chroma por caso

**Decisión**: colección `public__<slug_modelo>__<dim>` para el corpus y
`case__<case_id>__<slug_modelo>__<dim>` para cada caso. Los nombres se derivan de forma
determinista en `retrieval/collections.py` a partir del alcance autorizado, el modelo y la
dimensión. No se persiste un registro de colecciones: el conteo sale de `document_chunks` y la
existencia se consulta en Chroma.

**Rationale**: la constitución prohíbe mezclar datos de casos distintos en una colección. Separar
físicamente convierte un error de filtro en una consulta a la colección equivocada, detectable, en
lugar de una fuga silenciosa.

**Alternativas consideradas**: una colección única con `where={"case_id": ...}`; un filtro
omitido devuelve datos de otro caso.

**Límite conocido**: el número de colecciones crece con el número de casos. Aceptable para el
incremento; se revisará con la escala.

## R5. SQLite como fuente de verdad y texto de fragmento almacenado

**Decisión**: `document_chunks` guarda el texto normalizado, sus offsets, página, sección y
`token_count`. Chroma guarda solo vectores y metadatos mínimos. Reconstruir el índice no requiere
volver a extraer el PDF.

**Rationale**: permite cambiar de modelo de embeddings o reconstruir Chroma sin perder
procedencia, y hace que una cita sobreviva a cualquier reindexación.

**Alternativas consideradas**: guardar solo vectores y volver a extraer; lento y frágil ante
cambios de extractor.

## R6. Identidad documental, deduplicación y versiones

**Decisión**: `scope_key` = `case:<case_id>` o `public:<source_id>`. Restricción única
`(scope_key, sha256)`: el mismo contenido no se registra dos veces en el mismo espacio. Un
contenido distinto con el mismo nombre de archivo crea una versión nueva del mismo documento
lógico; un contenido distinto con otro nombre crea un documento nuevo.

**Rationale**: satisface «reimportar no duplica» y «una versión modificada conserva trazabilidad»
con una regla determinista y comprobable en la base.

**Alternativas consideradas**: deduplicar por nombre de archivo; falla ante renombres y permite
duplicados reales.

## R7. Citas: dos controles separados

**Decisión**:
1. **Existencia y localización** (automático): el fragmento existe, pertenece a la versión citada,
   la página o sección coincide y la cita textual aparece literalmente en el texto del fragmento,
   comparando con normalización de espacios.
2. **Respaldo semántico** (humano): una persona comprueba que el fragmento sostiene la
   afirmación. Se registra como revisión, no la afirma el sistema.

Una cita que falla el control 1 se descarta, se registra el motivo en la ejecución y no se muestra.

**Rationale**: el control 1 es determinista y ejecutable en CI. El control 2 no es automatizable
con honestidad; declararlo automático sería el tipo de afirmación sin evidencia que la
constitución prohíbe.

**Alternativas consideradas**: pedir al modelo que autoevalúe el respaldo; no es verificable y
traslada la decisión al actor interesado.

## R8. Evidencia, herramienta y abstención

**Decisión**: la recuperación documental y la herramienta de hallazgos son fuentes distintas. Una
pregunta puede no tener candidatos documentales y ser contestable con la herramienta, así que la
recuperación vacía **no** corta el turno. El agente se ejecuta siempre con la herramienta
disponible y responde con un esquema JSON validado (`answer`, `claims[]` con `chunk_ids`,
`tool_result_ref`, `missing_info[]`, `recommendation[]`) mediante `format` con JSON Schema de
`ChatOllama`.

La abstención se decide después, con reglas deterministas:

1. Hay al menos una cita válida → `answered`.
2. No hay citas, pero hay un resultado de herramienta que sostiene las cifras → `answered` con
   evidencia estructurada.
3. No hay citas ni resultado de herramienta, y la respuesta afirma algo normativo → una única
   reparación; si vuelve a fallar → `abstained_invalid_citations`.
4. Sin respuesta útil → `insufficient_evidence`.

**El umbral de recuperación es un filtro de candidatos débiles, no una prueba de ausencia de
evidencia.** Se calibra durante el desarrollo con datos de humo; nunca con el conjunto final
reservado. Una pregunta sin resultados documentales se distingue de una pregunta que la herramienta
puede responder.

**Rationale**: mantiene la abstención en el código donde importa —no afirmar sin respaldo— sin
bloquear la ruta de hallazgos, que por definición no tiene citas documentales.

**Alternativas consideradas**: cortar en recuperación vacía; habría hecho inalcanzable H5. Dejar
que el modelo decida si se abstiene; no es verificable.

**Calibración observada (2026-11-08, datos de humo, no conjunto final)**: con el corpus oficial
ingerido y EmbeddingGemma, dos preguntas pertinentes obtuvieron similitudes de 0,58 a 0,68 y dos
preguntas fuera de dominio, de 0,05 a -0,01. Se fijó `retrieval_min_score = 0.35`, que separa ambos
grupos sin presentar la recuperación vacía como prueba de ausencia. El generador configurado
(`qwen3.5:9b`) es un modelo de razonamiento: con razonamiento activo la salida estructurada no se
producía dentro del presupuesto (400 tokens, 29 s, contenido vacío); con `reasoning=False` respondió
en 2,7 s. La desactivación es una decisión de implementación, no un cambio de modelo.

## R9. Topología del grafo

**Decisión**: un solo nodo de generación con herramientas, rodeado de nodos deterministas:

`load_scope → retrieve → (sin candidatos) → abstain → persist`

`retrieve → agent ⇄ tools → validate → (ok) → persist`

`validate → (falla) → repair → validate → (falla) → abstain → persist`

Límites: 8 pasos, 2 llamadas a herramientas, 1 reparación de citas, 120 s de turno, 90 s por
llamada al modelo.

**Rationale**: seis historias no justifican varios modelos ni un enjambre de agentes. La
determinación de alcance, recuperación, validación y abstención pertenece al código.

**Alternativas consideradas**: agentes especialistas y enrutamiento por modelo; añade latencia y
superficie de error sin mejorar la evidencia.

## R10. Memoria en base separada

**Decisión**: `storage/checkpoints.sqlite` con `SqliteSaver`; `thread_id` = `conversation_id`.
La conversación visible se lee de `messages` en la base de negocio. Al iniciar un turno, si el
checkpointer no tiene estado para ese hilo, se reconstruye desde los últimos mensajes. Al cargar
un checkpoint se verifica que su `thread_id` coincida con el solicitado.

**Rationale**: el estado interno del grafo no debe acoplarse al esquema de negocio, y una
conversación debe sobrevivir a la pérdida del checkpointer.

**Alternativas consideradas**: usar la misma base para todo; mezcla esquemas y complica las
migraciones.

## R11. Herramienta de hallazgos con alcance en clausura

**Decisión**: la herramienta se construye por turno con `case_scope` capturado en el cierre. Su
esquema expuesto al modelo solo contiene filtros (`asset`, `severity`, `qid`, `cve`, `detail`,
`limit`, `group_by`). La implementación usa SQLAlchemy parametrizado; no existe SQL construido
desde texto del modelo.

**Rationale**: aunque el modelo envíe `case_id`, el argumento no existe en el esquema y no puede
ampliar el alcance. Los conteos salen de `COUNT(*)` sobre las mismas filas que se muestran.

**Alternativas consideradas**: pasar `case_id` como argumento y validarlo; una inyección o un
error de validación abre la puerta.

## R12. Recursos de interfaz

**Decisión**: Tailwind CSS y Flowbite se compilan con Node en desarrollo (`npm ci`, `npm run
build:css`) y el CSS resultante se versiona en `src/secguard_advisor/web/static/css/app.css`.
HTMX y el JS de Flowbite se vendorizan minificados con versión, licencia y SHA-256 en
`static/vendor/MANIFEST.md`. HTMX y Flowbite son MIT; Tailwind es MIT.

**Rationale**: la aplicación se ejecuta sin Node y sin red. Las versiones quedan fijadas y
auditables.

**Alternativas consideradas**: CDN (prohibido), binario standalone de Tailwind (no reproducible
entre sistemas operativos), CSS escrito a mano (incumple el stack).

**Pendiente de verificación en implementación**: elegir la combinación Tailwind/Flowbite
compatible al fijar versiones; no se declara una versión concreta hasta comprobarla.

## R13. Registro de ejecución con origen de cada paso

**Decisión**: `runs`, `run_steps`, `run_sources` y `run_tool_calls`. Cada paso y cada llamada a
herramienta registra `origin` = `deterministic` o `model_requested`.

**Rationale**: el requisito pide distinguir si el modelo solicitó una herramienta o si la
operación la ejecutó el código. Sin ese campo, la distinción se pierde.

**Alternativas consideradas**: inferir el origen desde los logs; no es consultable ni estable.

## R14. Aislamiento del conjunto de evaluación final

**Decisión**: `data/eval/final/` queda reservado y no lo lee ningún módulo de producto. Una prueba
de guardia verifica que ningún módulo de `src/secguard_advisor` referencia esa ruta. Las pruebas de
humo viven en `data/eval/smoke/` y no se presentan como evaluación final.

**Rationale**: la constitución exige que la prueba final no participe en selección ni promoción.
Un aislamiento por ruta, verificado por prueba, es más fuerte que una convención.

## R15. Idempotencia y recuperación de la ingesta

**Decisión**: la ingesta es un trabajo con estados (`queued`, `running`, `succeeded`, `failed`,
`interrupted`). Los fragmentos se escriben con `UNIQUE(version_id, chunk_index)` y la indexación
es un `upsert` por `chunk_id`. Al arrancar, los trabajos en `running` se marcan `interrupted` y la
versión queda reintentable. Reintentar reutiliza el texto extraído si existe.

**Rationale**: un reinicio a mitad de ingesta no duplica fragmentos ni deja documentos
«disponibles» a medias.

**Alternativas consideradas**: borrar y recrear fragmentos en cada intento; pierde citas ya
emitidas.

## R16. Observabilidad mínima

**Decisión**: log estándar con `run_id`, `case_id` y `event`, sin secretos. LangSmith se configura
por entorno; el turno se envuelve en un run con metadatos (`case_id`, `conversation_id`, `model`,
`embedding_model`, `app_version`). `trace_status` se marca `disabled`, `submitted` o `failed`.
Nunca se marca `confirmed` desde el código.

**Rationale**: «submitted» es lo único que el proceso puede afirmar; la existencia real se
comprueba en LangSmith durante la aceptación. La constitución prohíbe presentar una traza como
verificada sin serlo. `confirmed` solo lo escribe el procedimiento de aceptación; el código nunca
lo asigna.

## R17. Concurrencia y transacciones

**Decisión**: dos controles distintos. La **exclusión por caso** es persistida: un índice único
parcial sobre `runs(case_id)` cuando `status='running'`, adquirido atómicamente al insertar la
ejecución. El **límite global de generación** es un semáforo de un permiso en el proceso, adquirido
antes de crear la ejecución con espera acotada y liberado en `finally` después de persistir el
resultado. La aplicación corre en **un solo proceso y un worker**; el semáforo y la reconciliación
de arranque lo asumen.

La ejecución se crea en una transacción corta y se cierra, junto con la respuesta y las citas, en
otra transacción corta. Ninguna sesión de escritura permanece abierta durante la llamada al modelo.
Al arrancar, `running → interrupted` libera la exclusión por caso.

**Rationale**: SQLite con WAL permite lecturas concurrentes, pero una escritura larga bloquea a la
interfaz. El índice parcial hace que la exclusión por caso sea una invariante de base. El semáforo
global impide dos generaciones simultáneas aunque sean de casos distintos, que es lo que el plan
promete y lo que protege la memoria.

**Desconexión**: los manejadores síncronos no se cancelan al cortarse la conexión. La generación
continúa y los controles se liberan solo al terminar o agotar el tiempo. Un timeout del cliente no
habilita generaciones ilimitadas.

**Alternativas consideradas**: un candado en memoria para la exclusión por caso; se pierde al
reiniciar. Una cola persistente de trabajos; fuera de alcance.

## R18. Reintentos idempotentes

**Decisión**: el reintento reutiliza el mensaje de pregunta y crea una ejecución nueva con
`attempt_no` y `retry_of_run_id`. Solo se reintenta `failed`, `timeout` o `interrupted`. El mensaje
asistente solo existe para el intento que terminó con respuesta.

**Rationale**: conserva la pregunta y el orden del historial, distingue los intentos y evita
duplicar mensajes o efectos. Sin esto, cada reintento añadiría un turno falso a la conversación.

**Alternativas consideradas**: reescribir el mensaje de usuario; pierde trazabilidad. Crear una
pregunta nueva; duplica el historial.

## R19. Revisión humana del respaldo semántico

**Decisión**: cada cita admite una revisión humana con estados `unreviewed`, `supported` y
`not_supported`, autor, fecha y observación. El autor se toma de `SECGUARD_REVIEWER_NAME`; si no
está configurado, la revisión no se guarda y se responde con un error claro. Es una identidad local
declarada, no autenticación. Se muestra separada del control automático. No incluye P1–P4 ni
aprobación de informes.

**Rationale**: SC-003 exige un juicio que el código no puede hacer. Convertirlo en un estado
registrado y visible permite acreditar la revisión sin fingir automatización. Sin una identidad
declarada, el campo «autor» sería inventado, que es exactamente lo que la constitución prohíbe.

**Alternativas consideradas**: pedir al modelo que evalúe el respaldo; no es verificable. Añadir
autenticación en este incremento; fuera de alcance. Dejar el autor vacío; incumple FR-065.

## R20. Nueva pregunta, reintento y envío duplicado

**Decisión**: son tres casos distintos y se tratan distinto.

1. **Pregunta nueva después de un turno exitoso**: crea un mensaje de usuario nuevo y una ejecución
   nueva, aunque el texto sea idéntico. No es un reintento.
2. **Reintento de una operación fallida**: exige estado `failed`, `timeout` o `interrupted` **y
   ausencia de respuesta persistida**. Reutiliza el mensaje de pregunta y crea un intento nuevo.
3. **Envío duplicado de la misma solicitud mientras hay una ejecución activa**: se rechaza con un
   mensaje claro y no crea mensaje ni ejecución.

**Rationale**: sin esta distinción, un doble clic podría duplicar la pregunta, y un reintento podría
duplicar la respuesta. En este incremento no hay clave de idempotencia por solicitud; la exclusión
por caso cubre la ventana en la que el duplicado importa.

**Alternativas consideradas**: clave de idempotencia del cliente; añade contrato y estado que el
incremento no necesita. Cola de solicitudes; fuera de alcance.

## R21. Confirmación de una traza observada

**Decisión**: `confirmed` no lo escribe la aplicación. Lo escribe `scripts/confirm_trace.py`, que
recibe el `run_id` local y el identificador de traza, consulta LangSmith en modo lectura para
comprobar que la traza existe y, solo si la encuentra, actualiza `trace_status='confirmed'`. La
evidencia es la salida del comando, el identificador observado y la fecha, registrados en el reporte
de aceptación.

**Rationale**: separa «enviada sin error» (`submitted`) de «observada en la plataforma»
(`confirmed`). Sin la consulta de lectura, confirmar sería confiar en el SDK, que es justo lo que la
constitución prohíbe.

**Alternativas consideradas**: marcar `confirmed` tras `flush`; no prueba que la traza exista.
Revisar la interfaz web y anotarlo a mano sin comando; no deja evidencia reproducible.

## R22. Navegación multipágina con barra lateral

**Decisión**: cada sección es una página GET renderizada por el servidor (`/cases`, `/cases/new`,
`/cases/{id}` como resumen, `/cases/{id}/documents`, `/cases/{id}/chat`, la evidencia de ejecución y
las vistas de documento y fragmento). Un shell único aporta cabecera, barra lateral persistente en
escritorio y menú desplegable en móvil con el mismo marcado. El elemento activo se marca con
`aria-current="page"` y la ruta de navegación es un `nav` con lista. HTMX queda para las
interacciones dentro de cada sección.

**Rationale**: URLs direccionables y recargables, menos estado en el cliente y reutilización de los
contratos existentes. Un shell único evita duplicar plantillas.

**Alternativas consideradas**: SPA con router y navegación HTMX global; añade estado, duplica la
fuente de verdad de rutas y rompe el renderizado del servidor ya probado.

**Componentes**: Flowbite gratuito ya instalado (sidebar, drawer, breadcrumbs) con Tailwind local. El
bloque desplegable de fragmentos usa `<details>` nativo para no reinicializar componentes tras cada
reemplazo HTMX.

## R23. Memoria operativa, historial acotado y consulta de seguimiento

**Decisión**: la conversación visible vive en `messages` y es la fuente autoritativa. El checkpointer
de LangGraph guarda una instantánea acotada del historial con `thread_id = conversation_id` y se
reconcilia antes de cada turno (reconstruir si falta, recortar si está adelantado, reemplazar si
pertenece a otra conversación). El prompt recibe los últimos turnos completos con dos límites
explícitos: 8 mensajes y 6000 caracteres. La recuperación de cada pregunta se amplía con la última
pregunta confirmada para interpretar referencias, sin reutilizar respuestas como evidencia. La
evidencia se limita a 3500 tokens medidos al ingerir.

**Rationale**: `num_ctx=8192` y `num_predict=1200` dejan un margen para instrucciones (~500), historial
(~1500) y evidencia (≤3500). El historial ayuda a interpretar la pregunta, pero las citas siguen
validándose solo contra los fragmentos recuperados en el turno. Sin un segundo modelo ni un resumen no
aprobado.

**Alternativas consideradas**: enviar todo el historial (crece sin control y desplaza la evidencia);
usar un modelo auxiliar para reescribir la consulta (fuera de alcance); confiar en el checkpoint como
fuente de verdad (una pérdida o un fallo entre bases rompería la conversación).

## R24. Admisión de contexto con el tokenizador del generador

**Decisión**: antes de cada llamada al generador —incluida la reparación de citas— se mide el prompt
completo con el **tokenizador del propio modelo** y no con una estimación por bytes. El vocabulario y
las fusiones BPE se leen del GGUF ya instalado por Ollama (`~/.ollama/models`, respetando
`OLLAMA_MODELS`); no se descargan modelos. La pre-tokenización usa la expresión regular de bytes
presente en el binario de Ollama y se registran los tokens especiales del vocabulario. La plantilla
reproduce el renderizador `Qwen35Renderer` de Ollama (system + user + turno de asistente con bloque de
razonamiento vacío).

**Elementos incluidos**: instrucciones del sistema, pregunta actual, historial seleccionado, fuentes
con título, identificador y localizador, envoltorio de la plantilla, reserva de salida
(`num_predict=1200`) y un margen de 320 tokens para variaciones de plantilla o versión del
renderizador. El margen **no** cubre incertidumbre del tokenizador: la medición ya usa el tokenizador
del modelo.

**Verificación**: con `qwen3.5:9b`, un prompt mínimo dio 24 tokens en el conteo y 24 en
`prompt_eval_count`; español +1; texto técnico y Base64 quedaron 17-21 tokens **por encima** del
observado. La admisión es por tanto conservadora en la calibración. La diferencia se registra
(`admitted_tokens` frente a `observed_prompt_tokens`) y no se oculta.

**Reducción**: primero el historial más antiguo por turnos completos; después las fuentes de menor
rango, conservando `S1..Sk`. La pregunta y los textos incluidos no se recortan; el historial persistido
no se modifica.

**Si el tokenizador no está disponible** (modelo no instalado o GGUF ilegible), la ejecución falla con
`context_budget_unavailable` (503) sin estimar ni llamar al modelo. Si el contenido mínimo no cabe,
falla con `context_budget_exceeded` (500) sin llamar al modelo; ambos permiten reintento.

**Diagnóstico**: `estimate_tokens` (bytes/2,4) se conserva solo para observación. No decide la
admisión: en la regresión con Base64 aleatorio subestima (1534 frente a 1753 tokens reales) y en el
prompt real sobrestima (9670 frente a 6074). Por eso no puede presentarse como cota.

**Límites**: el conteo depende del vocabulario y del renderizador de la versión instalada; una
actualización de Ollama o del modelo exige recalibrar. La implementación de BPE de `tokenizers` puede
diferir de la de llama.cpp: en la calibración la diferencia fue a favor de la seguridad (conteo ≥
observado), pero no es una cota matemática para cualquier secuencia de bytes. Las dependencias
`gguf` (lectura del GGUF instalado) y `tokenizers` (BPE) se declaran explícitamente; no hay descargas
en tiempo de ejecución ni llamadas pagadas.

## R25. Herramienta de hallazgos: decisión estructurada, bucle acotado y presentación

**Contexto**: US5 incorpora `findings_query` sobre los hallazgos sintéticos del caso activo. El
contrato exige alcance capturado en el servidor, argumentos estrictos, conteos calculados en SQLite y
ninguna exposición de `case_id` al modelo.

**Selección de la herramienta**: se probaron dos caminos con el modelo real. Primero, `bind_tools` de
`ChatOllama` junto con `format` para la respuesta estructurada devolvió `tool_calls: []` de forma
repetida: Ollama prioriza el esquema de salida y no emite la llamada. Segundo, incluir
`tool_requests` en el esquema de respuesta tampoco fue fiable: las reglas de citas y `missing_info`
sesgaban al modelo a abstenerse aunque la pregunta fuera de conteos. La solución vigente separa la
decisión en una llamada estructurada propia (`ToolDecision`: `use_findings` + `arguments`) ejecutada
antes de la respuesta. No hay heurísticas por palabra ni preguntas codificadas: el modelo real decide
y aporta los argumentos.

**Bucle**: `retrieve → decide → tools → decide … → agent → validate`. Como máximo dos ejecuciones por
turno (`max_tool_calls=2`). Un error de argumentos se devuelve al decisor con el código
(`invalid_severity`, `invalid_qid`, …) para que corrija dentro del límite. Un fallo de base cierra el
turno como `failed/tool_failed` (500) y un timeout como `timeout/tool_timeout` (504). `origin` es
`model_requested` solo cuando hubo una decisión real del modelo; una decisión sin ejecución no
registra llamada.

**Presupuesto**: la decisión también se mide con el tokenizador del modelo (`check_prompt`) antes de
llamarlo. El prompt de respuesta incluye la definición de la herramienta, los argumentos, los
resultados y los envoltorios; se mide completo con `plan_prompt`. Con los resultados de la consulta
real, la segunda llamada admitió 817 tokens y el modelo observó 802. Los conteos se conservan siempre:
si el detalle no cupiera, se reduce lo enviado al modelo, no el resultado persistido; si no cabe una
llamada admisible se aplica `context_budget_exceeded` o `context_budget_unavailable`.

**Resultado determinista**: el `case_id` se captura en una clausura y no existe en el esquema ni en el
resultado. Los filtros usan parámetros enlazados; el filtro por CVE usa una subconsulta para que un
hallazgo con varios CVE no multiplique filas. Totales y grupos se calculan con `COUNT`/`GROUP BY` sobre
exactamente los filtros aplicados; `limit` afecta solo al detalle y `truncated` indica si se recortó.
Un caso sin hallazgos devuelve total 0 y no inventa dataset ni valores.

**Persistencia y presentación**: cada invocación se registra en `run_tool_calls` (nombre, origen,
argumentos validados, resumen, estado, error y duración). El resumen guarda total, grupos, dataset,
`truncated` e `items_count`, nunca las filas. La interfaz recalcula el detalle en modo lectura cuando
`detail=true` y lo muestra con la etiqueta «Datos educativos sintéticos», los filtros, la procedencia y
el aviso de que no es una importación de Qualys. Un total 0 se acompaña de la nota de que no demuestra
ausencia de vulnerabilidades ni riesgo bajo.

## R26. Evidencia de ejecución, límites y traza externa

**Evidencia persistida**: la página «Ver ejecución» se construye solo con los registros de la
ejecución (`runs`, `run_steps`, `run_sources`, `run_tool_calls`, citas y revisiones). No vuelve a
llamar al modelo ni ejecuta `findings_query`. Muestra estado y resultado, intento y vínculo con el
anterior, modelo con digest y parámetros, versión del prompt, pasos con origen y duración, fuentes,
herramientas con argumentos validados y resumen histórico, presupuesto medido, citas con control
automático y revisión humana por separado, error y estado de traza.

**Detalle de herramienta**: las filas de `detail=true` no se persisten. Si la página las recalcula,
las marca como «consulta actual» y aclara que los totales y grupos sí son el resultado histórico. La
vista no presenta ese recálculo como el detalle original preservado.

**Límites**: se cuentan como paso las operaciones de modelo o herramienta (decisión, generación,
reparación y llamadas de herramienta); la preparación determinista y la persistencia no consumen el
límite de 8. El máximo sigue siendo 2 llamadas a herramientas, 1 reparación, 120 s de turno y 90 s
por llamada. La decisión de herramienta consume paso y tiempo. Cada llamada recibe como máximo el
tiempo restante del turno, no un presupuesto nuevo; si el tiempo restante es menor que 90 s, un
timeout se clasifica como `run_timeout`; si se agotaron los 90 s de una llamada completa, como
`model_timeout`. El límite de pasos se mapea a `step_limit`; las llamadas adicionales a herramientas
se registran con `tool_call_limit` y no se ejecutan, preservando el comportamiento aprobado en US5.

**Traza**: se usa instrumentación manual con `langsmith.RunTree` para la ejecución raíz y las
operaciones relevantes. La instrumentación automática de LangChain se desactiva durante la llamada
al modelo para no duplicar trazas. El envío es síncrono (`auto_batch_tracing=False`) porque el modo
batch oculta los errores de red: así `submitted` significa que el SDK no observó error tras el envío y
`flush`, y una caída real produce `failed`. El `flush` se acota a 5 s. La aplicación nunca escribe
`confirmed`; la confirmación por API de lectura es T091.

**Redacción**: la traza envía solo metadatos: identificadores de ejecución, caso y prompt, modelo,
tokens, estados, claves de argumentos y conteos. No incluye pregunta, prompts, documentos del caso,
valores de argumentos, claves ni rutas locales. El filtro de logging redacta de forma recursiva claves
sensibles, rutas absolutas y trazas de pila.

**Verificación**: con datos sintéticos se observó un envío real `submitted` con traza
`01a1bee1-9f32-7561-8809-e653707d28d8` y enlace de LangSmith, sin consultar la API de lectura ni
escribir `confirmed`. Con `LANGSMITH_ENDPOINT=http://127.0.0.1:1` la consulta local se completó y la
ejecución quedó `failed`; con `LANGSMITH_TRACING=false` quedó `disabled`. La suite rápida quedó en 332
pruebas y la de integración en 24.

**Límites conocidos**: el SDK de LangSmith puede registrar errores en su propio logger; el estado se
basa en las excepciones observadas por el envío síncrono. La confirmación de que la traza existe en
LangSmith sigue siendo una operación de aceptación separada.
