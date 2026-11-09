# Feature Specification: Priorización y revisión de vulnerabilidades

**Feature Branch**: `003-priorizacion-revision-vulnerabilidades` (no creada en este paso)

**Created**: 2026-11-09

**Status**: Draft — propuesta de política revisada; aprobación pendiente

**Input**: User description: "Inicia la funcionalidad 003 de SecGuard Advisor: «Priorización y revisión
de vulnerabilidades». Primera parte del incremento 3: definir la política P1–P4 y especificar la
revisión explícita que permitirá obtener etiquetas elegibles para el futuro clasificador."

## Contexto y distinciones

Esta funcionalidad permite que una persona revise un registro de una instantánea Qualys confirmada y
registre una **clase operacional P1–P4** con justificación y procedencia. La política operacional
P1–P4 **todavía no está aprobada**; esta especificación no la presenta como acordada.

La clase operacional P1–P4 se distingue explícitamente de:

- la severidad original del proveedor;
- la escala de presentación 1 Informativa, 2 Baja, 3 Media, 4 Alta y 5 Crítica;
- la bandera conjunta de explotabilidad y malware;
- el estado `Active`, `New`, `Re-Opened`, `Fixed` o desconocido;
- la aprobación del texto de una respuesta;
- la revisión del respaldo semántico de una cita.

La aprobación de un informe o de una cita **no** crea ni modifica una clase de prioridad. Guardar una
revisión **no** dispara entrenamiento, reentrenamiento ni activación de modelos.

La **prioridad sugerida por la regla**, la **prioridad adjudicada por la persona** y la **elegibilidad
para entrenamiento** son estados distintos. Una sugerencia no es una adjudicación; una adjudicación no
es automáticamente elegible; y una discrepancia entre ambas se conserva sin borrar ninguna.

En esta especificación, «P1–P4» designa exclusivamente la clase operacional. La prioridad de entrega
de las historias se indica como «historia 1», «historia 2», «historia 3» y «historia 4»; no se usan
las etiquetas P1–P4 para ordenar el trabajo de implementación.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Revisar y adjudicar la prioridad de un registro confirmado (Prioridad de entrega: 1 — MVP)

Una persona con identidad declarada abre un registro de una instantánea confirmada, consulta sus
datos y procedencia, distingue los valores conocidos de los desconocidos o indeterminados, y registra
una clase operacional P1–P4 con justificación, política aplicada y fecha. También puede registrar
«información insuficiente» o «desacuerdo» sin inventar una clase.

**Why this priority**: es el núcleo de la funcionalidad y la única vía prevista para producir
adjudicaciones humanas explícitas, condición necesaria para obtener etiquetas elegibles en el futuro.
Sin este flujo no existe una fuente legítima de etiquetas.

**Independent Test**: con un caso y una instantánea confirmada de ejemplo, abrir un registro,
consultar sus evidencias, guardar una revisión completa y comprobar que queda asociada al caso,
instantánea y registro correctos, con autor declarado, fecha, política y justificación; comprobar que
la instantánea y las ejecuciones anteriores no cambian.

**Acceptance Scenarios**:

1. **Given** un registro de una instantánea confirmada y una política aprobada, **When** la persona
   elige P2, escribe una justificación y guarda, **Then** la revisión queda asociada al caso,
   instantánea y registro, figura como completada y es elegible.
2. **Given** un registro con estado desconocido o indicadores indeterminados, **When** la persona
   revisa la evidencia y guarda «información insuficiente» con motivo, **Then** la revisión queda
   registrada pero no produce etiqueta elegible.
3. **Given** un registro con varios campos desconocidos, **When** la persona intenta guardar una clase
   P1–P4 sin justificación, **Then** el sistema impide el guardado y muestra el campo faltante.
4. **Given** una política propuesta pero no aprobada y la opción D-02=A adoptada por el equipo,
   **When** la persona guarda una clase, **Then** la revisión puede conservarse como propuesta, pero
   se muestra como **no elegible** y no se presenta como criterio experto aprobado. Con D-02=B, la
   entrada de P1–P4 queda bloqueada hasta la aprobación.

---

### User Story 2 - Corregir una revisión conservando el historial (Prioridad de entrega: 2)

Una persona consulta las revisiones anteriores de un registro, identifica la vigente y registra una
corrección mediante una nueva revisión trazable. La revisión anterior no se sobrescribe.

**Why this priority**: la revisión experta puede cambiar por nueva evidencia o desacuerdo. Sin
historial, una corrección destruye la trazabilidad y contamina cualquier etiqueta futura.

**Independent Test**: guardar una revisión, crear una segunda revisión que la reemplace y comprobar
que ambas se conservan, que la vigente es la nueva y que la anterior mantiene autor, fecha,
justificación y política.

**Acceptance Scenarios**:

1. **Given** una revisión completada, **When** la persona registra una corrección con nueva
   justificación, **Then** se crea una revisión nueva que reemplaza a la anterior sin borrarla.
2. **Given** dos revisiones del mismo registro, **When** se abre el historial, **Then** se muestra el
   orden, el estado de cada una y cuál es la vigente.
3. **Given** dos personas que intentan corregir el mismo registro a la vez, **When** ambas guardan,
   **Then** una se acepta y la otra recibe un aviso de conflicto sin sobrescribir la primera.

---

### User Story 3 - Distinguir elegibilidad y origen de la etiqueta (Prioridad de entrega: 3)

Una persona consulta si una revisión es elegible para entrenamiento, por qué lo es o no, y si la
etiqueta proviene de una adjudicación humana, de una política o de una predicción futura.

**Why this priority**: la elegibilidad mal comunicada convierte una revisión incompleta o una
sugerencia automática en una etiqueta de entrenamiento no validada.

**Independent Test**: guardar una revisión completa, una incompleta, una con desacuerdo pendiente y
una bajo política no aprobada; comprobar que solo la primera es elegible y que todas muestran el
motivo y el origen.

**Acceptance Scenarios**:

1. **Given** una revisión completa bajo política aprobada, **When** se consulta su estado, **Then**
   figura como elegible con origen «adjudicación humana».
2. **Given** una revisión con información insuficiente o desacuerdo pendiente, **When** se consulta,
   **Then** figura como no elegible y se explica el motivo.
3. **Given** una etiqueta generada por una política o una predicción futura, **When** se muestra en
   la interfaz, **Then** no se presenta como criterio experto ni como adjudicación humana.

---

### User Story 4 - Revisar casos límite sin forzar una clase (Prioridad de entrega: 4)

Una persona revisa registros `Fixed`, de estado desconocido, con indicadores indeterminados o con
datos faltantes de exposición, criticidad o contexto de IA, y registra una decisión explícita sin
convertirlos automáticamente en P4.

**Why this priority**: los casos límite son los que más riesgo tienen de producir etiquetas falsas o
de aparentar una prioridad que nadie adjudicó.

**Independent Test**: revisar un `Fixed`, un estado desconocido y un registro con indicadores
indeterminados; comprobar que cada uno exige una decisión explícita, conserva su estado original y no
genera una etiqueta elegible por defecto.

**Acceptance Scenarios**:

1. **Given** un registro `Fixed`, **When** la persona lo revisa, **Then** se muestra como antecedente
   histórico y no como pendiente de remediación; cualquier clase registrada se distingue de una
   prioridad operativa pendiente.
2. **Given** un estado desconocido, **When** la persona revisa, **Then** se exige una decisión manual
   explícita y no se infiere P4 por ausencia de información.
3. **Given** indicadores indeterminados, **When** la persona revisa, **Then** se muestran como
   indeterminados, no como negativos, y la revisión no los convierte en positivos.

---

### Edge Cases

- Registro de una instantánea no confirmada o de otro caso: no se ofrece revisión.
- El mismo registro aparente —mismo QID, IP, puerto, protocolo o First Detected— en dos instantáneas:
  se revisa por separado; no se copia la revisión.
- Revisión guardada y luego confirmada una nueva instantánea: la revisión sigue ligada a la
  instantánea anterior; no se transfiere ni se reasigna.
- `Fixed` con ambos indicadores positivos: antecedente prioritario reportado, no remediación
  pendiente ni P1 automática.
- Estado desconocido o indicador indeterminado: no se convierte en un valor conocido ni en P4.
- Información insuficiente: no se fuerza una clase; queda registrada como no elegible.
- Desacuerdo entre revisiones: no se resuelve por mayoría ni por la última persona que guardó; queda
  pendiente hasta una decisión explícita.
- Política no aprobada: no se generan etiquetas elegibles.
- Cambio de versión de política: las revisiones anteriores conservan su versión; no se
  reclasifican retroactivamente.
- Autor declarado vacío: no se guarda la revisión; la identidad declarada no es autenticación.
- Justificación vacía, demasiado corta o genérica: se rechaza con un mensaje comprensible.
- Doble envío o doble clic: se crea una sola revisión.
- Ediciones concurrentes: se detecta el conflicto y no se sobrescribe la revisión aceptada.
- Registro con datos de exposición, criticidad o contexto de IA ausentes: se muestran como no
  disponibles; no se inventan.
- Revisión de un registro que ya tiene una revisión vigente: se ofrece corregir, no editar en sitio.
- Aprobación de texto o de cita en otra parte del producto: no cambia la revisión de prioridad.
- Navegación móvil o con teclado: el flujo sigue siendo operable y accesible.

## Requirements *(mandatory)*

### Functional Requirements

**Alcance y asociación**

- **FR-001**: El sistema MUST permitir iniciar una revisión solo desde un registro perteneciente a
  una instantánea Qualys confirmada del caso abierto.
- **FR-002**: Toda revisión MUST quedar asociada de forma explícita al caso, a la instantánea y al
  registro concreto revisado.
- **FR-003**: El sistema MUST impedir que una revisión de un caso o instantánea se aplique a otro
  caso, otra instantánea o un registro aparentemente igual.
- **FR-004**: El sistema MUST conservar la revisión aunque se confirmen nuevas instantáneas; no debe
  transferirla ni reasignarla por QID, IP, puerto, protocolo ni First Detected.

**Evidencia y decisión**

- **FR-005**: La revisión MUST mostrar los datos disponibles del registro y su procedencia, incluidos
  estado, severidad original y de presentación, explotabilidad, malware, CVE y fechas disponibles.
- **FR-006**: La interfaz MUST distinguir valor conocido, desconocido e indeterminado; un valor
  indeterminado no puede mostrarse como negativo ni como positivo.
- **FR-007**: La revisión MUST permitir registrar una clase operacional P1, P2, P3 o P4, o bien una
  decisión de «información insuficiente» o «desacuerdo».
- **FR-008**: La revisión MUST exigir una justificación escrita para toda clase y para toda decisión
  de información insuficiente o desacuerdo.
- **FR-009**: La revisión MUST registrar la identidad declarada del autor, la fecha y la versión de
  política aplicada.
- **FR-010**: La identidad declarada MUST NOT presentarse como autenticación, autorización ni
  identidad verificada.
- **FR-011**: El sistema MUST NOT asignar plazos universales de remediación ni presentar una clase
  P1–P4 como plazo.
- **FR-012**: El sistema MUST NOT convertir automáticamente severidad, escala 1–5, bandera conjunta
  de explotabilidad y malware, estado o contexto de IA en una clase P1–P4.

**Política P1–P4**

- **FR-013**: El sistema MUST identificar cada política mediante una versión legible y un estado
  explícito: propuesta, aprobada, retirada o equivalente.
- **FR-014**: Cada versión de política MUST declarar, como mínimo, significado de las clases, datos
  mínimos, condiciones, excepciones, desempates, tratamiento de `Fixed`, de estados desconocidos y de
  indicadores indeterminados, tratamiento de información insuficiente y ejemplos de frontera.
- **FR-015**: Cada versión de política MUST indicar qué campos adicionales —exposición, criticidad,
  contexto de IA u otros— influyen cuando estén disponibles y cómo se trata su ausencia.
- **FR-016**: Las versiones de política MUST ser inmutables; un cambio de contenido MUST crear una
  versión nueva.
- **FR-017**: Toda revisión MUST citar la versión de política aplicada; un cambio de política MUST NOT
  reclasificar retroactivamente revisiones anteriores.
- **FR-018**: Mientras no exista una política aprobada, el sistema MUST NOT producir etiquetas
  elegibles para entrenamiento y MUST indicar esa condición de forma visible.

**Elegibilidad y etiquetas**

- **FR-019**: Una revisión MUST ser elegible solo si es una adjudicación humana explícita, completa,
  con justificación, autor declarado, fecha, versión de política aprobada y clase P1–P4.
- **FR-020**: Información insuficiente, desacuerdo pendiente, rechazo sin clase alternativa o revisión
  incompleta MUST NOT producir etiquetas elegibles.
- **FR-021**: El sistema MUST distinguir etiquetas adjudicadas por personas, etiquetas generadas por
  una política y predicciones futuras de un clasificador.
- **FR-022**: Ninguna etiqueta generada por política o predicción futura MUST presentarse como
  criterio experto ni como adjudicación humana.
- **FR-023**: Guardar una revisión MUST NOT disparar entrenamiento, reentrenamiento, activación,
  promoción ni despliegue de modelos.
- **FR-024**: La interfaz MUST mostrar si una revisión está pendiente, completada o no elegible, y
  explicar el motivo cuando no sea elegible.

**Historial y concurrencia**

- **FR-025**: El sistema MUST conservar todas las revisiones de un registro en orden trazable.
- **FR-026**: Una corrección MUST registrarse como revisión nueva que reemplaza a la vigente; la
  revisión anterior MUST conservarse sin sobrescritura.
- **FR-027**: El sistema MUST mostrar cuál es la revisión vigente y qué revisión reemplaza.
- **FR-028**: Un doble envío MUST producir una sola revisión o un resultado idempotente claramente
  identificado.
- **FR-029**: Dos ediciones concurrentes MUST resolverse sin sobrescritura silenciosa; la persona
  MUST ver el conflicto y decidir cómo continuar.
- **FR-030**: La revisión MUST NOT modificar el CSV original, la instantánea confirmada ni las
  evidencias de ejecuciones anteriores.

**Interfaz, accesibilidad y privacidad**

- **FR-031**: El acceso a la revisión MUST estar disponible desde un registro de la sección
  «Vulnerabilidades»; el menú MUST seguir mostrando «Vulnerabilidades» sin opciones que aparenten
  modelos o entrenamiento disponibles.
- **FR-032**: La interfaz MUST definir estados vacíos, validaciones por campo, errores comprensibles,
  indicador de carga y prevención de doble envío.
- **FR-033**: La interfaz MUST ser operable con teclado, foco visible, etiquetas accesibles, cierre de
  menú móvil con Escape y objetivos de escritorio, móvil 390 y 320 sin desbordamiento.
- **FR-034**: La revisión MUST usar datos ficticios claramente identificados en ejemplos y pruebas; no
  debe incorporar filas reales a la especificación, Git, capturas ni servicios externos.
- **FR-035**: La revisión MUST NOT enviar datos del caso a servicios externos; cualquier traza
  externa debe limitarse a metadatos acotados y autorizados.
- **FR-036**: El formulario MUST tratar el contenido del CSV como dato no confiable y escapar todo
  valor mostrado.
- **FR-037**: La aprobación de texto de una respuesta o de una cita MUST NOT crear, modificar ni
  habilitar una revisión de prioridad.
- **FR-038**: La funcionalidad MUST conservar las capacidades verificadas de 001 y 002; no puede
  degradar consulta documental, citas, memoria, importación, snapshots, filtros ni consulta
  estructurada.

- **FR-039**: La política aprobada MUST definir una única salida para cada combinación de estado,
  indicadores y contexto, o la salida «Información insuficiente»; no puede dejar combinaciones
  ambiguas ni dos clases posibles para el mismo caso.
- **FR-040**: La política aprobada MUST declarar por separado el tratamiento de estado desconocido,
  indicadores indeterminados, contexto adicional no disponible y desacuerdo entre revisores.
- **FR-041**: El sistema MUST permitir registrar contexto adicional documentado por registro o por
  alcance explícito —caso, activo o grupo de registros— con procedencia, fecha, autor declarado y
  estado de disponibilidad; no puede inferirlo desde QID, IP, puerto, protocolo ni First Detected.
- **FR-042**: La bandera de prioridad conjunta de 002 MUST conservarse como indicador de
  explotabilidad y malware positivos; no puede renombrarse, convertirse en P1 ni usarse como
  adjudicación humana automática.
- **FR-043**: La revisión humana recomendada de 001 MUST NOT convertirse en requisito obligatorio de
  esta funcionalidad.
- **FR-044**: Los datos mínimos exigidos por cada regla de la política MUST declararse y validarse; si
  falta un dato que podría cambiar la clase, la salida MUST ser «Información insuficiente».
- **FR-045**: La confirmación de evidencia revisada MUST formar parte de la elegibilidad cuando la
  política aprobada lo exija, sin reemplazar la justificación ni la clase.
- **FR-046**: El sistema MUST conservar por separado la prioridad sugerida por la regla, la prioridad
  adjudicada por la persona y el estado de elegibilidad; ninguna puede borrar ni sobrescribir a las
  otras.
- **FR-047**: El formulario MUST permitir registrar exposición, criticidad y vínculo con una
  aplicación de IA, cada uno con estado, procedencia o evidencia, justificación, autor declarado y
  fecha; el historial de contexto MUST conservarse.
- **FR-048**: Una discrepancia entre sugerencia y adjudicación MUST quedar visible y justificada, sin
  eliminar ninguna de las dos; la elegibilidad MUST indicar cuál se usa y por qué.
- **FR-049**: Ante un indicador indeterminado, el sistema MUST evaluar las alternativas compatibles;
  si todas producen la misma clase, MUST mostrar una sugerencia con incertidumbre; si producen clases
  distintas, MUST devolver «Información insuficiente» e identificar las alternativas y el dato
  decisivo.
- **FR-050**: El vínculo con una aplicación de IA MUST registrarse como contexto de alcance y no puede
  elevar por sí solo la criticidad ni la clase.
- **FR-051**: El contexto agregado MUST distinguir `high`, `not_high`, `incomplete` y
  `not_applicable`; `not_applicable` no puede convertirse automáticamente en `not_high`.

### Key Entities

- **Registro de vulnerabilidad confirmado**: fila de una instantánea Qualys confirmada, con caso,
  instantánea, posición lógica, estado, severidad, indicadores, CVE, fechas y procedencia. Es de solo
  lectura para esta funcionalidad.
- **Revisión de prioridad**: decisión humana asociada a un registro y una instantánea; conserva
  clase P1–P4 o decisión de insuficiencia/desacuerdo, justificación, autor declarado, fecha, versión
  de política, estado, elegibilidad, origen de etiqueta y vínculo con la revisión reemplazada.
- **Prioridad sugerida**: salida de la regla o política para un registro, con versión, incertidumbre y
  alternativas cuando corresponda. No es una adjudicación humana ni una etiqueta elegible.
- **Discrepancia**: diferencia conservada entre sugerencia y adjudicación, con justificación y efecto
  declarado sobre la elegibilidad; no elimina ninguna de las dos.
- **Versión de política P1–P4**: documento versionado e inmutable con estado, definiciones, datos
  mínimos, condiciones, excepciones, desempates, tratamiento de casos límite, ejemplos y campos
  adicionales considerados.
- **Estado de elegibilidad**: resultado explícito que indica si una revisión puede alimentar
  entrenamiento y por qué.
- **Origen de etiqueta**: adjudicación humana, generación por política o predicción futura de
  clasificador; solo la primera puede ser elegible en esta funcionalidad.
- **Contexto adicional documentado**: exposición, criticidad o vínculo con la aplicación de IA
  asociados a un registro o a un alcance explícito, con fuente, fecha, autor declarado y estado
  `high`, `not_high`, `incomplete` o `not_applicable`. No se infiere ni se transfiere entre
  instantáneas.
- **Historial de revisiones**: secuencia ordenada de revisiones de un registro, con revisión vigente
  y reemplazos.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de las revisiones guardadas queda asociado a un caso, una instantánea y un
  registro; ninguna revisión se transfiere a otra instantánea o caso.
- **SC-002**: El 0% de las revisiones incompletas, insuficientes, en desacuerdo o bajo política no
  aprobada produce etiquetas elegibles.
- **SC-003**: El 100% de las correcciones conserva la revisión anterior y muestra la vigente.
- **SC-004**: El 0% de las aprobaciones de texto o de citas genera una etiqueta de prioridad.
- **SC-005**: El 100% de los registros `Fixed`, de estado desconocido o con indicadores indeterminados
  recibe un tratamiento explícito y no una clase P4 automática.
- **SC-006**: Un doble envío produce una sola revisión; una edición concurrente no sobrescribe la
  revisión aceptada.
- **SC-007**: Una persona puede completar una revisión de ejemplo con los campos obligatorios en
  menos de 3 minutos en una prueba controlada, sin ayuda externa.
- **SC-008**: La interfaz funciona a 1440, 390 y 320 píxeles sin desbordamiento horizontal, con
  teclado, foco visible, etiquetas accesibles y Escape en el menú móvil.
- **SC-009**: El 100% de las revisiones muestra la versión de política aplicada y el motivo de
  elegibilidad o no elegibilidad.
- **SC-010**: Las suites de 001 y 002 siguen pasando; no se pierde ninguna capacidad existente.
- **SC-011**: La especificación, las pruebas y las capturas usan exclusivamente ejemplos ficticios;
  no contienen filas reales, IP, activos ni títulos del CSV autorizado.
- **SC-012**: El 100% de las combinaciones de la política aprobada produce una única salida o
  «Información insuficiente»; ninguna combinación queda ambigua.
- **SC-013**: El 100% de los registros con estado desconocido, indicador indeterminado, contexto
  faltante o desacuerdo muestra un motivo distinto y comprensible.
- **SC-014**: El 0% de las clases P1 se genera automáticamente desde severidad, escala 1–5 o bandera
  conjunta de 002.
- **SC-015**: El 0% de las revisiones propuestas se convierte automáticamente en elegible al aprobar
  una política; cada una requiere confirmación explícita bajo la versión aprobada.
- **SC-016**: El 100% de los indicadores indeterminados produce una sugerencia con incertidumbre solo
  cuando todas las alternativas coinciden, o «Información insuficiente» con alternativas y dato
  decisivo cuando difieren; ninguno se convierte en negativo.
- **SC-017**: El 100% del contexto registra exposición y criticidad por separado, con procedencia,
  autor, fecha y alcance; `not_applicable` no se presenta como `not_high`.
- **SC-018**: El 100% de las discrepancias entre sugerencia y adjudicación conserva ambas, muestra la
  diferencia y justifica cuál se usa para elegibilidad.

## Flujo de revisión propuesto

1. La persona abre la sección «Vulnerabilidades», elige una instantánea confirmada y localiza un
   registro.
2. Desde el registro accede a «Revisar prioridad».
3. La pantalla muestra:
   - identificación del caso, instantánea y registro;
   - estado, severidad original y de presentación, explotabilidad, malware, CVE y fechas;
   - procedencia y versión de la instantánea;
   - valores conocidos, desconocidos e indeterminados, sin convertir unos en otros;
   - sugerencia de la regla, si existe, con su versión, incertidumbre y alternativas;
   - exposición y criticidad por separado, con estado, fuente o evidencia, justificación, autor,
     fecha y alcance;
   - vínculo con una aplicación de IA, si corresponde, con evidencia y sin elevación automática;
   - política aplicable y su estado;
   - revisiones anteriores, historial de contexto y cuál es la vigente.
4. La persona revisa la sugerencia y decide:
   - aceptar la clase sugerida; o
   - adjudicar otra clase P1–P4; o
   - registrar «información insuficiente» o «desacuerdo».
5. Para cualquier adjudicación, registra justificación, identidad declarada, fecha y confirmación
   explícita de evidencia revisada. Para el contexto adicional registra exposición, criticidad y
   vínculo IA, con procedencia, justificación y alcance.
6. Si la adjudicación difiere de la sugerencia, el sistema conserva ambas, muestra la discrepancia y
   exige justificarla; no borra ni sobrescribe la sugerencia.
7. El sistema valida, guarda una revisión trazable, calcula elegibilidad y muestra:
   - clase sugerida;
   - clase adjudicada;
   - estado de elegibilidad y motivo;
   - discrepancia, si existe.
8. Si ya existía una revisión, la nueva se registra como corrección y la anterior se conserva. El
   historial de contexto también es acumulativo y no modifica la instantánea Qualys.
9. Si la política no está aprobada y se adopta D-02=A, la revisión se conserva como propuesta no
   elegible y la interfaz lo indica; con D-02=B se bloquea la entrada de P1–P4. En ningún caso se
   presenta como etiqueta experta.

## Decisiones de política ya respaldadas

Estas decisiones provienen de la constitución, AGENTS.md, los contratos de 002 y el acuerdo de
alcance ya registrado:

- La aprobación de un informe no adjudica prioridades.
- Solo una revisión explícita y elegible puede alimentar entrenamiento.
- Información insuficiente, rechazos sin prioridad alternativa y desacuerdos pendientes no producen
  etiquetas elegibles.
- La política P1–P4 debe acordarse antes de entrenar; el agente no la inventa ni la presume aprobada.
- Guardar una revisión no dispara entrenamiento ni activación.
- La identidad declarada no es autenticación.
- Las instantáneas confirmadas son inmutables y no existe identidad estable demostrada entre
  reportes.
- P1–P4 no se confunde con severidad, escala 1–5, bandera conjunta, estado ni aprobación de citas.
- La prioridad sugerida y la prioridad adjudicada por una persona son registros distintos; aprobar o
  aceptar una sugerencia no crea por sí solo una etiqueta experta.
- El contexto adicional complementa la revisión y no modifica el CSV ni la instantánea original.
- No se asignan plazos universales de remediación.
- El alcance aprobado excluye clasificador, entrenamiento, MLflow, Prefect, promoción, rollback,
  exportación y empaquetado operativo.

## Compromisos de la propuesta v1.2 y decisiones posteriores

La propuesta consolidada v1.2 está disponible fuera del repositorio y se consultó para esta revisión.
Sus afirmaciones son **compromisos propuestos para discusión**, no aprobación de la política:

- P1–P4 como variable objetivo operativa, con información insuficiente como abstención y no como
  quinta clase ni P4.
- Adjudicación explícita separada de la aceptación del texto o de la cita.
- Prioridad sugerida y prioridad adjudicada separadas; la aceptación no borra la sugerencia.
- Política operacional pendiente de aprobación antes de etiquetar.
- Uso de severidad, estado, criticidad, exposición y vínculo con la aplicación de IA solo cuando los
  datos existan y estén documentados.
- Etiquetas de política sintética distintas de las adjudicaciones expertas.
- Segunda revisión para casos críticos, fronteras y una muestra estratificada, no para todas las
  filas.
- Sin plazos universales de remediación.

Las decisiones posteriores ya registradas en la constitución, AGENTS.md y 002 se conservan y
prevalecen: P1–P4 se difirió al incremento 3; 002 no incluye el formulario de prioridad; las
instantáneas son inmutables; no hay identidad estable entre reportes; la identidad del revisor es
declarada y no autenticada; guardar una revisión no entrena ni activa modelos; 001 y 002 están
verificadas localmente.

## Propuesta de decisión P1–P4 (NO aprobada)

La siguiente regla es una **propuesta para revisión del equipo**, no una política aprobada. No
habilita etiquetas elegibles ni se presenta como criterio experto.

### Orden de evaluación

1. Si el estado es `Fixed`, la salida es **antecedente histórico**; no se asigna P1–P4 para
   remediación.
2. Si el estado es desconocido, la salida es **Información insuficiente**.
3. Si cualquier indicador es indeterminado, la salida es **Información insuficiente**.
4. Si el contexto adicional está disponible, se agrega según la regla de contexto.
5. Se aplica la tabla de decisión; la primera condición que coincide define la única salida.
6. Si falta un dato que podría cambiar la clase, la salida es **Información insuficiente**.

### Regla de contexto

El contexto no se infiere desde QID, IP, puerto, protocolo ni First Detected, no se transfiere entre
instantáneas y debe declarar su alcance —registro, activo, caso o grupo documentado—. Cada dato de
contexto conserva fuente o evidencia, justificación, autor declarado, fecha y alcance.

#### Exposición

- `known_high`: existe evidencia documentada de exposición alta para el alcance declarado.
- `known_not_high`: existe evidencia documentada de exposición baja o media para el alcance.
- `unknown`: no hay evidencia suficiente; se registra qué falta y por qué.
- `not_applicable`: la exposición no es un factor pertinente para ese registro o alcance; se exige
  justificación explícita.

La evidencia puede ser un inventario, una arquitectura, una política o una observación fechada. No se
acepta «no aplica» sin motivo ni se deduce por ausencia de dato.

#### Criticidad

- `known_high`: el activo o proceso tiene criticidad alta documentada para el caso.
- `known_not_high`: criticidad baja o media documentada.
- `unknown`: falta evidencia; se registra la carencia.
- `not_applicable`: la criticidad no es un factor pertinente; se exige justificación.

Criticidad no es severidad, exposición ni prioridad. Se documenta por separado.

#### Vínculo con una aplicación de IA

- `linked`: el registro afecta una aplicación de IA, sus datos, modelos o herramientas, con evidencia.
- `not_linked`: no existe ese vínculo, con evidencia.
- `unknown`: no se pudo determinar.
- `not_applicable`: el caso no contiene una aplicación de IA o el vínculo no corresponde; se justifica.

El vínculo con IA es contexto de alcance: **no eleva por sí solo la criticidad ni la clase**. Se usa
para justificar o interpretar el contexto, no como sustituto de exposición o criticidad.

#### Contexto agregado

El agregado usa exposición y criticidad; el vínculo con IA se registra aparte y no lo modifica
automáticamente.

- `high`: exposición o criticidad es `known_high`.
- `not_high`: ambas son `known_not_high`.
- `not_applicable`: ambas son `not_applicable`.
- `incomplete`: cualquier otra combinación, incluida una desconocida o una no aplicable junto a otra
  no alta. `not_applicable` no se convierte en `not_high`.

`incomplete` y `not_applicable` no permiten asignar una clase: la salida propuesta es Información
insuficiente, salvo `Fixed`, que se trata antes como antecedente histórico.

### Indicadores indeterminados

Regla propuesta:

1. Evaluar las alternativas compatibles con el dato desconocido.
2. Si todas producen la misma clase, permitir una **sugerencia** con incertidumbre; no es una
   adjudicación humana ni una etiqueta elegible.
3. Si producen clases distintas, devolver **Información insuficiente**, identificar las alternativas y
   solicitar el dato decisivo.
4. Nunca convertir un indeterminado en negativo.

Aplicación a la tabla actual: cualquier indicador indeterminado en un estado conocido distinto de
`Fixed` puede cambiar el patrón de indicadores y, con ello, la clase; por tanto, **en esta propuesta
todas las combinaciones con indeterminado producen Información insuficiente**. No se promete una
excepción que la tabla no contiene. Si el equipo cambia la tabla para que las alternativas coincidan,
la regla general permitiría una sugerencia con incertidumbre.

### Tabla de decisión propuesta

| Estado | Indicadores | Contexto agregado | Salida propuesta | Elegibilidad propuesta |
|---|---|---|---|---|
| `Fixed` | Cualquiera | Cualquiera | Antecedente histórico; no P1–P4 de remediación | No elegible para remediación; se conserva como antecedente |
| Desconocido | Cualquiera | Cualquiera | Información insuficiente | No elegible |
| `Active`/`New`/`Re-Opened` | Cualquier indicador indeterminado | Cualquiera | Información insuficiente con alternativas y dato decisivo | No elegible |
| `Active`/`New`/`Re-Opened` | Ambos positivos | `high` | P1 | Elegible solo con política aprobada y confirmación humana explícita |
| `Active`/`New`/`Re-Opened` | Ambos positivos | `not_high` | P2 | Elegible con política aprobada y confirmación humana explícita |
| `Active`/`New`/`Re-Opened` | Ambos positivos | `incomplete` | Información insuficiente | No elegible |
| `Active`/`New`/`Re-Opened` | Ambos positivos | `not_applicable` | Información insuficiente | No elegible |
| `Active`/`New`/`Re-Opened` | Un positivo | `high` | P2 | Elegible con política aprobada y confirmación humana explícita |
| `Active`/`New`/`Re-Opened` | Un positivo | `not_high` | P3 | Elegible con política aprobada y confirmación humana explícita |
| `Active`/`New`/`Re-Opened` | Un positivo | `incomplete` | Información insuficiente | No elegible |
| `Active`/`New`/`Re-Opened` | Un positivo | `not_applicable` | Información insuficiente | No elegible |
| `Active`/`New`/`Re-Opened` | Ninguno positivo | `high` | P3 | Elegible con política aprobada y confirmación humana explícita |
| `Active`/`New`/`Re-Opened` | Ninguno positivo | `not_high` y severidad 4–5 | P3 | Elegible con política aprobada y confirmación humana explícita |
| `Active`/`New`/`Re-Opened` | Ninguno positivo | `not_high` y severidad 1–3 | P4 | Elegible con política aprobada y confirmación humana explícita |
| `Active`/`New`/`Re-Opened` | Ninguno positivo | `incomplete` | Información insuficiente | No elegible |
| `Active`/`New`/`Re-Opened` | Ninguno positivo | `not_applicable` | Información insuficiente | No elegible |

Cada fila define una única salida para la combinación. Las filas se evalúan en el orden indicado:
`Fixed`, estado desconocido, indeterminado y luego el patrón de indicadores con el contexto agregado.
La severidad no promueve por sí sola una clase: solo desempata P3/P4 cuando no hay indicadores
positivos y el contexto es `not_high`. La bandera conjunta de 002 se conserva como indicador de ambos
positivos; no es P1 ni sustituye la adjudicación humana.

### Datos mínimos propuestos

Para cualquier clase distinta de «Información insuficiente» o «Antecedente histórico»:

- caso, instantánea y registro;
- estado, severidad y etiqueta de presentación;
- explotabilidad y malware con su estado conocido/indeterminado;
- exposición y criticidad por separado, con estado `known_high`, `known_not_high`, `unknown` o
  `not_applicable`, procedencia, justificación, autor, fecha y alcance;
- vínculo con una aplicación de IA con estado `linked`, `not_linked`, `unknown` o `not_applicable` y
  evidencia, sin efecto automático sobre la clase;
- contexto agregado `high`, `not_high`, `incomplete` o `not_applicable`;
- clase P1–P4 propuesta;
- justificación;
- autor declarado;
- fecha;
- versión de política;
- confirmación explícita de evidencia revisada;
- sugerencia de la regla, si existe, y adjudicación humana separadas; discrepancia justificada si
  difieren.

Datos opcionales: CVSS, antigüedad, tipo de detección u otros. El CVSS no está en el formato actual de
41 columnas; no se exige ni se supone. La ausencia de un dato opcional no se convierte en un valor
negativo.

### Ejemplos ficticios y frontera

Todos los ejemplos son ficticios y no provienen de filas privadas del CSV autorizado.

| Ejemplo | Datos ficticios | Salida propuesta |
|---|---|---|
| P1 | `QID 000001`, `CVE-2026-0001`, activo `app-demo.example`, Active, severidad 5, ambos indicadores positivos, exposición `known_high`, criticidad `known_high`, vínculo IA `linked` documentado | P1 |
| P2 por ambos positivos | Mismo registro, exposición y criticidad `known_not_high`, vínculo IA `linked` | P2; el vínculo IA no eleva por sí solo |
| P2 por un positivo | `QID 000002`, Active, severidad 4, explotabilidad positiva, malware negativo/no informado, exposición `known_high`, criticidad `known_not_high` | P2 |
| P3 por un positivo | Mismo registro, exposición y criticidad `known_not_high` | P3 |
| P3 sin positivos | `QID 000003`, Re-Opened, severidad 5, ambos indicadores negativos/no informados, exposición `known_high`, criticidad `known_not_high` | P3 |
| P4 | `QID 000004`, Active, severidad 2, ambos indicadores negativos/no informados, exposición y criticidad `known_not_high` | P4 |
| Frontera P1/P2 | Ambos positivos y contexto `high` frente a `not_high` | P1 frente a P2; `incomplete` o `not_applicable` producen Información insuficiente |
| Frontera P2/P3 | Un positivo y contexto `high` frente a `not_high` | P2 frente a P3; `incomplete` o `not_applicable` producen Información insuficiente |
| Frontera P3/P4 | Ninguno positivo, contexto `not_high`, severidad 4–5 frente a 1–3 | P3 frente a P4; `incomplete` o `not_applicable` producen Información insuficiente |
| `Fixed` | `QID 000005`, Fixed, ambos positivos, contexto `high`, vínculo IA `linked` | Antecedente histórico; no P1–P4 de remediación |
| Estado desconocido | `QID 000006`, UnknownState, ambos positivos, contexto `high` | Información insuficiente |
| Indicador indeterminado | `QID 000007`, Active, explotabilidad indeterminada, malware positivo, contexto `high` | Información insuficiente; alternativas P1/P2 y dato decisivo |
| Contexto incompleto | `QID 000008`, Active, ambos positivos, exposición `unknown`, criticidad `known_not_high` | Información insuficiente; falta exposición |
| Contexto no aplicable | `QID 000009`, Active, ambos positivos, exposición y criticidad `not_applicable` | Información insuficiente; no se convierte en `not_high` |
| Discrepancia | `QID 000010`, sugerencia P1, adjudicación humana P2 con justificación | Se conservan ambas; la discrepancia queda visible y la elegibilidad usa la adjudicación si cumple las condiciones |


## Tratamiento de información faltante, estado desconocido, indicadores indeterminados y desacuerdo

| Situación | ¿Impide adjudicar? | Salida propuesta | Explicación |
|---|---|---|---|
| Estado de vulnerabilidad desconocido | Sí, para prioridad de remediación | Información insuficiente | El estado original se conserva; no se convierte en P4 ni en conocido |
| Indicador indeterminado | Sí, en la tabla actual | Información insuficiente con alternativas y dato decisivo | Puede cambiar el patrón de indicadores; no se convierte en negativo ni se usa para forzar P4 |
| Contexto `incomplete` | Sí | Información insuficiente | Falta exposición o criticidad, o una no aplicable impide el agregado; se registra qué falta |
| Contexto `not_applicable` | Sí, en la propuesta actual | Información insuficiente | No se convierte automáticamente en `not_high`; requiere una decisión de política |
| Sugerencia y adjudicación diferentes | No impide por sí sola, pero exige justificación | Ambas se conservan; la discrepancia queda visible | La elegibilidad usa la adjudicación humana si cumple las condiciones; no se borra la sugerencia |
| Desacuerdo entre revisores | Sí, hasta resolución explícita | Desacuerdo pendiente | No se resuelve por mayoría ni por la última revisión |
| Evidencia o justificación insuficiente | Sí | Información insuficiente o revisión incompleta | No se genera etiqueta elegible |
| `Fixed` | No aplica prioridad de remediación | Antecedente histórico | No es P1–P4 ni pendiente de remediación |
| Datos conocidos suficientes | No | Clase según la tabla | Requiere confirmación humana y política aprobada |


## Resultado de aplicabilidad con el CSV filtrado (simulación exploratoria)

Fecha: 2026-11-09. Insumo: `../14-Qualys_Hallazgos_Active_New_ReOpened.csv` y su manifiesto. Se usó
almacenamiento temporal, `LANGSMITH_TRACING=false`, sin modelos, sin servicios externos y sin guardar
etiquetas operativas. No se abrió el reporte original de 62 MB. Solo se reportan agregados; no se
incluyen filas, activos, IP ni títulos.

La simulación aplica la regla propuesta de esta especificación a los datos realmente disponibles:

| Resultado | Cantidad |
|---|---|
| Registros totales | 662 |
| Registros con estado conocido (`pending_known`) | 662 |
| `Fixed` | 0 |
| Estado desconocido | 0 |
| Registros que obtienen una clase con los datos actuales | 0 |
| Registros con Información insuficiente | 662 |

Motivos de insuficiencia, contando cada registro una vez en el total:

| Motivo | Registros |
|---|---|
| Contexto faltante (exposición/criticidad) | 662 |
| Algún indicador indeterminado | 654 |
| Contexto faltante e indicador indeterminado (solapamiento) | 654 |
| Solo contexto faltante, indicadores determinados | 8 |

Los motivos se solapan: la unión es 662 registros insuficientes, no la suma de la columna.

Patrones de indicadores observados:

| Patrón | Registros |
|---|---|
| Ambos positivos | 8 |
| Solo explotabilidad positiva | 121 |
| Solo malware positivo | 0 |
| Ninguno positivo | 533 |
| Ambos indeterminados | 533 |
| Malware indeterminado y explotabilidad positiva | 121 |

No se detectaron columnas de exposición, criticidad ni vínculo con una aplicación de IA. `TruRisk
Score` existe en el CSV, pero es un puntaje del proveedor y no se usa como exposición ni criticidad.
Tampoco se usan `Threat`, `Impact`, `PCI Vuln`, `Category` ni `Associated Tags` como exposición o
criticidad: son campos descriptivos del proveedor, no contexto documentado del caso.

Datos adicionales que habría que completar para obtener cobertura:

- exposición y criticidad documentadas para 662 registros, con procedencia y alcance;
- resolución de indicadores para 654 registros: 533 con ambos indeterminados y 121 con malware
  indeterminado y explotabilidad positiva;
- vínculo con IA documentado cuando corresponda, sin asumirlo como elevación automática.

Con esta propuesta y los datos actuales, **ningún registro obtiene una clase**. El resultado mide
aplicabilidad de la política, no precisión, calidad del clasificador ni desempeño predictivo. No se
inventó contexto para aumentar la cobertura.

## Recomendaciones propuestas para decisión del responsable (NO aprobadas)

1. **Aprobar la política por acuerdo del equipo**, registrada con versión, fecha y contenido.
2. **Mientras no esté aprobada, permitir revisiones propuestas no elegibles**, claramente marcadas.
3. **Una aprobación posterior no convierte automáticamente las revisiones previas en elegibles**:
   requieren confirmación explícita bajo la versión aprobada.
4. **Usar los datos existentes de Qualys y el contexto adicional documentado cuando exista**; no
   inventar exposición, criticidad, CVSS ni contexto de IA.
5. **Tratar `Fixed` como antecedente histórico**, sin prioridad de remediación pendiente ni etiqueta
   para ese objetivo.
6. **Exigir para elegibilidad**: clase, justificación, autor declarado, fecha, versión aprobada y
   confirmación explícita de evidencia revisada.
7. **Conservar las revisiones históricas bajo su versión**; cada entrenamiento futuro debe seleccionar
   expresamente las versiones compatibles.
8. **No exigir una segunda revisión para toda fila por defecto**; reservarla para casos críticos,
   fronteras y una muestra estratificada, como propone v1.2.
9. **No convertir la revisión humana recomendada de 001 en requisito obligatorio** de esta
   funcionalidad.
10. **Conservar siempre la sugerencia de la regla y la adjudicación humana**; si difieren, mostrar la
    discrepancia, exigir justificación y no borrar ninguna. La elegibilidad usa la adjudicación
    humana si cumple las condiciones.
11. **Registrar el vínculo con una aplicación de IA como contexto de alcance**, sin usarlo como
    elevación automática de criticidad o clase.

## Decisiones pendientes y preguntas abiertas

Ninguna decisión de esta sección se considera resuelta. La política operacional P1–P4 sigue
**pendiente de aprobación** por el equipo.

### Grupo A — Gobernanza de la política

| ID | Decisión pendiente | Alternativas concretas | Recomendación propuesta | Impacto |
|---|---|---|---|---|
| D-01 | ¿Quién aprueba la política y cómo se registra? | A) Acuerdo de las tres personas del equipo con fecha y versión; B) aprobación del responsable del producto con revisión del equipo; C) aprobación externa del mentor/docente | A, por la gobernanza vigente de la constitución | Define cuándo una versión pasa a «aprobada» y habilita elegibilidad |
| D-02 | ¿Qué ocurre si no hay política aprobada? | A) Permitir revisiones propuestas no elegibles; B) bloquear la entrada de P1–P4 hasta la aprobación; C) permitir solo borradores sin clase | A, con marca visible de no elegible | Afecta la usabilidad inicial y el riesgo de etiquetas prematuras |
| D-03 | ¿Cómo se retira o reemplaza una política? | A) Versión nueva y política anterior «retirada», sin reclasificar; B) reclasificación retroactiva controlada; C) congelar todas las revisiones antiguas | A, conservando historial por versión | Afecta historial y reproducibilidad |

### Grupo B — Contenido de las clases

| ID | Decisión pendiente | Alternativas concretas | Recomendación propuesta | Impacto |
|---|---|---|---|---|
| D-04 | Significado y datos mínimos de P1, P2, P3 y P4 | A) regla basada solo en campos existentes de Qualys; B) regla que incorpora exposición/criticidad/contexto de IA cuando existan; C) definición cualitativa con ejemplos y revisión caso a caso | B, con abstención cuando falte contexto que pueda cambiar la clase | Determina la política y los ejemplos de frontera |
| D-05 | Condiciones, excepciones y desempates | A) prioridad lexicográfica por indicadores, luego severidad; B) puntaje ponderado explícito; C) árbol de decisión con excepciones documentadas | C, con la tabla determinista propuesta | Define reproducibilidad y discusión entre revisores |
| D-06 | Tratamiento de `Fixed` | A) no recibe clase operativa pendiente; se registra como antecedente histórico; B) puede recibir clase solo para análisis histórico y no elegible; C) puede recibir clase elegible si el equipo lo justifica | A, sin etiqueta para remediación | Evita confundir antecedente con remediación pendiente |
| D-07 | Tratamiento de estado desconocido e indicadores indeterminados | A) revisión manual obligatoria y no elegible hasta resolver; B) permite clase con justificación y marca de incertidumbre; C) excluye del conjunto de entrenamiento | A, con motivos separados | Afecta elegibilidad y falsos positivos |
| D-08 | Influencia de exposición, criticidad y contexto de IA | A) solo si existen y están documentados; B) se exige completarlos antes de elegir P1/P2; C) no se usan hasta una funcionalidad posterior | A, con exposición y criticidad separadas y abstención si el agregado es `incomplete` o `not_applicable` | Determina si faltan datos para clases altas |
| D-09 | Tratamiento de información insuficiente | A) decisión explícita sin clase y no elegible; B) clase provisional P4 no elegible; C) bloqueo hasta completar datos | A, nunca P4 | Evita forzar P4 |
| D-10 | Ejemplos de frontera entre clases | A) dos ejemplos por frontera (P1/P2, P2/P3, P3/P4); B) un ejemplo por clase y reglas de desempate; C) matriz de casos con datos ficticios | C, con los ejemplos ficticios de esta especificación | Reduce ambigüedad entre revisores |

### Grupo C — Elegibilidad y cambios

| ID | Decisión pendiente | Alternativas concretas | Recomendación propuesta | Impacto |
|---|---|---|---|---|
| D-11 | Datos mínimos para elegibilidad | A) clase, justificación, autor, fecha y política aprobada; B) además, confirmación explícita de evidencia revisada; C) además, segunda revisión independiente | B, sin segunda revisión obligatoria para toda fila | Define el costo y la calidad de la etiqueta |
| D-12 | Corrección y desacuerdo | A) nueva revisión reemplaza y conserva historial; B) desacuerdo crea revisión paralela hasta resolución; C) ambas | C, con revisión vigente y desacuerdo pendiente | Afecta el estado «pendiente» y la elegibilidad |
| D-13 | Efecto de un cambio de política | A) revisiones antiguas conservan elegibilidad según su versión aprobada; B) se recalifican y quedan pendientes; C) se excluyen del entrenamiento | A, con selección explícita de versiones compatibles | Afecta reproducibilidad del conjunto de etiquetas |
| D-14 | Discrepancia entre sugerencia y adjudicación | A) conservar ambas, adjudicación humana prevalece si cumple condiciones y la discrepancia se justifica; B) bloquear elegibilidad hasta resolverla; C) exigir segunda revisión | A, sin borrar la sugerencia | Define qué se usa para entrenamiento y cómo se audita |
| D-15 | Efecto del vínculo con una aplicación de IA | A) registrar como alcance sin elevación automática; B) usarlo solo si la política lo define; C) excluirlo del contexto | A, con justificación explícita | Evita asumir que IA implica mayor criticidad |

### Preguntas abiertas prioritarias

- **Q1 (D-01/D-02)**: ¿La política se aprueba por acuerdo de las tres personas y se permite guardar
  revisiones propuestas no elegibles mientras tanto?
- **Q2 (D-04/D-05)**: ¿La tabla determinista propuesta es la base aceptada, o el equipo prefiere un
  puntaje ponderado o una definición cualitativa?
- **Q3 (D-06/D-07/D-08)**: ¿`Fixed` queda fuera de la prioridad de remediación y el estado
  desconocido/indicador indeterminado/contexto faltante obligan a abstención?
- **Q4 (D-11/D-12)**: ¿La elegibilidad exige confirmación explícita de evidencia revisada y cómo se
  resuelve un desacuerdo?
- **Q5 (D-13)**: ¿Las revisiones antiguas conservan su versión y cada entrenamiento selecciona
  versiones compatibles?
- **Q6 (D-14)**: ¿La sugerencia y la adjudicación se conservan siempre, y la adjudicación humana
  prevalece para elegibilidad si cumple las condiciones?
- **Q7 (D-15)**: ¿El vínculo con IA se registra como alcance sin elevar automáticamente la clase?

## Assumptions

- 001 y 002 están implementadas y verificadas localmente; sus flujos y garantías se conservan.
- Las instantáneas confirmadas son inmutables y no existe identidad estable demostrada de una
  vulnerabilidad entre reportes.
- La política operacional P1–P4 no está aprobada; la propuesta de esta especificación es educativa y
  no normativa.
- Se propone registrar revisiones bajo una política propuesta, pero no considerarlas elegibles hasta
  que exista una versión aprobada. Es una recomendación sujeta a D-02, no una decisión aprobada.
- El autor se registra como identidad declarada, sin autenticación.
- No se dispone de datos de exposición, criticidad, CVSS o contexto de IA para las 662 filas de
  referencia; no se suponen. El CVSS no forma parte del formato actual de 41 columnas.
- Los ejemplos de interfaz y pruebas usan datos ficticios; no se incorporan filas reales.
- La simulación de aplicabilidad con el CSV actual da 0/662 registros clasificables; no se usó para
  inventar contexto ni para ajustar la política.
- `not_applicable` no se trata como `not_high`; en esta propuesta conduce a Información insuficiente
  hasta que D-08 defina otra cosa.
- El vínculo con una aplicación de IA se registra como alcance, no como elevación automática de
  criticidad o clase.
- La propuesta consolidada v1.2 se consultó fuera del repositorio. Sus compromisos se usan como
  propuestas para discusión; no acreditan aprobación de la política P1–P4. Esta especificación se basa
  además en la constitución, AGENTS.md, los contratos de 002 y
  `docs/planificacion/00-contexto-inicial.md`.
- El menú existente se mantiene como «Vulnerabilidades»; no se añaden opciones de modelos,
  entrenamiento ni etiquetas antes de implementarlas.

## Fuera de alcance

No forman parte de esta funcionalidad:

- el clasificador y su entrenamiento, reentrenamiento o ajuste;
- MLflow, Prefect, promoción, rollback, exportación y empaquetado operativo;
- la generación automática de etiquetas P1–P4;
- la modificación del CSV, de las instantáneas o de las evidencias de ejecución;
- la aprobación de informes o de citas como sustituto de la revisión de prioridad;
- plazos universales de remediación;
- autenticación, autorización o identidad verificada;
- datos de exposición, criticidad o contexto de IA que no estén disponibles.

## Dependencias para las futuras funcionalidades de clasificación y operación

- **Aprobación de la política P1–P4 (A-01)** con versión, contenido, condiciones, excepciones,
  datos mínimos y ejemplos.
- **Definición de elegibilidad y datos mínimos** para que el clasificador consuma solo etiquetas
  humanas válidas.
- **Historial de revisiones y versiones de política** para reproducir el conjunto de etiquetas.
- **Separación de fuentes de etiqueta** para no mezclar adjudicaciones, políticas y predicciones.
- **Esquema futuro de exportación** de etiquetas elegibles, con versión de política y procedencia.
- **Clasificador futuro** que compare con líneas base de severidad y política, sin reutilizar la
  prueba final para seleccionar.
- **Operación futura** con MLflow, Prefect, promoción, rollback y empaquetado, fuera de este alcance.
- **Conservación de 001 y 002** como regresión obligatoria antes de cualquier avance del incremento 3.
