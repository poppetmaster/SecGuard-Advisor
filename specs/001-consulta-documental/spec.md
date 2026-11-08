# Feature Specification: Consulta documental con evidencias, memoria por caso y hallazgos

**Feature Branch**: `001-consulta-documental` (sin rama creada: el hook de git no está instalado y el repositorio aún no tiene commits)

**Created**: 2026-11-08

**Status**: Draft

**Input**: Definición de la funcionalidad 001 entregada por el equipo: «consulta documental con evidencias, memoria por caso y herramientas de lectura de hallazgos». El texto completo del encargo está en la conversación de origen; esta especificación lo traduce a comportamiento verificable.

## Contexto y propósito del incremento

Un responsable de TI o seguridad trabaja localmente. Crea un caso con contexto educativo
sintético, aporta documentos, pregunta a un asistente documental y recibe respuestas en
español respaldadas por fuentes localizables. La conversación conserva contexto entre
preguntas. Cuando la pregunta requiere datos de hallazgos, el asistente usa una herramienta de
lectura acotada al caso. Cuando falta evidencia, lo dice.

El incremento debe producir **un recorrido completo demostrable**: caso → documentos →
pregunta → seguimiento → hallazgos → abstención → reinicio → aislamiento entre casos →
evidencia de ejecución. No se aceptan pantallas desconectadas ni respuestas predeterminadas.

Esta etapa define **qué** debe hacer el producto y **cómo** se reconoce que funciona. El diseño
técnico detallado corresponde a `/speckit.plan`.

## User Scenarios & Testing *(mandatory)*

Las prioridades ordenan los cortes de implementación, no la aceptación: el incremento se
considera completo solo cuando las seis historias se demuestran.

### User Story 1 - Crear y recuperar un caso (Priority: P1)

El usuario crea un caso con título, descripción, aplicación de IA analizada, datos tratados,
activos relevantes y restricciones conocidas. Puede dejar campos desconocidos sin que el
sistema los complete. Al reiniciar la aplicación, el caso sigue disponible.

**Why this priority**: sin un caso con contexto no hay alcance, ni evidencia que asociar, ni
respuesta que fundamentar.

**Independent Test**: crear un caso con dos campos desconocidos, reiniciar la aplicación y
reabrirlo; el contexto debe coincidir y los campos desconocidos deben seguir marcados como
desconocidos.

**Acceptance Scenarios**:

1. **Given** que no existe ningún caso, **When** el usuario crea uno con título y contexto
   educativo, **Then** el caso aparece en la lista con identificador, fecha de creación y
   todos los campos ingresados.
2. **Given** un campo de contexto sin información, **When** el usuario guarda el caso,
   **Then** el campo queda marcado como «desconocido» y el sistema no lo completa ni lo
   infiere.
3. **Given** un caso creado, **When** la aplicación se reinicia y el usuario lo reabre,
   **Then** el caso y su contexto se conservan íntegros.
4. **Given** un caso con contexto sintético, **When** el usuario lo abre, **Then** la interfaz
   lo identifica como escenario educativo y no como datos de una empresa real.
5. **Given** que el usuario intenta guardar sin título, **When** confirma, **Then** recibe un
   error comprensible y no se crea ningún caso.

---

### User Story 2 - Incorporar documentos (Priority: P1)

El usuario carga PDF textuales y Markdown, ve el estado de procesamiento y distingue qué
documentos están disponibles para consulta. Cada documento conserva procedencia, versión o
fecha cuando exista, y una ubicación identificable. Las guías públicas y las evidencias del
caso se distinguen.

**Why this priority**: sin documentos disponibles y con procedencia no hay recuperación
verificable ni citas que se puedan comprobar.

**Independent Test**: cargar un PDF textual, un Markdown, un PDF sin texto y un archivo
inválido; verificar los cuatro estados y que solo los dos primeros sean consultables.

**Acceptance Scenarios**:

1. **Given** un caso abierto, **When** el usuario carga un PDF textual, **Then** el documento
   pasa por un estado de procesamiento visible y queda «disponible» con nombre, origen,
   tamaño, fecha y número de páginas.
2. **Given** un Markdown con secciones, **When** se procesa, **Then** queda disponible y sus
   fragmentos conservan la sección de origen.
3. **Given** un PDF escaneado sin texto extraíble, **When** se procesa, **Then** queda «sin
   texto utilizable» con una explicación y no es consultable.
4. **Given** un archivo corrupto, una extensión falsa o un formato no admitido, **When** el
   usuario lo carga, **Then** se rechaza con el motivo y no se registra como disponible.
5. **Given** un documento ya cargado, **When** el usuario reimporta exactamente el mismo
   archivo al mismo caso, **Then** el contenido no se duplica y el sistema informa que ya
   existe.
6. **Given** un documento disponible, **When** el usuario carga una versión modificada,
   **Then** se registra como nueva versión con trazabilidad, la anterior queda marcada como
   superada y no se usa por defecto en las respuestas.
7. **Given** documentos de distinto origen, **When** el usuario consulta la lista, **Then** ve
   claramente cuáles son guías públicas y cuáles son evidencias del caso.
8. **Given** un documento con instrucciones incrustadas, **When** se procesa y se consulta,
   **Then** el contenido se trata como dato: no se ejecutan instrucciones ni acciones
   externas.
9. **Given** un caso seleccionado, **When** se intenta asociar un documento a otro caso,
   **Then** la operación se rechaza.

---

### User Story 3 - Preguntar y comprobar las fuentes (Priority: P1)

El usuario formula una pregunta y recibe una respuesta en español que distingue hechos
documentados, recomendaciones e información insuficiente. Cada cita permite localizar el
documento y su página o sección, y el fragmento citado respalda la afirmación asociada.

**Why this priority**: es el valor central del producto. Sin citas verificables, el asistente
no se distingue de un generador de texto plausible.

**Independent Test**: formular una pregunta cuya respuesta esté en un documento cargado y
comprobar que la cita abre el fragmento exacto que sostiene la afirmación; formular una
pregunta sin respaldo y comprobar la abstención.

**Acceptance Scenarios**:

1. **Given** documentos disponibles, **When** el usuario pregunta algo cubierto por ellos,
   **Then** recibe una respuesta en español con al menos una cita que indica documento y
   página o sección.
2. **Given** una respuesta con citas, **When** el usuario abre una cita, **Then** llega al
   fragmento citado y puede comprobar que respalda la afirmación.
3. **Given** una pregunta sin fuentes pertinentes, **When** el usuario la formula, **Then** el
   sistema declara que la información es insuficiente y no inventa una respuesta
   fundamentada.
4. **Given** una pregunta que requiere una cifra, **When** el asistente responde, **Then** la
   cifra proviene de una herramienta controlada o no se responde.
5. **Given** una respuesta del asistente, **When** el usuario la lee, **Then** está marcada
   como borrador no revisado y distingue hecho documentado, recomendación y vacío de
   información.
6. **Given** una pregunta sobre cumplimiento o certificación, **When** el asistente responde,
   **Then** no afirma cumplimiento ni emite certificación.

---

### User Story 4 - Continuar la conversación (Priority: P2)

El usuario hace una segunda pregunta que aprovecha el contexto del mismo caso. La memoria
persiste tras reiniciar y permanece separada entre casos.

**Why this priority**: una consulta aislada obliga a repetir contexto y no demuestra memoria;
pero el producto ya entrega valor sin ella.

**Independent Test**: hacer una pregunta, luego una de seguimiento que dependa de la primera,
reiniciar y comprobar que el hilo y su contexto siguen disponibles.

**Acceptance Scenarios**:

1. **Given** una conversación con una pregunta previa, **When** el usuario hace una pregunta de
   seguimiento que depende de ese contexto, **Then** la respuesta lo aprovecha sin exigir que
   se repita la información.
2. **Given** una conversación en curso, **When** la aplicación se reinicia, **Then** el
   historial del caso se conserva.
3. **Given** dos casos con conversaciones, **When** el usuario consulta uno, **Then** no
   recupera mensajes, documentos ni contexto privado del otro.
4. **Given** un caso con historial, **When** el usuario lo abre, **Then** ve pregunta,
   respuesta, citas y herramientas usadas en cada turno.

---

### User Story 5 - Consultar hallazgos mediante una herramienta (Priority: P2)

El usuario pregunta por los hallazgos de los activos del caso y obtiene filtros, conteos o
detalles calculados sobre registros persistidos. El conjunto es sintético, precargado por un
procedimiento reproducible e identificado como educativo.

**Why this priority**: demuestra el uso de herramientas con datos estructurados y el control
de alcance; el flujo documental ya funciona sin ella.

**Independent Test**: preguntar por el número de hallazgos de una severidad, recalcularlo de
forma independiente sobre los registros y comparar; luego preguntar por hallazgos de otro caso.

**Acceptance Scenarios**:

1. **Given** un caso con hallazgos sintéticos precargados, **When** el usuario pregunta cuántos
   hay de una severidad, **Then** recibe un conteo que coincide con un recálculo independiente
   sobre los registros.
2. **Given** el mismo caso, **When** el usuario pide filtrar por activo o severidad, **Then**
   recibe la lista correspondiente con sus datos originales.
3. **Given** un hallazgo, **When** el usuario pide su detalle, **Then** ve datos originales y
   procedencia, incluidos QID o CVE cuando existan.
4. **Given** dos casos, **When** el usuario pregunta por hallazgos del caso no autorizado,
   **Then** la herramienta no devuelve datos de ese caso y no se produce fuga.
5. **Given** un caso sin hallazgos, **When** el usuario pregunta, **Then** el sistema informa
   que no hay hallazgos y no inventa cifras.
6. **Given** una respuesta basada en hallazgos, **When** el usuario revisa la ejecución,
   **Then** puede distinguir que se usó una herramienta y con qué parámetros.
7. **Given** los hallazgos mostrados, **When** el usuario los lee, **Then** están identificados
   como datos educativos sintéticos y no como una importación de Qualys.

---

### User Story 6 - Verificar la ejecución (Priority: P2)

El integrante del equipo identifica las fuentes recuperadas, las herramientas utilizadas, el
modelo, la duración, el estado y los errores de una ejecución. Cuando el servicio de trazas
está configurado, existe una traza real; si no está disponible, la consulta local continúa y
conserva evidencia mínima.

**Why this priority**: sin evidencia de ejecución no se puede auditar una respuesta ni
distinguir una respuesta documental de una respuesta con herramienta.

**Independent Test**: ejecutar una consulta con y sin el servicio de trazas disponible y
comprobar en ambos casos el registro local completo y la distinción honesta de la traza.

**Acceptance Scenarios**:

1. **Given** una consulta ejecutada, **When** el usuario abre su evidencia, **Then** ve
   fuentes recuperadas, herramientas usadas, modelo, duración, estado y error si existió.
2. **Given** el servicio de trazas configurado, **When** se ejecuta una consulta, **Then**
   existe una traza real identificable y el registro local la referencia.
3. **Given** el servicio de trazas no disponible, **When** se ejecuta una consulta, **Then**
   la consulta se completa, el registro local conserva la evidencia mínima y la interfaz
   declara que la traza no está disponible.
4. **Given** un modelo que no responde dentro del límite o que está caído, **When** el usuario
   consulta, **Then** recibe un mensaje comprensible, la ejecución queda en estado de fallo o
   tiempo agotado y la conversación sigue utilizable.
5. **Given** cualquier ejecución, **When** el usuario revisa la evidencia, **Then** no aparece
   ninguna credencial.

### Edge Cases

- **PDF sin texto extraíble**: se marca «sin texto utilizable» y se explica que probablemente
  es un documento escaneado; no se consulta.
- **PDF con texto parcial**: las páginas legibles se procesan; las no legibles se reportan y no
  se presentan como contenido recuperado.
- **Extensión falsa o archivo corrupto**: se rechaza por contenido real, no por nombre.
- **Archivo sobredimensionado**: se rechaza con el límite aplicado y el motivo.
- **Markdown con enlaces o imágenes rotas**: el texto se procesa; los recursos no se resuelven
  ni se intenta acceder a rutas externas.
- **Documento con instrucciones incrustadas** («ignora las instrucciones anteriores»): se
  trata como dato; no cambia el comportamiento ni produce acciones.
- **Reimportación idéntica**: no duplica fragmentos; informa que ya existe.
- **Versión modificada**: crea versión nueva y marca la anterior como superada; las citas
  antiguas siguen siendo localizables en su versión.
- **Pregunta sin fuentes pertinentes**: se declara insuficiencia; no se cita un documento
  irrelevante solo para aparentar respaldo.
- **Pregunta ambigua**: se pide aclaración o se responde declarando la interpretación usada.
- **Pregunta que mezcla dos casos**: solo se responde con el alcance del caso activo.
- **Activo sin hallazgos**: se informa la ausencia; no se extrapola desde otro activo.
- **Hallazgo sin CVE o sin QID**: se muestra el dato disponible sin completar el faltante.
- **Filtro sin resultados**: se informa el vacío, no se devuelve una lista aproximada.
- **Reinicio durante el procesamiento**: el documento no queda «disponible»; se muestra como
  fallido o pendiente con opción de reintentar, nunca como completado.
- **Dos consultas simultáneas sobre el mismo caso**: la segunda espera o se rechaza con un
  mensaje claro; no se mezclan respuestas.
- **Corpus público no descargado**: la consulta funciona solo con evidencias del caso y
  declara la ausencia del corpus; no inventa referencias.
- **Servicio de trazas caído**: la consulta continúa; se registra la indisponibilidad.
- **Cita cuya versión fue superada**: la cita sigue resolviendo a la versión citada, no a la
  nueva.

## Requirements *(mandatory)*

### Functional Requirements

#### Caso

- **FR-001**: El sistema DEBE permitir crear un caso con título obligatorio, descripción,
  aplicación de IA analizada, datos tratados, activos relevantes y restricciones conocidas.
- **FR-002**: Los campos sin información DEBEN permanecer vacíos y marcarse como
  «desconocido»; el sistema NO DEBE inferirlos ni completarlos automáticamente.
- **FR-003**: Cada caso DEBE tener identificador único y fecha de creación visible.
- **FR-004**: El caso y su contexto DEBEN conservarse tras reiniciar la aplicación.
- **FR-005**: El usuario DEBE poder listar los casos existentes y reabrir cualquiera con su
  contexto completo.
- **FR-006**: Los casos con contexto sintético DEBEN identificarse visiblemente como
  escenarios educativos.
- **FR-007**: El sistema NO DEBE crear un caso sin título y DEBE explicar el motivo.

#### Documentos

- **FR-008**: El sistema DEBE aceptar PDF con texto y Markdown como documentos del caso.
- **FR-009**: El sistema DEBE validar extensión, contenido real y tamaño, y rechazar con
  explicación lo que no cumpla.
- **FR-010**: Cada documento DEBE conservar nombre original, origen (guía pública o evidencia
  del caso), tamaño, fecha de carga y versión o fecha declarada cuando exista.
- **FR-011**: El estado de procesamiento DEBE ser visible: pendiente, procesando, disponible,
  fallido o sin texto utilizable.
- **FR-012**: Solo los documentos «disponibles» DEBEN ser consultables.
- **FR-013**: Cuando no se extraiga texto, el documento DEBE marcarse «sin texto utilizable» y
  explicarse la causa probable.
- **FR-014**: Un fallo de procesamiento DEBE registrar un motivo comprensible y NO DEBE
  presentarse como completado.
- **FR-015**: Cada fragmento DEBE conservar página o sección y posición dentro del documento.
- **FR-016**: Reimportar contenido idéntico al mismo caso NO DEBE duplicar fragmentos y DEBE
  informar que ya existe.
- **FR-017**: Un contenido modificado DEBE registrarse como versión nueva del mismo documento,
  con trazabilidad, marcando la anterior como superada.
- **FR-018**: Guías públicas y evidencias del caso DEBEN distinguirse en la lista, las citas y
  las respuestas.
- **FR-019**: El usuario DEBE poder ver la lista de documentos del caso con estado, origen y
  procedencia.
- **FR-020**: Todo documento de origen *evidencia del caso* DEBE pertenecer a un único caso y no
  poder asociarse a un caso no seleccionado. Las fuentes públicas de referencia pertenecen al
  corpus compartido, no a un caso, y son accesibles desde cualquier caso.
- **FR-021**: El sistema NO DEBE exponer rutas del sistema de archivos; identifica el documento
  por nombre y procedencia.
- **FR-022**: El contenido de los documentos DEBE tratarse como dato no confiable; NO DEBE
  ejecutar instrucciones incrustadas ni acciones externas.
- **FR-023**: El sistema DEBE aplicar límites configurables de tipo y tamaño y explicar el
  rechazo cuando se excedan.

#### Consulta y citas

- **FR-024**: El usuario DEBE poder formular preguntas en lenguaje natural y recibir respuestas
  en español.
- **FR-025**: La respuesta DEBE distinguir hecho documentado, recomendación e información
  insuficiente.
- **FR-026**: Toda afirmación normativa DEBE incluir cita con documento y página o sección.
- **FR-027**: Una cita DEBE resolver a un fragmento existente, pertenecer a la versión citada y
  contener literalmente el texto citado; si no cumple, NO DEBE mostrarse.
- **FR-028**: El usuario DEBE poder localizar el fragmento citado.
- **FR-029**: Si no hay fuentes pertinentes, el sistema DEBE declararlo y NO DEBE inventar una
  respuesta fundamentada.
- **FR-030**: Las cifras e indicadores DEBEN provenir de herramientas controladas, no del
  modelo.
- **FR-031**: La respuesta DEBE mostrar los fragmentos recuperados que usó como evidencia.
- **FR-032**: Toda respuesta DEBE marcarse como borrador no revisado.
- **FR-033**: El sistema NO DEBE afirmar cumplimiento ni emitir certificación.
- **FR-034**: La recuperación DEBE limitarse a los documentos disponibles del caso y al corpus
  público seleccionado.
- **FR-035**: Si la pregunta queda fuera del dominio cubierto, el sistema DEBE declararlo.

#### Memoria

- **FR-036**: Una pregunta de seguimiento DEBE aprovechar el contexto del mismo caso.
- **FR-037**: La memoria DEBE persistir tras reiniciar la aplicación.
- **FR-038**: La memoria DEBE estar aislada por caso; ninguna consulta DEBE recuperar contexto
  de otro caso.
- **FR-039**: El usuario DEBE ver el historial de la conversación del caso.
- **FR-040**: El historial DEBE conservar pregunta, respuesta, citas, herramientas usadas y
  referencia a la ejecución.

#### Hallazgos

- **FR-041**: El sistema DEBE cargar un conjunto sintético pequeño mediante un procedimiento
  reproducible y marcarlo como educativo.
- **FR-042**: Cada hallazgo DEBE incluir activo, severidad original, identificadores
  disponibles (QID, CVE cuando existan), fechas y procedencia.
- **FR-043**: El usuario DEBE poder obtener filtros, conteos y detalles de hallazgos del caso.
- **FR-044**: La herramienta DEBE leer únicamente hallazgos del caso autorizado.
- **FR-045**: El modelo NO DEBE ampliar el alcance ni ejecutar consultas arbitrarias.
- **FR-046**: Toda cifra mostrada DEBE calcularse sobre registros persistidos y ser
  reproducible.
- **FR-047**: Si no hay hallazgos, el sistema DEBE informarlo y NO DEBE inventar resultados.
- **FR-048**: La ejecución DEBE indicar si se usó la herramienta y con qué parámetros.
- **FR-049**: Los hallazgos NO DEBEN presentarse como una importación de Qualys.
- **FR-050**: Los hallazgos sintéticos NO DEBEN considerarse el conjunto final de evaluación.

#### Ejecución y observabilidad

- **FR-051**: Cada consulta DEBE generar un registro con identificador, fecha, caso, pregunta,
  modelo, duración, estado y error cuando exista.
- **FR-052**: El registro DEBE incluir fuentes recuperadas y herramientas usadas.
- **FR-053**: El usuario DEBE poder abrir la evidencia de ejecución desde la conversación.
- **FR-054**: Cuando el servicio de trazas esté configurado, DEBE existir una traza real; si no
  está disponible, la consulta local DEBE continuar y conservar evidencia mínima.
- **FR-055**: El sistema NO DEBE presentar una traza simulada como real y DEBE declarar la
  indisponibilidad.
- **FR-056**: El sistema DEBE limitar duración y pasos; al excederse, DEBE informar con claridad,
  registrar el estado correspondiente y dejar la conversación utilizable.
- **FR-057**: Si el modelo no está disponible, el sistema DEBE informarlo, registrar el fallo y
  NO DEBE producir una respuesta inventada.

#### Seguridad, interfaz y límites

- **FR-058**: El alcance del caso DEBE aplicarse antes de leer documentos, hallazgos o memoria. El
  identificador autorizado lo determina el servidor y NO DEBE exponerse al modelo como argumento
  ni en el resultado de una herramienta.
- **FR-059**: El sistema DEBE validar archivos y prevenir el acceso a rutas no autorizadas.
- **FR-060**: El sistema NO DEBE ejecutar remediaciones ni acciones externas.
- **FR-061**: Los estados y errores DEBEN mostrarse en español y ser comprensibles para un
  usuario no técnico.
- **FR-062**: Los recursos de interfaz DEBEN servirse localmente.
- **FR-063**: Las credenciales NO DEBEN aparecer en la interfaz, las respuestas, los registros,
  las trazas ni el repositorio.
- **FR-064**: El producto NO DEBE atribuir aprobación al docente ni presentar las pruebas
  sintéticas como validación empresarial.
- **FR-065**: El sistema DEBE permitir registrar una revisión humana del respaldo semántico de una
  cita con estado pendiente, respaldada o no respaldada, autor, fecha y observación cuando
  corresponda. El autor proviene de una identidad local declarada en la configuración
  (`SECGUARD_REVIEWER_NAME`). Sin esa identidad, NO DEBE permitirse guardar la revisión. Esta
  configuración NO es autenticación. El sistema NO DEBE inferir la revisión ni declararla
  automáticamente.
- **FR-066**: La ejecución DEBE distinguir el control automático de cita —existencia, localización
  y coincidencia literal— de la revisión semántica humana. Una cita válida NO acredita por sí sola
  que el fragmento respalde la afirmación.
- **FR-067**: Reintentar un turno fallido DEBE conservar la pregunta original, registrar un intento
  nuevo y NO DEBE duplicar mensajes ni efectos. El reintento DEBE exigir que la ejecución esté en
  `failed`, `timeout` o `interrupted` y que no exista una respuesta persistida para ese intento.
- **FR-068**: DEBE existir una sola consulta activa por caso y una sola generación local a la vez en
  toda la aplicación. Una segunda consulta del mismo caso DEBE rechazarse con un mensaje claro; una
  consulta de otro caso DEBE esperar de forma acotada o rechazarse, sin mezclar respuestas. La
  ejecución activa DEBE liberarse al terminar, fallar, agotar el tiempo o reiniciarse la aplicación.
  La desconexión del cliente NO DEBE liberar la ejecución antes de que la generación termine.

#### Controles de cita y evidencia

El control automático prueba tres cosas: que el fragmento existe, que pertenece a la versión
citada y que el texto citado aparece literalmente en él. Es determinista y se ejecuta en cada
respuesta.

El respaldo semántico —que el fragmento sostenga la afirmación— es un juicio humano. Se registra
con estado pendiente, respaldada o no respaldada, autor, fecha y observación cuando corresponda. El
autor proviene de `SECGUARD_REVIEWER_NAME`; sin esa identidad configurada no se guarda la revisión,
y la configuración no se presenta como autenticación. No se declara cumplido por el sistema. Una
cita que pasa el control automático no acredita fundamentación.

La revisión humana del respaldo semántico NO incluye adjudicación de prioridades P1–P4 ni
aprobación de informes: esas capacidades pertenecen a incrementos posteriores.

### Key Entities

- **Caso**: unidad de alcance. Título, descripción, aplicación de IA, datos tratados, activos,
  restricciones, marca de contexto sintético, fecha de creación.
- **Activo**: elemento del caso sobre el que existen hallazgos; puede no tener hallazgos.
- **Documento**: archivo asociado a un caso. Nombre, origen, tamaño, fecha de carga, versión
  declarada, estado de procesamiento, procedencia.
- **Versión de documento**: contenido concreto de un documento en un momento; permite
  trazabilidad cuando el archivo cambia y conserva la validez de citas anteriores.
- **Fragmento**: porción recuperable de una versión, con página o sección y posición.
- **Conversación**: hilo de mensajes de un caso. En este incremento, uno por caso.
- **Mensaje**: pregunta o respuesta, con sus citas, herramientas y referencia a la ejecución.
- **Cita**: vínculo entre una afirmación y un fragmento concreto de una versión de documento.
- **Ejecución**: registro de una consulta con modelo, duración, estado, error, fuentes y
  herramientas.
- **Hallazgo sintético**: registro educativo de un activo con severidad original,
  identificadores y procedencia.
- **Fuente pública**: documento oficial del corpus de referencia, con versión, licencia y
  procedencia. Es compartida por todos los casos y no pertenece a ninguno.

## Datos de entrada y salidas

### Entradas

| Flujo | Entrada | Obligatoria | Observación |
|---|---|---|---|
| Caso | Título | Sí | Sin título no se crea el caso |
| Caso | Descripción, aplicación de IA, datos tratados, activos, restricciones | No | Vacío se marca «desconocido» |
| Documento | Archivo PDF textual o Markdown | Sí | Se valida contenido real y tamaño |
| Documento | Origen: guía pública o evidencia del caso | Sí | Determina cómo se cita |
| Documento | Versión o fecha declarada | No | Se conserva cuando existe |
| Consulta | Pregunta en lenguaje natural | Sí | Debe pertenecer a un caso abierto |
| Hallazgos | Filtros: activo, severidad, identificador | No | Vacío devuelve el conjunto del caso |
| Ejecución | Selección de una ejecución del historial | Sí | Solo del caso abierto |

### Salidas

| Flujo | Salida | Contenido mínimo |
|---|---|---|
| Caso | Caso creado o reabierto | Identificador, contexto, marca de sintético |
| Documento | Estado de procesamiento | Estado, motivo si falla, procedencia, ubicación |
| Consulta | Respuesta en español | Hechos, recomendaciones, insuficiencia, citas, marca de borrador |
| Consulta | Evidencia visible | Fragmentos recuperados y su procedencia |
| Memoria | Historial del caso | Turnos con pregunta, respuesta, citas y herramientas |
| Hallazgos | Conteo, lista o detalle | Cifras recalculables, datos originales, procedencia |
| Ejecución | Registro | Identificador, modelo, duración, estado, fuentes, herramientas, error |
| Ejecución | Referencia de traza | Identificador real o declaración de indisponibilidad |

## Success Criteria *(mandatory)*

Los siguientes valores son **umbrales de aceptación**, no resultados medidos. Ninguna métrica de
esta sección se presenta como obtenida.

### Measurable Outcomes

- **SC-001**: Un usuario que conoce el producto completa el recorrido de aceptación completo
  —caso, dos documentos, cuatro preguntas, reinicio y segundo caso— en 15 minutos o menos.
- **SC-002**: El 100 % de las citas mostradas resuelven a un fragmento existente e indican
  documento y página o sección.
- **SC-003**: En una revisión humana de 10 afirmaciones normativas tomadas de las respuestas, el
  100 % tiene una cita válida y la persona revisora registra que el fragmento respalda la
  afirmación. La compuerta automática solo prueba existencia, localización y coincidencia literal
  de la cita; no acredita respaldo semántico.
- **SC-004**: El 100 % de los conteos de hallazgos mostrados coincide con un recálculo
  independiente sobre los mismos registros.
- **SC-005**: En una prueba con dos casos, cero consultas del caso A devuelven documentos,
  mensajes o hallazgos del caso B.
- **SC-006**: El 100 % de los casos y conversaciones se recuperan íntegros tras reiniciar la
  aplicación, en tres intentos consecutivos.
- **SC-007**: Reimportar un archivo idéntico al mismo caso incrementa en cero el número de
  fragmentos consultables.
- **SC-008**: El 100 % de las consultas genera un registro de ejecución con estado y duración.
- **SC-009**: Cuando el servicio de trazas no está disponible, el 100 % de las consultas se
  completa localmente y declara la indisponibilidad.
- **SC-010**: Un integrante del equipo identifica si se usó una herramienta en 5 segundos o
  menos desde la vista de ejecución.
- **SC-011**: El 100 % de los archivos rechazados o fallidos muestra un motivo comprensible y
  ninguno queda marcado como disponible.
- **SC-012**: El 100 % de las preguntas sin fuente pertinente produce una declaración de
  insuficiencia y ninguna cita inventada.
- **SC-013**: Reintentar un turno fallido no incrementa el número de mensajes de usuario ni crea
  una segunda respuesta para el mismo intento; cada intento queda identificado.
- **SC-014**: En una prueba de dos consultas simultáneas sobre el mismo caso, solo una se ejecuta y
  la otra recibe un rechazo explícito; no se mezclan respuestas.
- **SC-015**: En una prueba con dos casos distintos y dos consultas simultáneas, solo una generación
  se ejecuta a la vez; la otra espera de forma acotada o recibe un rechazo explícito, sin mezclar
  respuestas ni liberar la ejecución activa por desconexión del cliente.

## Assumptions

- Un solo usuario local, sin autenticación, en una sola máquina. El alcance por caso se aplica
  en el servidor aunque no exista login.
- La interfaz y las respuestas están en español; el código y los identificadores, en inglés.
- Una conversación por caso en este incremento. No hay múltiples hilos ni borrado de historial.
- El corpus público se incorpora mediante un procedimiento reproducible del equipo, no por
  carga del usuario. Lo que el usuario carga son evidencias del caso. El corpus es compartido y
  accesible desde cualquier caso; no pertenece a ninguno.
- El corpus del incremento 1 son las cuatro fuentes acordadas; NIST SP 1301 queda para el
  incremento 2.
- Los hallazgos sintéticos se precargan para el caso de demostración. Un caso nuevo parte sin
  hallazgos.
- Solo se admiten PDF con capa de texto y Markdown. No hay OCR ni reconocimiento de imágenes.
- No se edita el contenido de un documento: un archivo modificado crea una versión nueva.
- Por defecto se recupera la versión vigente de cada documento; las versiones superadas siguen
  siendo localizables para citas antiguas.
- Los límites de duración, pasos y tamaño de archivo son configurables; sus valores concretos
  se fijan en el plan.
- Toda respuesta es un borrador. Este incremento no incluye aprobación de informes ni
  adjudicación de prioridades P1–P4. La revisión del respaldo semántico de una cita es la única
  revisión humana incluida.
- Reintentar un turno fallido reutiliza la pregunta original y crea un intento nuevo. Un turno
  exitoso no se reintenta. El reintento exige que no exista respuesta persistida para ese intento.
- Solo hay una consulta activa por caso y una sola generación local a la vez. Una segunda consulta
  del mismo caso se rechaza; una de otro caso espera de forma acotada o se rechaza. La ejecución
  activa se libera al terminar, fallar, agotar el tiempo o reiniciarse la aplicación, nunca por
  desconexión del cliente.
- Tres casos distintos: (1) una pregunta nueva después de un turno exitoso es un turno nuevo,
  aunque el texto se repita; (2) un reintento reutiliza la pregunta de una ejecución fallida sin
  respuesta; (3) un envío duplicado mientras hay una ejecución activa se rechaza sin crear mensaje.
  Este incremento no implementa idempotencia por clave de solicitud.
- La identidad del revisor proviene de `SECGUARD_REVIEWER_NAME`. Es una declaración local, no una
  autenticación. Sin valor configurado no se guarda ninguna revisión semántica.
- La aplicación es mono-organización. No hay multiempresa ni aislamiento entre organizaciones.

## Dependencias y pendientes

- **Constitución vigente**: v1.0.1, que prevalece sobre esta especificación.
- **Corpus**: las cuatro fuentes del incremento 1 deben descargarse y verificarse; la descarga
  sigue pendiente y no se declara realizada.
- **Modelos locales**: generador y embeddings instalados y verificados.
- **Servicio de trazas**: configurado y con traza real verificada; su indisponibilidad no
  bloquea la consulta local.
- **Formato CSV de Qualys**: pendiente y fuera de esta funcionalidad.
- **Política P1–P4**: pendiente y fuera de esta funcionalidad.
- **Destino GitHub**: pendiente; no hay badges de CI verificables todavía.
- **Versión de Python**: fijada en 3.14.6 por la constitución.

## Fuera de alcance

- Adaptador completo de CSV de Qualys.
- Formulario de adjudicación de prioridades P1–P4.
- Aprobación final y exportación completa de informes.
- Clasificador y reentrenamiento.
- Agente especialista adicional, clustering, Isolation Forest y reranker.
- Streaming de respuestas.
- API pagada del producto.
- Publicación, operación multiempresa y despliegue distribuido.
- OCR de documentos escaneados.
- Edición del contenido de documentos cargados.

## Correspondencia con la rúbrica

Esta tabla orienta la evidencia; **no acredita cumplimiento**. La acreditación se determina al
evaluar el producto, no por declararlo en una especificación.

| Criterio | Evidencia que esta funcionalidad aporta | Cobertura |
|---|---|---|
| R.6.1 Cr1 — formulación del problema y contexto | Caso con contexto organizacional sintético y restricciones explícitas | Parcial |
| R.6.1 Cr2 — justificación del modelo | No cubierto aquí; corresponde a la comparación de generadores | No cubierto |
| R.6.1 Cr3 — integración del modelo al caso | Consulta documental, memoria y herramienta sobre un caso real de uso | Parcial |
| R.6.1 Cr4 — interpretación de la evaluación | No cubierto aquí; corresponde a la evaluación del incremento | No cubierto |
| R.6.2 Cr5 — selección de tareas automatizables | Ingesta, recuperación, consulta de hallazgos y registro de ejecución automatizados | Parcial |
| R.6.2 Cr6 — eficiencia demostrada | Duración registrada por ejecución; falta la comparación antes/después | Parcial |
| R.6.2 Cr7 — riesgos éticos | Datos sintéticos rotulados, documentos no confiables, sin remediaciones | Parcial |
| R.6.2 Cr8 — documentación replicable | Recorrido de aceptación reproducible y evidencia de ejecución | Parcial |
| R.7.1 Cr1–Cr3 — pipeline de datos | Ingesta con validación, estados, deduplicación y procedencia | Parcial |
| R.7.2 Cr4–Cr6 — MLOps | No cubierto aquí; corresponde al incremento 3 | No cubierto |
| RA1 / RA2 — comunicación | Fuera del software; se evidencia con informe y sustentación | No cubierto |
