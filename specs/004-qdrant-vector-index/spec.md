# Feature Specification: Migración del índice documental a Qdrant

**Feature Branch**: `004-qdrant-vector-index` (no creada en este paso)

**Created**: 2026-11-11

**Status**: Draft — condicionado a la ratificación de la enmienda constitucional 1.2.0 y a las
decisiones técnicas de `/speckit.plan`. No habilita implementación por sí solo.

**Input**: User description: «Migración del índice documental a Qdrant»: sustituir Chroma como
backend de recuperación documental, conservando SQLite como fuente de verdad, documentos,
versiones, fragmentos, procedencia, citas, corpus público, aislamiento por caso, memoria,
conversación e importación/consulta de vulnerabilidades de 002.

## Contexto y distinciones

Esta funcionalidad cambia el **backend de recuperación documental**. No cambia el alcance del
producto, el modelo de embeddings, el generador, la memoria, la semántica de `findings_query` ni la
política P1–P4.

Estado de gobierno:

- La constitución 1.2.0 está **preparada** y la autorización del responsable Edwin Perez L. está
  registrada.
- El acuerdo de Cristian Quebrada y Ruben Dario Sabogal **no consta**. La enmienda no se presenta
  como ratificada.
- Esta especificación es un **borrador condicionado**: puede revisarse y completarse, pero no
  implementarse hasta que la enmienda 1.2.0 sea ratificada conforme a la gobernanza vigente.
- La funcionalidad 003 permanece suspendida. 004 no implementa P1–P4 ni las retoma.

**Hallazgo de capacidad relevante:** los vectores actuales **no están persistidos en SQLite**. La
tabla de fragmentos conserva texto, metadatos, modelo y dimensión de embeddings, estado de índice y
localizador; el vector vive en el índice derivado. Por tanto, la reconstrucción inicial no puede
asumir que los vectores se pueden copiar desde SQLite. Debe regenerarlos con el mismo modelo y
dimensión, o reutilizar una exportación verificada del índice anterior si el plan la habilita. Esta
decisión no cambia el modelo de embeddings de 004.

**Decisiones técnicas diferidas al plan:** versiones de servidor y cliente, topología de
colecciones y filtros, esquema de payload e índices, configuración de Docker Compose, backups,
snapshots, ventana de reversión y estrategia de reconstrucción. La especificación define el
comportamiento y los criterios de aceptación, no esas decisiones.

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
   el backend utilizado.

---

### User Story 5 - Detectar fallos y volver explícitamente al backend anterior (Priority: P3)

Una persona responsable detecta que la migración no cumple los criterios, selecciona explícitamente
Chroma y restaura el comportamiento anterior. El sistema conserva la evidencia de qué backend
atendió cada ejecución y advierte si el índice anterior quedó desfasado por documentos añadidos
durante la transición.

**Why this priority**: la migración debe ser reversible y observable; una vuelta silenciosa o una
promesa de índice actualizado sin estarlo destruiría la confianza.

**Independent Test**: construir Qdrant, validar una consulta, seleccionar Chroma y comprobar que la
consulta vuelve a usar el índice anterior; añadir un documento durante la transición y verificar que
el sistema advierte que Chroma no lo contiene.

**Acceptance Scenarios**:

1. **Given** dos backends disponibles y una selección explícita, **When** se ejecuta una consulta,
   **Then** la evidencia indica el backend seleccionado.
2. **Given** una validación fallida de Qdrant, **When** la persona vuelve a Chroma, **Then** las
   consultas usan Chroma y no se presenta Qdrant como aceptado.
3. **Given** documentos añadidos durante la transición, **When** se vuelve a Chroma, **Then** el
   sistema advierte que el índice anterior puede estar desfasado y no promete actualización
   automática.
4. **Given** una aceptación inicial de Qdrant, **When** termina la validación, **Then** Chroma no se
   elimina como parte de esa aceptación.

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
- Fragmento con dimensión o modelo incompatible: no se mezcla; se reporta y se regenera o se
  excluye según la decisión del plan.
- Diferencia entre conteo del índice y conteo de la fuente de verdad: no se declara éxito.
- Qdrant caído: error explícito, sin fallback silencioso a Chroma.
- Reinicio de Qdrant con persistencia: el índice sigue disponible.
- Configuración incompatible: fallo explícito, sin borrar datos.
- Documentos añadidos durante la transición: el retorno a Chroma advierte posible desfase.
- Índice anterior con documentos que ya no están disponibles: no se presentan como evidencia.
- Registros Qualys: nunca se indexan como documentos ni se recuperan como citas.
- Consulta sin resultados: se declara ausencia de evidencia; no se inventa una cita.
- Pregunta de seguimiento: conserva la memoria y el aislamiento del caso.
- Espacio de almacenamiento separado: las pruebas no tocan la instancia del usuario.
- Datos privados en fixtures: prohibidos; solo públicos o ficticios.

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
- **FR-011**: El sistema MUST registrar el estado de una reconstrucción: no iniciada, en curso,
  completada, parcial o fallida.
- **FR-012**: Una reconstrucción interrumpida MUST NOT presentarse como completada; el reintento
  MUST ser seguro y no duplicar entradas válidas.
- **FR-013**: Una reconstrucción parcial fallida MUST informar cuántos fragmentos quedaron sin
  indexar y por qué; no debe declarar consistencia.
- **FR-014**: Si un fragmento persistido no tiene texto, metadatos o dimensión compatibles, el
  sistema MUST reportarlo y MUST NOT mezclarlo con el índice válido.
- **FR-015**: Si el índice contiene entradas que no existen en SQLite, el sistema MUST reportar la
  diferencia y MUST NOT presentar el índice como consistente.
- **FR-016**: El sistema MUST NOT asumir que los vectores están persistidos en SQLite. Si no se
  reutiliza una exportación verificada del índice anterior, MUST regenerar los vectores con el mismo
  modelo y dimensión actuales.
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
- **FR-025**: El sistema MUST comparar pertinencia, cobertura, citas y aislamiento mediante un
  conjunto reproducible de preguntas. El conjunto DEBE incluir preguntas del corpus público, de dos
  casos ficticios con documentos distintos y de ausencia de evidencia, con fragmentos relevantes
  conocidos. NO se exige igualdad exacta del orden de resultados con Chroma.
- **FR-026**: El umbral de recuperación MUST validarse con la métrica y configuración de Qdrant; el
  valor de Chroma NO debe copiarse sin comprobar su equivalencia.
- **FR-027**: Los umbrales propuestos y los resultados observados MUST distinguirse en la evidencia;
  no se inventan métricas.

**Despliegue, persistencia y fallos**

- **FR-028**: El despliegue objetivo MUST ser un servidor Qdrant local persistente, preferiblemente
  mediante Docker Compose, con acceso limitado al equipo local.
- **FR-029**: El modo embebido MUST reservarse para pruebas o una alternativa documentada; su uso NO
  sustituye la aceptación contra el servidor objetivo.
- **FR-030**: El sistema MUST informar de forma comprensible si Qdrant está disponible, inaccesible o
  mal configurado.
- **FR-031**: Si Qdrant falla, el sistema MUST NOT cambiar en silencio a Chroma ni a otro backend.
- **FR-032**: Un reinicio del servicio Qdrant con persistencia MUST conservar el índice y permitir
  consultas posteriores.
- **FR-033**: Una configuración incompatible MUST fallar de forma explícita y NO DEBE borrar datos ni
  marcar el índice como válido.
- **FR-034**: El sistema MUST registrar qué backend atendió cada ejecución y con qué identificador
  de índice o colección, sin exponer secretos.

**Transición y reversión**

- **FR-035**: El sistema MUST permitir seleccionar explícitamente el backend activo entre Chroma y
  Qdrant durante la transición.
- **FR-036**: La evidencia de ejecución MUST identificar el backend utilizado.
- **FR-037**: La validación de Qdrant MUST completarse antes de declarar la migración aceptada.
- **FR-038**: El sistema MUST permitir volver explícitamente a Chroma si la validación falla.
- **FR-039**: El retorno a Chroma MUST advertir si el índice anterior quedó desfasado por documentos
  añadidos durante la transición; NO DEBE prometer un índice actualizado que no lo esté.
- **FR-040**: Chroma MUST conservarse durante la transición y NO DEBE eliminarse como parte de la
  aceptación inicial de 004.

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

- **FR-046**: La interfaz MUST informar el estado de la reconstrucción y los errores de forma
  comprensible.
- **FR-047**: La evidencia de ejecución MUST conservar la información existente de fuentes, citas,
  herramientas, pasos y duración, añadiendo el backend sin eliminar campos previos.
- **FR-048**: La interfaz MUST NOT presentar el cambio de backend como una capacidad nueva del
  producto ni como una mejora de calidad no medida.
- **FR-049**: El sistema MUST conservar la navegación, memoria, conversación y consulta de
  vulnerabilidades existentes.
- **FR-050**: El sistema MUST NOT añadir autenticación, despliegue público ni control multiusuario
  en 004.

### Key Entities

- **Fragmento persistido**: unidad de texto y metadatos en SQLite; fuente de verdad para reconstruir
  el índice. Conserva `chunk_id`, documento, versión, página o sección, localizador, texto, modelo y
  dimensión.
- **Entrada de índice**: representación derivada de un fragmento en Qdrant; conserva el
  `chunk_id` y los metadatos necesarios para resolver la cita. No es fuente de verdad.
- **Reconstrucción de índice**: operación que crea o actualiza el índice desde los fragmentos
  persistidos; tiene estado, conteos, errores y evidencia.
- **Backend vectorial seleccionado**: elección explícita entre Chroma y Qdrant durante la
  transición, registrada en la ejecución.
- **Resultado de recuperación**: fragmento recuperado con procedencia, puntuación y referencia a la
  versión; puede resolverse a una cita.
- **Cita**: vínculo entre una afirmación y un fragmento de una versión concreta; conserva
  localizador y estado de control automático.
- **Conjunto de comparación**: preguntas y fragmentos relevantes conocidos, usado para comparar
  pertinencia, cobertura, citas y aislamiento entre Chroma y Qdrant.
- **Evidencia de transición**: registro de backend, índice, validación, fallos y reversión.

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
- **SC-012**: La comparación reproducible reporta pertinencia, cobertura, citas y aislamiento sin
  exigir igualdad exacta de orden con Chroma.
- **SC-013**: El umbral de recuperación se valida con la configuración de Qdrant; no se declara
  equivalente por copiar el valor de Chroma.
- **SC-014**: Las suites de 001 y 002 siguen pasando.
- **SC-015**: El 100% de las ejecuciones de la transición identifica el backend utilizado.
- **SC-016**: La aceptación inicial conserva Chroma y permite un retorno explícito sin borrar el
  índice anterior.
- **SC-017**: Las pruebas iniciales usan datos públicos o ficticios y no tocan la instancia del
  usuario.
- **SC-018**: No se presentan métricas de mejora no medidas ni se declara Qdrant implementado antes
  de la aceptación.

## Assumptions

- La enmienda constitucional 1.2.0 está preparada y autorizada por el responsable, pero **no
  ratificada** por Cristian Quebrada y Ruben Dario Sabogal. Esta especificación es un borrador
  condicionado.
- El despliegue objetivo es Qdrant en servidor local persistente, preferiblemente con Docker Compose;
  el modo embebido es para pruebas o alternativa documentada.
- SQLite sigue siendo la fuente de verdad; Chroma se conserva durante la transición.
- El modelo de embeddings actual y su dimensión no cambian en 004.
- Los vectores no están en SQLite; la reconstrucción regenera embeddings salvo que el plan habilite
  una exportación verificada del índice anterior.
- Las pruebas iniciales usan corpus público o fixtures ficticios y almacenamiento separado.
- 003 sigue suspendida y no forma parte de 004.
- Las versiones, topología de colecciones, payload, Docker Compose y backups se deciden en
  `/speckit.plan`; no son requisitos previos para esta especificación.
- No se asume autenticación, multiusuario ni despliegue público.

## Dependencies

- Ratificación de la constitución 1.2.0 conforme a la gobernanza vigente para habilitar la
  implementación.
- Capacidades y contratos verificados de 001 y 002.
- Servidor Qdrant local persistente y Docker Compose, a definir en el plan.
- Modelo de embeddings local actual y fragmentos persistidos en SQLite.
- Conjunto reproducible de preguntas y fixtures públicos o ficticios.
- Almacenamiento separado para pruebas y reconstrucción inicial.

## Out of Scope

- Cambiar el modelo de embeddings o su dimensión.
- Integrar Claude, DeepSeek u otro generador API.
- Introducir Telegram, correo o mesa de ayuda.
- Implementar P1–P4 o retomar 003.
- Indexar el CSV Qualys o sus resultados.
- Cambiar la memoria, la conversación o la semántica de `findings_query`.
- Añadir autenticación, multiusuario o despliegue público.
- Eliminar Chroma como parte de la aceptación inicial.

## Decisiones técnicas diferidas al plan

| Decisión | Qué debe resolver el plan | No bloquea esta especificación |
|---|---|---|
| Versiones | Versión de servidor y cliente Qdrant, compatibilidad y fijación | La especificación fija comportamiento, no versiones |
| Topología | Servidor local, Docker Compose, volumen, acceso y límites | El objetivo servidor persistente está fijado |
| Colecciones y filtros | Una colección por caso/pública o filtros por payload | Debe conservar aislamiento y corpus compartido |
| Payload e índices | Campos, tipos, índices de payload y correspondencia con SQLite | Debe conservar `chunk_id`, versión, procedencia y localizador |
| Reconstrucción | Exportar vectores verificados o regenerarlos con el mismo modelo | Los vectores no están en SQLite; no se asume reutilización |
| Umbral | Métrica, configuración y calibración de Qdrant | No se copia el valor de Chroma |
| Comparación | Preguntas, fragmentos relevantes, métricas y criterios | No se exige orden exacto con Chroma |
| Backups y reversión | Snapshots, retención, ventana y retorno a Chroma | Chroma se conserva; no se borra en la aceptación inicial |
| Evidencia | Campos de backend, índice y validación | Debe permitir saber qué backend atendió cada ejecución |
| Concurrencia | Reconstrucción, consulta y bloqueo durante transición | No debe dejar índice parcial como válido |
| Configuración | Variables, secretos y acceso local | No se exponen secretos ni se habilita despliegue público |

## Gobierno y ratificación

- **Constitución aplicable:** 1.2.0, preparada y autorizada por Edwin Perez L., pero pendiente de
  ratificación por Cristian Quebrada y Ruben Dario Sabogal.
- **Estado de esta especificación:** borrador revisable; no es una autorización de implementación.
- **Efecto de la ratificación pendiente:** no se inicia `/speckit.plan` ni `/speckit.implement` como
  trabajo normativo hasta que la enmienda sea ratificada. La especificación puede revisarse y
  completarse mientras tanto.
- **003:** permanece suspendida; su política P1–P4 no está aprobada.
- **Decisiones de negocio pendientes:** la ratificación de 1.2.0 y la confirmación de que 004 sigue
  siendo una migración de backend sin cambio de embeddings. Las versiones, topología, payload,
  Docker Compose y backups son decisiones técnicas del plan, no requisitos de negocio de esta
  especificación.
