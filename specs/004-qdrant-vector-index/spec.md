# Feature Specification: Migración del índice documental a Qdrant

**Feature Branch**: `004-qdrant-vector-index` (no creada en este paso)

**Created**: 2026-11-11

**Status**: Borrador planificable — ratificación comunicada por el responsable registrada. Plan,
diseño y tareas generados, y análisis de consistencia documental aplicado sobre los artefactos.
Ninguna tarea ejecutada, ningún comportamiento implementado y ninguna aceptación declarada. No
habilita implementación por sí solo.

**Input**: User description: «Migración del índice documental a Qdrant»: sustituir Chroma como
backend de recuperación documental, conservando SQLite como fuente de verdad, documentos,
versiones, fragmentos, procedencia, citas, corpus público, aislamiento por caso, memoria,
conversación e importación/consulta de vulnerabilidades de 002.

## Contexto y distinciones

Esta funcionalidad cambia el **backend de recuperación documental**. No cambia el alcance del
producto, el modelo de embeddings, el generador, la memoria, la semántica de `findings_query` ni la
política P1–P4.

Estado de gobierno:

- La constitución 1.3.0 registra la **ratificación comunicada por Edwin Perez L.** el 2026-11-11
  para Qdrant, el generador por API posterior y las acciones externas posteriores.
- No constan los acuerdos de Cristian Quebrada y Ruben Dario Sabogal, acta, firma ni aprobación
  académica. No se inventan.
- La especificación puede revisarse y planificarse; la implementación sigue sujeta a las compuertas
  de planificación y aceptación.
- La funcionalidad 003 permanece suspendida. 004 no implementa P1–P4 ni las retoma.

**Decisión de simplificación de 004:** el índice Qdrant se crea **desde cero** a partir de los
fragmentos persistidos. No se migran ni exportan vectores de Chroma, no hay escritura dual, no hay
selección permanente entre backends, no se exige comparación ejecutable Chroma/Qdrant y no hay
retorno a Chroma. Los archivos y datos Chroma existentes no se borran en 004.

**Hallazgo de capacidad relevante:** los vectores actuales **no están persistidos en SQLite**. La
tabla de fragmentos conserva texto, metadatos, modelo y dimensión de embeddings, estado de índice y
localizador; el vector vive en el índice derivado. Por tanto, la reconstrucción limpia **regenera**
los vectores con el mismo modelo y dimensión local vigentes. No se asume que se puedan copiar desde
SQLite ni se exportan desde Chroma. Esta decisión no cambia el modelo de embeddings de 004.

**Decisiones técnicas diferidas al plan:** versiones de servidor y cliente, topología de
colecciones y filtros, esquema de payload e índices, configuración de Docker Compose, backups de
Qdrant y estrategia de reconstrucción. La especificación define el comportamiento y los criterios de
aceptación, no esas decisiones.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reconstruir el índice desde la fuente de verdad (Priority: P1)

Una persona con acceso local inicia la reconstrucción del índice documental en Qdrant a partir de
los documentos, versiones y fragmentos ya persistidos. No vuelve a subir documentos ni depende de
que el índice anterior esté disponible. Al terminar, el índice contiene exactamente los fragmentos
persistidos que corresponde indexar, con sus identificadores y metadatos.

**Why this priority**: sin una reconstrucción confiable no existe un índice Qdrant válido ni una
migración defendible. Es el núcleo del cambio de backend.

**Independent Test**: preparar un caso ficticio con documentos y fragmentos conocidos, ejecutar la
reconstrucción sobre un Qdrant de prueba y comprobar que el número de fragmentos indexados coincide
con los fragmentos persistidos, que los identificadores son los mismos y que no hay duplicados.

**Acceptance Scenarios**:

1. **Given** un almacenamiento separado con documentos y fragmentos persistidos, **When** se
   ejecuta la reconstrucción inicial, **Then** Qdrant contiene una entrada por fragmento indexable,
   con el mismo `chunk_id`, documento, versión, procedencia y localizador de SQLite.
2. **Given** una reconstrucción ya completada, **When** se ejecuta de nuevo, **Then** no se crean
   duplicados y el conteo de fragmentos indexados no aumenta.
3. **Given** una reconstrucción interrumpida, **When** se reintenta, **Then** el índice no se
   presenta como completo hasta que la reconstrucción termine o se reanude de forma verificable.
4. **Given** un fragmento sin metadatos suficientes o con una dimensión incompatible, **When** se
   reconstruye, **Then** se reporta como no indexable y no se mezcla con el índice válido.
5. **Given** un índice Qdrant con entradas que no existen en SQLite, **When** se compara con la
   fuente de verdad, **Then** la diferencia se reporta y no se presenta como índice consistente.

---

### User Story 2 - Consultar documentos con el nuevo backend (Priority: P1)

Una persona formula una pregunta en un caso y recibe respuestas con fragmentos recuperados desde
Qdrant. La consulta busca únicamente en el corpus público permitido y en los documentos disponibles
del caso actual; no mezcla otros casos ni registros Qualys.

**Why this priority**: la migración solo tiene valor si la consulta documental sigue funcionando y
mantiene el aislamiento y la evidencia.

**Independent Test**: con dos casos ficticios con documentos distintos y un corpus público de
prueba, formular una pregunta en cada caso y comprobar que los resultados del caso A no aparecen en
el caso B y que el corpus público sí puede aparecer en ambos.

**Acceptance Scenarios**:

1. **Given** un caso con documentos disponibles y un corpus público indexado, **When** se consulta,
   **Then** los resultados provienen solo de esas dos fuentes permitidas.
2. **Given** dos casos con documentos distintos, **When** se consulta uno de ellos, **Then** no se
   recupera ningún fragmento privado del otro caso.
3. **Given** un documento con versión vigente y una versión superada, **When** se hace una nueva
   búsqueda, **Then** se recupera la versión vigente y la superada no reaparece por defecto.
4. **Given** una cita histórica que apunta a una versión superada, **When** el usuario abre la cita,
   **Then** se resuelve el fragmento persistido de esa versión y se conserva su localizador.
5. **Given** un registro importado de Qualys, **When** se consulta el índice documental, **Then** el
   registro no aparece como fragmento, documento ni cita del RAG.

---

### User Story 3 - Mantener citas, procedencia y aislamiento (Priority: P2)

Una persona revisa una respuesta y abre una cita. La cita resuelve al mismo fragmento persistido,
con documento, versión, página o sección y localizador; el control automático de citas sigue
funcionando igual que antes. El cambio de backend no convierte una cita válida en una cita
semánticamente respaldada.

**Why this priority**: la recuperación sin citas verificables no es aceptable para el producto,
aunque el backend sea más rápido o moderno.

**Independent Test**: recuperar un fragmento conocido desde Qdrant, abrir su cita y comprobar que el
`chunk_id`, la versión, el localizador y el texto coinciden con SQLite; comprobar además que una
cita de otro caso o de una versión inexistente se rechaza.

**Acceptance Scenarios**:

1. **Given** un fragmento indexado, **When** se resuelve su cita, **Then** el documento, la versión,
   la página o sección y el localizador coinciden con el registro persistido.
2. **Given** una cita con `chunk_id` inexistente o de otra versión, **When** se valida, **Then** se
   rechaza y no se muestra como evidencia.
3. **Given** una cita de un caso distinto, **When** se valida, **Then** se rechaza por alcance.
4. **Given** una cita que pasa el control automático, **When** se muestra, **Then** se distingue de
   la revisión semántica humana y no se presenta como respaldo verificado.
5. **Given** una recuperación vacía, **When** se responde, **Then** se conserva la abstención y no se
   inventan citas.

---

### User Story 4 - Reiniciar y recuperar la disponibilidad (Priority: P2)

Una persona reinicia el servicio Qdrant o la aplicación y comprueba que el índice persiste y que las
consultas siguen funcionando. Si Qdrant no está disponible, la aplicación informa el fallo de forma
explícita y no cambia en silencio a Chroma.

**Why this priority**: un índice que se pierde al reiniciar o que cae sin aviso no es un backend
aceptable para la demostración ni para la operación local.

**Independent Test**: indexar un caso ficticio, reiniciar el servicio Qdrant conservando su volumen,
volver a consultar y comprobar que los fragmentos siguen disponibles. Repetir con Qdrant detenido y
comprobar el error explícito y la ausencia de fallback.

**Acceptance Scenarios**:

1. **Given** un Qdrant local persistente con índice construido, **When** se reinicia el servicio,
   **Then** el índice sigue disponible y las consultas devuelven los mismos fragmentos indexados.
2. **Given** Qdrant inaccesible, **When** se intenta consultar, **Then** la aplicación informa un
   error comprensible y no usa Chroma de forma silenciosa.
3. **Given** una configuración incompatible de Qdrant, **When** arranca o consulta, **Then** falla
   de forma explícita, sin marcar el índice como válido ni borrar datos.
4. **Given** una ejecución que usa Qdrant, **When** se consulta su evidencia, **Then** se identifica
   Qdrant, su versión y el índice utilizado.

---

### User Story 5 - Detectar fallos y recuperar el índice Qdrant (Priority: P3)

Una persona responsable detecta que el índice Qdrant está incompleto, interrumpido o inaccesible,
reconstruye desde SQLite y verifica integridad y completitud antes de declararlo listo. No hay
retorno a Chroma ni selección de backend.

**Why this priority**: la recuperación ante fallos de Qdrant es necesaria, pero el producto ya no
mantiene un segundo backend documental.

**Independent Test**: corromper o interrumpir un índice Qdrant de prueba, ejecutar la recuperación,
comprobar que el índice parcial no se presenta como listo y que la reconstrucción desde SQLite
restaura los fragmentos esperados.

**Acceptance Scenarios**:

1. **Given** un índice Qdrant parcial o interrumpido, **When** la persona lo inspecciona, **Then** el
   sistema no lo presenta como completo y explica qué falta.
2. **Given** un índice Qdrant incompleto, **When** se reconstruye desde SQLite, **Then** se restauran
   los fragmentos esperados sin duplicados y con procedencia.
3. **Given** un fallo de Qdrant, **When** se intenta consultar, **Then** el error es explícito y no
   se usa Chroma como fallback.
4. **Given** una recuperación completada, **When** se valida, **Then** la evidencia identifica Qdrant
   y el índice reconstruido; los archivos Chroma permanecen intactos y sin uso.

---

### User Story 6 - Cargar el primer documento y consultar un alcance vacío (Priority: P2)

Una persona crea un caso y carga su primer documento. No ejecuta una reconstrucción completa. Si el
caso todavía no tiene documentos privados, puede consultar el corpus público; si el caso debería
tener documentos indexados pero no tiene alias, ve un error de disponibilidad, no una respuesta de
“sin evidencia”.

**Why this priority**: el flujo normal de alta no puede depender de mantenimiento manual, y un
índice ausente no debe confundirse con un alcance vacío.

**Independent Test**: crear un caso sin documentos, consultar el corpus público y comprobar que
responde; cargar el primer documento y comprobar que el alias se publica solo después de validar;
provocar un fallo de embedding y comprobar que no se publica alias nuevo; reintentar y comprobar que
no hay duplicados.

**Acceptance Scenarios**:

1. **Given** un caso nuevo sin documentos privados y un corpus público indexado, **When** se
   consulta, **Then** se recuperan resultados públicos y no se bloquea por falta de alias privado.
2. **Given** un caso nuevo y su primer documento válido, **When** la ingesta termina, **Then** se
   crea la generación/alias del caso sin reconstrucción completa.
3. **Given** un fallo de extracción, embedding o escritura Qdrant en el primer documento, **When**
   la ingesta termina, **Then** la versión queda no disponible, no se publica alias nuevo y el
   corpus público sigue consultable.
4. **Given** un reintento del primer documento, **When** se ejecuta, **Then** no se duplican
   fragmentos y el alias se publica solo si la validación es completa.
5. **Given** un caso con documentos disponibles en SQLite pero sin alias, **When** se consulta,
   **Then** se devuelve un error de índice de caso no disponible, no “sin evidencia”.
6. **Given** un corpus público con documentos en SQLite pero sin alias público, **When** se
   consulta, **Then** se devuelve un error de índice público no disponible.
7. **Given** un corpus público no configurado o vacío, **When** se consulta un caso con documentos,
   **Then** el alcance público se omite y la consulta del caso puede continuar.

---

### User Story 7 - Aislar instancias y coordinar mantenimiento (Priority: P3)

Una persona opera almacenamiento habitual, presentación y pruebas sobre el mismo servidor Qdrant sin
que compartan documentos. La aplicación y el comando de reconstrucción coordinados por un lock de
archivo entre procesos; uno rechaza al otro cuando corresponde.

**Why this priority**: sin namespace, dos instancias con el mismo `case_id` colisionan; sin lock
entre procesos, una reconstrucción y una ingesta pueden escribir a la vez.

**Independent Test**: crear dos instancias con el mismo `case_id` y documentos distintos, y
comprobar que no comparten alias ni resultados. Iniciar una reconstrucción en un proceso y una
ingesta en otro, comprobar el rechazo; matar el proceso y comprobar que el lock se libera.

**Acceptance Scenarios**:

1. **Given** dos instancias con el mismo `case_id` y contenidos distintos, **When** se consulta cada
   una, **Then** no comparten documentos privados, aliases públicos ni resultados.
2. **Given** un `SECGUARD_INSTANCE_ID` distinto del marcador de storage, **When** arranca o
   reconstruye, **Then** falla cerrado sin escribir ni cambiar aliases.
3. **Given** una reconstrucción con el lock de instancia, **When** se intenta una ingesta, **Then**
   se rechaza con un error explícito y no se escribe a medias.
4. **Given** una ingesta con el lock, **When** se intenta reconstruir, **Then** se rechaza con un
   error explícito, sin cola ni espera indefinida.
5. **Given** un proceso interrumpido con el lock, **When** se reintenta, **Then** el sistema
   operativo liberó el lock y el índice anterior sigue activo.

---

### Edge Cases

- Dos casos con documentos distintos: ninguna consulta de un caso recupera documentos privados del
  otro.
- Corpus público compartido: puede aparecer en consultas de ambos casos, con su procedencia.
- Versión superada: no reaparece en búsquedas nuevas; una cita histórica sigue resolviendo a su
  versión y localizador.
- Reconstrucción repetida: no duplica entradas ni incrementa el conteo.
- Reconstrucción interrumpida: no se marca como completa; el reintento no deja entradas parciales
  como válidas.
- Reconstrucción parcial fallida: se reportan fragmentos no indexados y el índice no se presenta
  como consistente.
- Fragmento faltante en SQLite pero presente en el índice: se reporta y se excluye de la consulta.
- Fragmento presente en SQLite pero ausente en el índice: se reporta como faltante y se reconstruye.
- Fragmento con dimensión o modelo incompatible: no se mezcla; se reporta y se regenera con el
  mismo modelo o se excluye del índice, sin declarar éxito.
- Diferencia entre conteo del índice y conteo de la fuente de verdad: no se declara éxito.
- Qdrant caído: error explícito, sin fallback silencioso a Chroma.
- Reinicio de Qdrant con persistencia: el índice sigue disponible.
- Configuración incompatible: fallo explícito, sin borrar datos.
- Documentos añadidos antes de una reconstrucción: se incluyen desde SQLite en la siguiente
  reconstrucción; no se promete actualización de Chroma.
- Archivos o datos Chroma existentes: no se usan, no se comparan y no se borran en 004.
- No hay selección permanente de backend ni retorno a Chroma.
- Registros Qualys: nunca se indexan como documentos ni se recuperan como citas.
- Consulta sin resultados: se declara ausencia de evidencia; no se inventa una cita.
- Pregunta de seguimiento: conserva la memoria y el aislamiento del caso.
- Espacio de almacenamiento separado: las pruebas no tocan la instancia del usuario.
- Datos privados en fixtures: prohibidos; solo públicos o ficticios.
- Dos instancias con el mismo `case_id`: no comparten documentos, aliases ni resultados.
- Instancia copiada a otra ruta: el fingerprint de ruta canónica no coincide; falla cerrado.
- `SECGUARD_INSTANCE_ID` ausente o inválido: error de configuración; no se usa un ID generado.
- Primer documento con extracción/embedding/Qdrant fallido: versión no disponible, sin alias nuevo.
- Caso sin documentos privados: consulta pública normal; no error por alias privado ausente.
- Caso con documentos esperados pero sin alias: error de índice de caso, no “sin evidencia”.
- Público con documentos esperados pero sin alias: error de índice público.
- Público no configurado o vacío: se omite; el caso puede continuar.
- Reconstrucción e ingesta concurrentes: lock de archivo por instancia; rechazo explícito e
  identificación de la operación que lo posee.
- Proceso interrumpido con lock: el sistema operativo lo libera; el registro de propietario queda
  obsoleto y se ignora; el alias anterior permanece.
- Registro de propietario residual con el lock libre: no demuestra actividad; el estado se resuelve
  por el bloqueo real, no por los metadatos.
- Namespace incompatible: no se escribe, no se cambia alias, no se usa Chroma.

## Requirements *(mandatory)*

### Functional Requirements

**Alcance y conservación**

- **FR-001**: El sistema MUST conservar SQLite como fuente de verdad de documentos, versiones,
  fragmentos, procedencia, citas y metadatos.
- **FR-002**: El sistema MUST tratar el índice Qdrant como derivado y reconstruible; eliminarlo NO
  DEBE perder datos de negocio ni procedencia.
- **FR-003**: El sistema MUST conservar los identificadores de fragmento y la correspondencia con
  SQLite; una reconstrucción NO DEBE exigir volver a subir documentos.
- **FR-004**: El sistema MUST conservar las capacidades verificadas de 001 y 002: consulta
  documental, citas, memoria, aislamiento, importación Qualys, snapshots y `findings_query`.
- **FR-005**: El sistema MUST NOT indexar el CSV Qualys, sus filas, resultados o agregados como
  documentos, fragmentos o citas del RAG.
- **FR-006**: El sistema MUST NOT cambiar el modelo de embeddings, la dimensión, la memoria ni la
  semántica de `findings_query` durante 004.
- **FR-007**: El sistema MUST NOT presentar Qdrant como implementado hasta que exista una aceptación
  observada contra el servidor objetivo.

**Reconstrucción**

- **FR-008**: El sistema MUST permitir una reconstrucción inicial del índice desde los fragmentos
  persistidos y sus metadatos.
- **FR-009**: La reconstrucción MUST conservar `chunk_id`, documento, versión, origen, localizador y
  metadatos de página o sección.
- **FR-010**: La reconstrucción MUST ser idempotente: repetirla no debe crear duplicados ni aumentar
  el conteo de fragmentos indexados.
- **FR-011**: El sistema MUST registrar y exponer cinco estados observables de una reconstrucción:
  `not_started` (no iniciada), `in_progress` (en curso), `completed` (completada), `partial`
  (parcial) y `failed` (fallida). `not_started` se deriva de la ausencia de reporte y de que el lock
  no esté tomado por una reconstrucción; `in_progress` se deriva de un lock tomado por un proceso vivo
  cuyo registro de propietario declara la operación `rebuild`; los otros tres se leen del último
  reporte terminal. Un lock ocupado por una ingesta NO DEBE interpretarse como reconstrucción en
  curso; un lock activo NO DEBE interpretarse como éxito y la ausencia de reporte NO DEBE
  interpretarse como fallo.
- **FR-012**: Una reconstrucción interrumpida MUST NOT presentarse como completada; el reintento
  MUST ser seguro y no duplicar entradas válidas.
- **FR-013**: Una reconstrucción parcial fallida MUST informar cuántos fragmentos quedaron sin
  indexar y por qué; no debe declarar consistencia.
- **FR-014**: Si un fragmento persistido no tiene texto, metadatos o dimensión compatibles, el
  sistema MUST reportarlo y MUST NOT mezclarlo con el índice válido.
- **FR-015**: Si el índice contiene entradas que no existen en SQLite, el sistema MUST reportar la
  diferencia y MUST NOT presentar el índice como consistente.
- **FR-016**: El sistema MUST NOT asumir que los vectores están persistidos en SQLite y MUST NOT
  exportarlos desde Chroma. La reconstrucción MUST regenerar los vectores con el mismo modelo y
  dimensión locales vigentes.
- **FR-017**: La reconstrucción NO DEBE borrar ni modificar los documentos, fragmentos o versiones
  de SQLite.

**Recuperación, versiones y citas**

- **FR-018**: Las consultas MUST recuperar únicamente el corpus público permitido y los documentos
  disponibles del caso actual.
- **FR-019**: Las consultas MUST respetar el aislamiento de documentos privados entre casos.
- **FR-020**: Las consultas MUST recuperar la versión vigente de cada documento para búsquedas
  nuevas.
- **FR-021**: Las versiones superadas MUST NOT reaparecer por defecto en búsquedas nuevas.
- **FR-022**: Una cita histórica MUST seguir resolviendo al fragmento y la versión citados, aunque
  la versión esté superada.
- **FR-023**: Las citas MUST conservar documento, versión, página o sección, localizador y
  procedencia; el control automático de citas MUST seguir verificando existencia, versión y texto
  literal.
- **FR-024**: Una recuperación vacía MUST declararse como ausencia de evidencia; no debe inventar
  citas.
- **FR-025**: El sistema MUST evaluar funcionalmente pertinencia, cobertura, citas y aislamiento
  mediante un conjunto reproducible de preguntas y evidencia esperada. El conjunto DEBE incluir
  preguntas del corpus público, de dos casos ficticios con documentos distintos y de ausencia de
  evidencia. NO se exige comparación ejecutable con Chroma ni igualdad de orden.
- **FR-026**: El umbral de recuperación MUST calibrarse con la métrica y configuración de Qdrant; no
  se copia un valor de Chroma sin comprobar su significado. El valor 0.35 vigente para Chroma NO DEBE
  conservarse como predeterminado validado ni heredarse en silencio: el valor aplicado MUST provenir
  de la calibración con Qdrant y quedar registrado en la configuración. La calibración y la
  evaluación final MUST usar conjuntos separados, y los criterios de aceptación MUST fijarse antes de
  ejecutar la evaluación final.
- **FR-027**: Los umbrales propuestos y los resultados observados MUST distinguirse en la evidencia;
  no se inventan métricas.

**Despliegue, persistencia y fallos**

- **FR-028**: El despliegue objetivo MUST ser un servidor Qdrant local persistente, preferiblemente
  mediante Docker Compose, con acceso limitado al equipo local.
- **FR-029**: El modo embebido MUST reservarse para pruebas o una alternativa documentada; su uso NO
  sustituye la aceptación contra el servidor objetivo.
- **FR-030**: El sistema MUST informar de forma comprensible si Qdrant está disponible, inaccesible o
  mal configurado, mediante errores clasificados con mensaje en español: `qdrant_unavailable` (503),
  `case_index_unavailable` (503), `public_index_unavailable` (503),
  `instance_namespace_mismatch` (503), `reconstruction_in_progress` (409) e
  `ingestion_in_progress` (409). Cada error MUST conservar su propio código en la respuesta al
  usuario y en la evidencia registrada, y MUST NOT degradarse a `internal_error`.
- **FR-031**: Si Qdrant falla, el sistema MUST NOT cambiar en silencio a Chroma ni a otro backend.
- **FR-032**: Un reinicio del servicio Qdrant con persistencia MUST conservar el índice y permitir
  consultas posteriores.
- **FR-033**: Una configuración incompatible MUST fallar de forma explícita y NO DEBE borrar datos ni
  marcar el índice como válido.
- **FR-034**: El sistema MUST registrar Qdrant, su versión y el índice o colección utilizado en cada
  ejecución, sin exponer secretos.

**Sustitución y retirada de Chroma**

- **FR-035**: Tras la sustitución, Qdrant MUST ser el único backend de recuperación documental. NO
  se mantiene selección permanente entre Chroma y Qdrant.
- **FR-036**: La evidencia de ejecución MUST identificar Qdrant y el índice utilizado.
- **FR-037**: La validación de integridad y completitud de Qdrant MUST completarse antes de declarar
  el índice listo.
- **FR-038**: El sistema MUST NOT migrar ni exportar vectores de Chroma, ni implementar escritura
  dual o comparación obligatoria Chroma/Qdrant.
- **FR-039**: Un fallo de Qdrant MUST recuperarse reconstruyendo desde SQLite; NO DEBE existir
  retorno a Chroma como capacidad del producto.
- **FR-040**: Los archivos, colecciones y datos Chroma existentes NO DEBEN borrarse en 004. La
  retirada de su código no autoriza su limpieza física.

**Privacidad, datos y pruebas**

- **FR-041**: Las pruebas iniciales MUST usar corpus público o fixtures ficticios.
- **FR-042**: La especificación, capturas, logs y servicios externos MUST NOT contener datos
  privados, filas Qualys, IP, activos ni títulos privados.
- **FR-043**: Toda prueba o reconstrucción inicial MUST ejecutarse en almacenamiento separado antes
  de actuar sobre una instancia del usuario.
- **FR-044**: El sistema MUST conservar todos los datos existentes; una reconstrucción NO DEBE
  borrar documentos, versiones, fragmentos, conversaciones, snapshots ni evidencia.
- **FR-045**: El sistema MUST NOT enviar datos del caso a servicios externos durante 004.

**Interfaz y observabilidad**

- **FR-046**: El estado y el avance de una reconstrucción MUST informarse mediante el comando de
  reconstrucción, su reporte local (estado, alcance, generación, alias, conteos, faltantes y causa) y
  una consulta de estado de solo lectura (`uv run python scripts/rebuild_qdrant.py --status`). Esa
  consulta MUST distinguir reconstrucción no iniciada, ingesta en curso, reconstrucción en curso y
  último resultado terminal completado, parcial o fallido; con ausencia total de estado registrado
  MUST devolver `not_started` y finalizar con éxito. Si el reporte terminal es ilegible, la consulta
  MUST finalizar con salida 2, informar por `stderr` y devolver `state: null` y `last_terminal: null`
  con un error explícito (`status_report_unreadable`), sin presentarlo como `not_started`, sin inventar
  un estado terminal y sin borrar, sobrescribir ni reparar el reporte. La misma forma de error MUST
  aplicarse a `instance_configuration_invalid` cuando la configuración de instancia falta o es inválida,
  y a `lock_unreadable` cuando el archivo de lock existe pero no puede leerse; en ambos casos NO DEBE
  devolverse `not_started`, NO DEBE afirmarse que no existe una operación activa y NO DEBE crearse
  marcador, lock, directorio ni otro archivo. Esos comandos son la interfaz operativa de la reconstrucción en
  004 y NO se exige una pantalla web de administración. La interfaz web MUST
  presentar de forma comprensible los errores de índice y de disponibilidad de los flujos existentes.
- **FR-047**: La evidencia de ejecución MUST conservar la información existente de fuentes, citas,
  herramientas, pasos y duración, añadiendo el backend sin eliminar campos previos.
- **FR-048**: La interfaz MUST NOT presentar el cambio de backend como una capacidad nueva del
  producto ni como una mejora de calidad no medida.
- **FR-049**: El sistema MUST conservar la navegación, memoria, conversación y consulta de
  vulnerabilidades existentes.
- **FR-050**: El sistema MUST NOT añadir autenticación, despliegue público ni control multiusuario
  en 004.
- **FR-051**: Toda instancia MUST tener un `SECGUARD_INSTANCE_ID` estable, opaco y validado. El
  namespace MUST aplicarse a colecciones públicas y privadas, aliases, generaciones, reportes y
  locks.
- **FR-052**: El ID de instancia NO DEBE generarse en cada arranque ni contener rutas privadas. Un
  marcador persistente MUST registrar el ID y un fingerprint derivado de la ruta canónica del
  almacenamiento y del ID de instancia; el fingerprint NO DEBE depender del contenido, tamaño, fecha
  de modificación ni hash de los archivos SQLite, de los documentos ni del propio marcador. Si el
  marcador no coincide, o si falta y ya existen colecciones o alias de esa instancia en el servidor,
  el sistema MUST fallar cerrado con `instance_namespace_mismatch`, sin escribir, sin cambiar alias y
  sin adoptar el namespace de forma silenciosa.
- **FR-053**: El primer documento válido de un caso sin índice MUST crear la generación/alias del
  caso sin exigir una reconstrucción completa. El alias MUST publicarse solo después de validar la
  versión.
- **FR-054**: Un fallo de extracción, embedding o escritura Qdrant en el primer documento MUST dejar
  la versión no disponible y NO DEBE publicar alias nuevo. El reintento MUST evitar duplicados y
  mantener coherencia con SQLite.
- **FR-055**: Un caso sin documentos privados MUST poder consultar el corpus público. Un caso con
  documentos esperados pero sin alias MUST devolver un error de índice, no “sin evidencia”. Un
  corpus público esperado pero sin alias MUST devolver un error de índice público. Qdrant
  inaccesible MUST devolver un error explícito.
- **FR-056**: La ingesta y la reconstrucción MUST compartir un lock de archivo exclusivo por
  instancia, válido entre procesos. Si una está activa, la otra MUST rechazarse de forma explícita;
  el lock MUST liberarse al terminar o morir el proceso.
- **FR-057**: Dos instancias con el mismo `case_id` y documentos distintos MUST NOT compartir
  documentos privados, aliases públicos ni resultados.
- **FR-058**: El namespace y el lock MUST resolverse con configuración persistente y archivos
  locales; NO se crea una tabla SQLite nueva.
- **FR-059**: El lock de instancia MUST identificar la operación (`ingestion` o `rebuild`) y el
  intento que lo posee mediante un registro asociado al bloqueo real. El registro MUST considerarse
  válido solo mientras el lock está tomado por un proceso vivo; con el lock libre, cualquier registro
  residual MUST ignorarse y MUST NOT presentar actividad. El sistema MUST distinguir ingesta activa,
  reconstrucción activa y último resultado terminal, sin tabla SQLite nueva ni pantalla
  administrativa. La consulta de estado MUST ser de solo lectura: NO DEBE iniciar reconstrucciones,
  generar embeddings, crear colecciones, registrar instancias, escribir archivos ni cambiar alias.

### Key Entities

- **Fragmento persistido**: unidad de texto y metadatos en SQLite; fuente de verdad para reconstruir
  el índice. Conserva `chunk_id`, documento, versión, página o sección, localizador, texto, modelo y
  dimensión.
- **Entrada de índice**: representación derivada de un fragmento en Qdrant; conserva el
  `chunk_id` y los metadatos necesarios para resolver la cita. No es fuente de verdad.
- **Reconstrucción de índice**: operación que crea o actualiza el índice desde los fragmentos
  persistidos; tiene estado, conteos, errores y evidencia.
- **Instancia lógica**: namespace estable (`SECGUARD_INSTANCE_ID`) que separa almacenamiento
  habitual, presentación y pruebas en un mismo servidor Qdrant. No se genera por arranque.
- **Marcador de instancia**: archivo persistente con el ID y un fingerprint de la ruta canónica del
  almacenamiento y del ID; detecta copias o
  namespaces incompatibles sin exponer rutas legibles.
- **Lock de instancia**: archivo exclusivo compartido por la aplicación y el comando de
  reconstrucción; coordina procesos distintos y registra la operación y el intento que lo posee.
- **Índice Qdrant activo**: índice derivado utilizado para la recuperación documental; registra
  instancia, versión, alias y generación en la evidencia.
- **Resultado de recuperación**: fragmento recuperado con procedencia, puntuación y referencia a la
  versión; puede resolverse a una cita.
- **Cita**: vínculo entre una afirmación y un fragmento de una versión concreta; conserva
  localizador y estado de control automático.
- **Conjunto de evaluación funcional**: preguntas y evidencia esperada, usado para evaluar
  pertinencia, cobertura, citas y aislamiento sin comparación obligatoria con Chroma.
- **Evidencia de índice**: registro de Qdrant, versión, colección, validación, conteos y fallos.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de los fragmentos indexables de un caso ficticio puede reconstruirse desde
  SQLite sin volver a subir documentos.
- **SC-002**: Una segunda reconstrucción produce cero duplicados y no incrementa el conteo de
  fragmentos indexados.
- **SC-003**: Una reconstrucción interrumpida no se presenta como completada; el reintento no deja
  entradas parciales como válidas.
- **SC-004**: El 100% de las citas mostradas resuelve al fragmento y versión persistidos, con
  localizador y procedencia.
- **SC-005**: En una prueba con dos casos, cero consultas del caso A recuperan documentos privados
  del caso B.
- **SC-006**: El corpus público puede recuperarse en ambos casos con su procedencia, sin mezclarse
  con documentos privados.
- **SC-007**: Una versión superada no reaparece en búsquedas nuevas; una cita histórica sigue
  resolviendo a su versión.
- **SC-008**: El 0% de los registros Qualys aparece como documento, fragmento o cita del índice
  documental.
- **SC-009**: Con Qdrant inaccesible, el 100% de las consultas informa el fallo y el 0% cambia en
  silencio a Chroma.
- **SC-010**: Tras reiniciar Qdrant con persistencia, el 100% de los fragmentos indexados sigue
  disponible.
- **SC-011**: Una configuración incompatible falla de forma explícita y no borra datos.
- **SC-012**: La evaluación funcional reproducible reporta pertinencia, cobertura, citas y
  aislamiento con evidencia esperada; no exige comparación con Chroma.
- **SC-013**: El umbral de recuperación se calibra con la configuración de Qdrant; no se declara
  equivalente por copiar el valor de Chroma.
- **SC-014**: Las suites de 001 y 002 siguen pasando.
- **SC-015**: El 100% de las ejecuciones identifica Qdrant, su versión y el índice utilizado.
- **SC-016**: Qdrant es el único backend documental después de la sustitución; no hay selección
  dual, escritura dual ni retorno a Chroma.
- **SC-017**: Las pruebas iniciales usan datos públicos o ficticios y no tocan la instancia del
  usuario.
- **SC-018**: Los archivos y datos Chroma existentes no se borran en 004; las citas históricas siguen
  resolviendo desde SQLite.
- **SC-019**: No se presentan métricas de mejora no medidas ni se declara Qdrant implementado antes
  de la aceptación.
- **SC-020**: Dos instancias con el mismo `case_id` y documentos distintos no comparten documentos
  privados, aliases públicos ni resultados.
- **SC-021**: El primer documento válido publica el alias del caso solo tras validar; un fallo no
  publica alias y el reintento no duplica fragmentos.
- **SC-022**: Un caso sin documentos privados consulta el corpus público; un caso con documentos
  esperados sin alias devuelve un error de índice, no “sin evidencia”.
- **SC-023**: Ingesta y reconstrucción se rechazan mutuamente mediante un lock de archivo entre
  procesos; tras matar el proceso, el lock se libera y el alias anterior sigue activo.
- **SC-024**: Un namespace incompatible falla cerrado, no escribe y no cambia aliases.

## Assumptions

- La constitución 1.3.0 registra la **ratificación comunicada por el responsable** el 2026-11-11.
  No constan los acuerdos de Cristian Quebrada y Ruben Dario Sabogal, acta, firma ni aprobación
  académica. La especificación puede planificarse; la implementación sigue sujeta a las compuertas.
- El despliegue objetivo es Qdrant en servidor local persistente, preferiblemente con Docker Compose;
  el modo embebido es para pruebas o alternativa documentada.
- SQLite sigue siendo la fuente de verdad. Qdrant es el único backend documental objetivo; Chroma
  deja de usarse y sus archivos no se borran en 004.
- El modelo de embeddings actual y su dimensión no cambian en 004.
- Los vectores no están en SQLite; la reconstrucción los regenera con el mismo modelo local. No se
  exportan vectores de Chroma.
- No existe atomicidad entre Qdrant y SQLite. SQLite decide la disponibilidad de documentos y
  versiones; si falla el commit en SQLite después de escribir puntos o publicar un alias, el
  reintento converge sin duplicados y las consultas excluyen las versiones no disponibles.
- No hay migración de vectores, escritura dual, selección permanente de backend, comparación
  obligatoria Chroma/Qdrant ni retorno a Chroma.
- Las pruebas iniciales usan corpus público o fixtures ficticios y almacenamiento separado.
- Cada instancia usa un `SECGUARD_INSTANCE_ID` estable y distinto; el marcador de instancia y su
  fingerprint de ruta canónica detectan copias o namespaces incompatibles.
- El primer documento de un caso se indexa de forma incremental; la reconstrucción completa es una
  operación de mantenimiento para documentos existentes.
- Un caso sin documentos privados no requiere alias privado; el corpus público puede responder.
- La coordinación ingesta/reconstrucción usa un lock de archivo por instancia, no una cola ni una
  tabla nueva.
- 003 sigue suspendida y no forma parte de 004.
- Las versiones, topología de colecciones, payload, Docker Compose y backups se deciden en
  `/speckit.plan`; no son requisitos previos para esta especificación.
- No se asume autenticación, multiusuario ni despliegue público.

## Dependencies

- Constitución 1.3.0 con ratificación del responsable registrada; acuerdos del equipo no constan.
- Capacidades y contratos verificados de 001 y 002.
- Servidor Qdrant local persistente y Docker Compose, a definir en el plan.
- Modelo de embeddings local actual y fragmentos persistidos en SQLite.
- Conjunto reproducible de preguntas y fixtures públicos o ficticios.
- Almacenamiento separado para pruebas y reconstrucción inicial.

## Out of Scope

- Cambiar el modelo de embeddings o su dimensión.
- Migrar o exportar vectores de Chroma.
- Mantener escritura dual, selección permanente de backend o retorno a Chroma.
- Exigir comparación ejecutable Chroma/Qdrant.
- Integrar Claude, DeepSeek u otro generador API.
- Introducir Telegram, correo o mesa de ayuda.
- Implementar P1–P4 o retomar 003.
- Indexar el CSV Qualys o sus resultados.
- Cambiar la memoria, la conversación o la semántica de `findings_query`.
- Añadir autenticación, multiusuario o despliegue público.
- Eliminar archivos o datos Chroma durante 004.

## Decisiones técnicas diferidas al plan

| Decisión | Qué debe resolver el plan | No bloquea esta especificación |
|---|---|---|
| Versiones | Versión de servidor y cliente Qdrant, compatibilidad y fijación | La especificación fija comportamiento, no versiones |
| Topología | Servidor local, Docker Compose, volumen, acceso y límites | El objetivo servidor persistente está fijado |
| Colecciones y filtros | Una colección por caso/pública o filtros por payload | Debe conservar aislamiento y corpus compartido |
| Payload e índices | Campos, tipos, índices de payload y correspondencia con SQLite | Debe conservar `chunk_id`, versión, procedencia y localizador |
| Reconstrucción | Regenerar embeddings desde SQLite con el mismo modelo; sin exportar vectores de Chroma | Los vectores no están en SQLite; no se asume reutilización |
| Umbral | Métrica, configuración y calibración de Qdrant | No se copia el valor de Chroma |
| Evaluación | Preguntas, evidencia esperada, métricas y criterios | No se exige comparación ni orden exacto con Chroma |
| Backups y recuperación | Snapshots/backups de Qdrant y reconstrucción desde SQLite | No hay retorno a Chroma |
| Evidencia | Campos de Qdrant, versión, índice y validación | Debe permitir saber qué índice atendió cada ejecución |
| Concurrencia | Reconstrucción, consulta y bloqueo durante la sustitución | No debe dejar índice parcial como válido |
| Configuración | Variables, secretos y acceso local | No se exponen secretos ni se habilita despliegue público |

## Gobierno y ratificación

- **Constitución aplicable:** 1.3.0, con ratificación comunicada por Edwin Perez L. el 2026-11-11.
- **Acuerdos del equipo:** no constan los de Cristian Quebrada y Ruben Dario Sabogal; no se
  inventan acta, firma, fecha de reunión ni aprobación académica.
- **Estado de esta especificación:** borrador planificable; no es una autorización de implementación.
- **Efecto:** la planificación de 004 se ejecuta por la ratificación del responsable. La
  implementación sigue sujeta a las compuertas de planificación y aceptación.
- **003:** permanece suspendida; su política P1–P4 no está aprobada.
- **Decisiones de negocio pendientes:** no se solicita de nuevo la confirmación de Edwin. Queda
  registrada, sin inventar, la evidencia de acuerdo de Cristian Quebrada y Ruben Dario Sabogal. Las
  versiones, topología, payload, Docker Compose y backups son decisiones técnicas del plan.
