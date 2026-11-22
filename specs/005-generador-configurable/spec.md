# Feature Specification: Generador configurable (Ollama, DeepSeek y Claude Haiku)

**Feature Branch**: `005-generador-configurable` (no creada en este paso)

**Created**: 2026-11-22

**Status**: Borrador planificable. Investigación, plan, diseño y tareas generados, y análisis de
consistencia documental aplicado. Ninguna tarea ejecutada, ninguna dependencia instalada, ninguna
llamada pagada realizada y ninguna aceptación declarada. No habilita implementación por sí solo.

**Input**: User description: «Prepara la funcionalidad 005 de SecGuard Advisor: selección
configurable del generador entre Ollama local, DeepSeek Flash y Claude Haiku». 004 está cerrado y
aceptado localmente; 003 continúa suspendida.

## Contexto y distinciones

Esta funcionalidad cambia **qué generador produce la respuesta** sin cambiar el flujo de consulta:
recuperación en Qdrant, SQLite como fuente de verdad, memoria por caso, `findings_query`, citas
verificables, reparación acotada y abstención se conservan. EmbeddingGemma sigue local y Qdrant sigue
siendo el índice documental.

- **Ollama local** permanece disponible con el modelo actual y no se retira.
- Se añaden adaptadores para **DeepSeek** y **Anthropic (Claude Haiku)**.
- La selección es explícita por configuración local; **no hay fallback automático** ni cambio de
  proveedor durante un turno.
- No se construye un formulario de administración de proveedores.
- No se añaden otros proveedores, Telegram, informes nuevos ni clasificación P1–P4.
- El presupuesto externo **no está aprobado** en esta preparación. No se realizan llamadas pagadas.
- 003 continúa suspendida y 004 no se reabre.

**Hallazgo de compatibilidad relevante:** el esquema actual `ToolDecision.arguments` es un objeto
libre (`dict`). Los esquemas estructurados de Anthropic no admiten un objeto sin propiedades
declaradas de forma útil. La especificación exige un esquema de argumentos **tipado y acotado**,
compatible con los tres proveedores y equivalente en comportamiento a `findings_query`. No se cambia
la semántica de la herramienta.

**Hallazgo de contexto relevante:** el tokenizador GGUF actual mide el prompt de Ollama y no es
válido para proveedores externos. Cada proveedor necesita su propia admisión de contexto. Anthropic
ofrece un endpoint gratuito de conteo; DeepSeek publica un tokenizador fuera de línea y devuelve uso
observado. La especificación exige una medición conservadora antes de la llamada y el uso observado
después.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Elegir el generador sin cambiar el flujo (Priority: P1)

Una persona con acceso local edita la configuración, elige `ollama`, `deepseek` o `anthropic`, define
el identificador de modelo, la credencial cuando corresponde y los límites. Al arrancar, la
aplicación valida la configuración y falla con un mensaje claro si falta algo. La consulta, la
memoria, la herramienta, las citas y la evidencia de ejecución funcionan igual; cada ejecución
registra proveedor, modelo, uso y costo.

**Why this priority**: sin una selección explícita y validada no existe una funcionalidad
configurable segura. Es la base de las otras dos entregas.

**Independent Test**: arrancar con `ollama` y con una configuración externa ficticia; comprobar que
la selección se respeta, que una credencial ausente impide arrancar con un mensaje claro, que no hay
fallback y que la ejecución registra el proveedor y el modelo correctos.

**Acceptance Scenarios**:

1. **Given** una configuración con `provider=ollama`, **When** se ejecuta una consulta, **Then** el
   flujo actual funciona sin cambios y la ejecución registra `ollama` y el modelo local.
2. **Given** una configuración con `provider=anthropic` y credencial presente, **When** se ejecuta
   una consulta autorizada, **Then** se usa Anthropic, se registra el modelo y no se intenta Ollama.
3. **Given** una configuración con `provider=deepseek` y credencial ausente, **When** se intenta
   arrancar, **Then** la aplicación no arranca y explica qué variable falta, sin mostrar secretos.
4. **Given** un proveedor seleccionado, **When** una llamada falla, **Then** el turno falla de forma
   clasificada y no cambia de proveedor.

---

### User Story 2 - Impedir la salida de contenido privado (Priority: P2)

Una persona configura un proveedor externo y necesita que el contenido privado del caso no salga del
equipo. La aplicación bloquea el envío externo salvo autorización explícita por caso, nunca envía
registros Qualys ni sus derivados, y mantiene LangSmith con su política independiente. Si no hay
autorización, el turno se detiene antes de cualquier llamada externa.

**Why this priority**: la inferencia externa amplía la superficie de exposición; sin frontera de
datos la funcionalidad no es aceptable.

**Independent Test**: con un caso privado sin autorización, seleccionar un proveedor externo y
comprobar que no se realiza ninguna llamada y que el error es explícito; con un caso ficticio
autorizado, comprobar que solo se envía el contenido permitido y que Qualys nunca se envía.

**Acceptance Scenarios**:

1. **Given** un caso con documentos privados y sin autorización externa, **When** se consulta con un
   proveedor externo, **Then** el turno falla con `external_processing_blocked` antes de la llamada.
2. **Given** un caso ficticio con autorización vigente, **When** se consulta con un proveedor
   externo, **Then** se envía solo la pregunta, el historial permitido, los fragmentos autorizados y,
   si corresponde, un resultado sintético acotado; nunca datos importados.
3. **Given** una importación Qualys confirmada, **When** se consulta con un proveedor externo,
   **Then** ningún registro, fila, CVE, activo ni resultado derivado se envía al proveedor.
4. **Given** LangSmith desactivado, **When** se activa un proveedor externo, **Then** LangSmith
   sigue desactivado y no recibe contenido.

---

### User Story 3 - Controlar contexto, uso y gasto (Priority: P3)

Una persona que usa un proveedor externo necesita saber cuánto contexto se envía, cuánto se gasta y
qué ocurre al agotarse el presupuesto. El sistema mide el prompt antes de la llamada con el método
del proveedor, reserva el gasto máximo antes de cada intento, registra el uso observado y calcula el
costo con una tarifa fechada; si no hay datos suficientes, informa «costo desconocido», nunca cero.

**Why this priority**: sin control de contexto y gasto no se puede autorizar un proveedor pago.

**Independent Test**: con un presupuesto pequeño, comprobar que una llamada que excede el saldo se
bloquea antes de enviarse; con una respuesta que informa uso, comprobar el costo calculado; sin uso
observado, comprobar «desconocido».

**Acceptance Scenarios**:

1. **Given** un prompt que excede el límite de contexto del proveedor, **When** se intenta generar,
   **Then** se reduce historial y fuentes; si el mínimo no cabe, falla con `context_budget_exceeded`.
2. **Given** un presupuesto configurado, **When** el costo máximo reservado supera el saldo,
   **Then** la llamada no se envía y el turno falla con `budget_exceeded`.
3. **Given** una respuesta con uso reportado, **When** termina el turno, **Then** se registran
   tokens de entrada, salida y caché, duración, proveedor, modelo y costo calculado.
4. **Given** una respuesta sin uso reportado, **When** termina el turno, **Then** el costo se marca
   `unknown` y no se presenta como cero.

---

### User Story 4 - Comparar proveedores con evidencia reproducible (Priority: P4)

Una persona autorizada ejecuta un conjunto pequeño y reproducible de preguntas públicas o ficticias
con los tres proveedores y compara tiempo, citas, seguimiento de instrucciones, estructura,
recomendaciones y costo. Los resultados medidos se mantienen separados de las expectativas.

**Why this priority**: la comparación sustenta una decisión posterior, pero no es necesaria para que
la selección configurable funcione.

**Independent Test**: ejecutar el conjunto con Ollama local y con los proveedores externos que tengan
credencial y presupuesto; comprobar que el reporte separa mediciones de expectativas y que una
ejecución sin credencial se omite con motivo.

**Acceptance Scenarios**:

1. **Given** el conjunto público/ficticio y presupuesto autorizado, **When** se ejecuta la
   comparación, **Then** cada proveedor recibe las mismas preguntas y el reporte registra métricas
   por proveedor.
2. **Given** ausencia de credencial o presupuesto, **When** se intenta comparar un proveedor externo,
   **Then** se omite con un motivo explícito y no se simula un resultado.
3. **Given** los resultados, **When** se publica el informe, **Then** las mediciones y las
   expectativas están en secciones separadas.

---

### Edge Cases

- Credencial presente pero inválida o revocada: error de autenticación clasificado, sin reintentos
  infinitos y sin mostrar la clave.
- Proveedor externo sin saldo o límite de tasa: error clasificado; no se reintenta más allá del
  límite y no hay fallback.
- Respuesta externa con JSON inválido, vacío o truncado: se aplica la reparación acotada existente y,
  si falla, `invalid_model_output` o abstención, según corresponda.
- Respuesta externa sin campos de uso: costo `unknown`, no cero.
- Prompt mínimo que no cabe en el contexto del proveedor: `context_budget_exceeded`, sin recortar la
  pregunta ni el contexto declarado del caso.
- Cambio de proveedor a mitad de un turno: imposible por diseño; la configuración se resuelve al
  arrancar y el proveedor se fija por ejecución.
- Reinicio con una reserva de presupuesto abierta: la reserva se reconcilia; no se deja gasto
  duplicado ni se presenta una llamada no realizada como ejecutada.
- Caso autorizado externamente que luego se revoca: las llamadas siguientes se bloquean; las
  ejecuciones anteriores conservan su evidencia.
- LangSmith activo y proveedor externo activo: cada uno mantiene su política; activar uno no autoriza
  al otro.
- Modelo externo retirado o identificador inválido: validación de arranque o error del proveedor
  clasificado; se documenta la fecha de verificación y se exige revalidar.

## Requirements *(mandatory)*

### Functional Requirements

**Configuración y selección**

- **FR-001**: El sistema MUST permitir seleccionar explícitamente el proveedor activo entre `ollama`,
  `deepseek` y `anthropic`, con `ollama` como valor predeterminado.
- **FR-002**: El sistema MUST permitir configurar el identificador de modelo, el límite de salida, los
  tiempos de espera y el presupuesto por proveedor.
- **FR-003**: El sistema MUST leer la configuración local desde un archivo excluido de Git y desde
  variables de entorno, con precedencia explícita: variables de entorno > archivo local > valores
  predeterminados.
- **FR-004**: El sistema MUST entregar una plantilla de configuración sin credenciales y MUST NOT
  versionar el archivo con secretos.
- **FR-005**: El sistema MUST validar la configuración al arrancar y MUST fallar con un mensaje claro
  si falta una credencial, el proveedor es desconocido o un límite es inválido.
- **FR-006**: El sistema MUST NOT aplicar fallback automático entre proveedores ni cambiar de
  proveedor durante un turno.
- **FR-007**: Cada ejecución MUST registrar proveedor, identificador de modelo, versión o digest
  cuando exista, límites aplicados y resultado, sin almacenar secretos.

**Contratos funcionales**

- **FR-008**: Los tres proveedores MUST conservar el mismo flujo: recuperación, memoria acotada,
  decisión de herramienta, generación de respuesta, citas verificables, reparación acotada y
  abstención.
- **FR-009**: El sistema MUST reutilizar un único grafo y un contrato común de generador; MUST NOT
  duplicar el grafo por proveedor.
- **FR-010**: El esquema de decisión de herramienta MUST ser tipado, acotado y compatible con los tres
  proveedores, con la misma semántica de `findings_query`.
- **FR-011**: Los errores de proveedor MUST clasificarse al menos como no disponible, timeout,
  autenticación, límite de tasa, salida inválida, presupuesto agotado, falta de autorización externa
  y herramienta bloqueada, con mensajes al usuario sin secretos.
- **FR-012**: Los límites existentes de operaciones, llamadas a herramienta, reparación y tiempo del
  turno MUST conservarse para todos los proveedores.

**Contexto, uso y costo**

- **FR-013**: El tokenizador GGUF MUST aplicarse solo a Ollama. Cada proveedor externo MUST usar su
  propio método de admisión de contexto, documentado y conservador.
- **FR-014**: El sistema MUST medir o estimar el prompt antes de cada llamada externa y MUST reducir
  historial y fuentes antes de exceder el contexto; si el mínimo no cabe, MUST fallar con
  `context_budget_exceeded`.
- **FR-015**: El sistema MUST registrar tokens de entrada, salida y caché reportados por el
  proveedor, la duración y el modelo.
- **FR-016**: El sistema MUST calcular el costo con una tarifa fechada y versionada; si faltan datos,
  MUST registrar `unknown` y MUST NOT inventar cero.
- **FR-017**: El sistema MUST reservar el gasto máximo antes de cada llamada, incluidos reintentos, y
  MUST bloquear con `budget_exceeded` si no hay saldo.
- **FR-018**: La reserva y la liquidación del presupuesto MUST sobrevivir a un reinicio y MUST
  reconciliarse sin duplicar gasto.

**Privacidad**

- **FR-019**: El sistema MUST bloquear cualquier llamada a un proveedor externo si el caso no tiene
  una autorización explícita vigente para procesamiento externo.
- **FR-020**: La autorización externa MUST registrar alcance, política, identidad declarada, fecha y
  revocación; MUST NOT inferirse de la mera existencia de una credencial.
- **FR-021**: El sistema MUST impedir el envío de registros Qualys, filas, CVE, activos,
  resultados de herramientas importadas y cualquier derivado privado a proveedores externos. Un
  resultado sintético de `findings_query` solo puede enviarse si el caso está autorizado como
  `fictional_case` y el resultado declara `origin=synthetic`; un resultado importado o mixto MUST
  bloquearse.
- **FR-022**: El sistema MUST aplicar minimización y redacción al historial, la pregunta, el contexto
  del caso y los fragmentos antes de cualquier salida externa.
- **FR-023**: Activar un proveedor externo MUST NOT habilitar ni ampliar LangSmith; cada política
  permanece independiente.
- **FR-024**: El sistema MUST NOT afirmar retención cero, ausencia de entrenamiento ni garantía de
  privacidad sin evidencia documental aplicable.

**Modelos y verificación**

- **FR-025**: Los identificadores y capacidades de Claude Haiku y DeepSeek MUST verificarse en
  documentación oficial, con fecha y fuente registradas, antes de implementar y antes de aceptar.
- **FR-026**: El sistema MUST NOT asumir que una denominación comercial es un identificador de API
  válido; el identificador configurado MUST validarse contra la documentación vigente.
- **FR-027**: Las pruebas externas MUST ejecutarse solo con credenciales y presupuesto explícitos; sin
  ellos MUST omitirse con motivo y MUST NOT simular resultados.
- **FR-028**: El sistema MUST conservar la integración local real con Ollama como prueba obligatoria.

**Alcance**

- **FR-029**: La funcionalidad MUST NOT añadir otros proveedores, Telegram, informes nuevos,
  clasificación P1–P4 ni un formulario de administración de proveedores.
- **FR-030**: La funcionalidad MUST NOT modificar el modelo de embeddings, el índice Qdrant, la
  semántica de Qualys ni los datos existentes del usuario.
- **FR-031**: Con un proveedor externo, `findings_query` solo puede ejecutarse si el caso está
  autorizado como `fictional_case` y la consulta se limita a `origin=synthetic`; cualquier intento
  de consultar datos importados o mixtos MUST bloquear el turno con `external_tool_blocked` antes de
  ejecutar la herramienta y MUST sugerir Ollama. Nunca se envían filas Qualys ni resultados
  importados.
- **FR-032**: La autorización externa de 005 MUST limitarse a `public_corpus` o `fictional_case`;
  MUST NOT autorizar `private_case`.
- **FR-033**: La identidad del modelo MUST registrar el digest local cuando exista y el identificador
  o versión externa observada cuando corresponda; MUST NOT inventar un digest externo.

### Key Entities

- **ProviderProfile**: proveedor activo, identificador de modelo, límites, tiempos de espera,
  presupuesto y referencia a la credencial; nunca contiene la credencial en claro.
- **GenerationRecord**: proveedor, modelo, digest o versión, límites, duración, uso y resultado de una
  ejecución.
- **UsageRecord**: tokens de entrada, salida y caché reportados, origen de la medición y estado
  (`observed`, `estimated`, `unknown`).
- **CostTariff**: precios de entrada, salida y caché por proveedor y modelo, moneda, fecha de
  vigencia, fuente y versión.
- **BudgetLedger**: saldo autorizado, reservas, liquidaciones, intentos y estado de reconciliación.
- **ExternalProcessingAuthorization**: caso, alcance permitido, política, identidad declarada, fecha
  de autorización y fecha de revocación.
- **ProviderComparison**: conjunto de preguntas, proveedor, métricas de tiempo, citas, estructura,
  recomendaciones y costo, con resultados medidos separados de expectativas.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Con credenciales y presupuesto disponibles, las mismas diez preguntas públicas o
  ficticias producen respuestas estructuradas válidas y citas verificables en los tres proveedores.
- **SC-002**: El 100 % de los intentos de enviar contenido privado sin autorización se bloquean antes
  de la llamada; el 100 % de los registros Qualys permanece fuera de cualquier proveedor externo.
- **SC-003**: Ninguna prueba de escaneo encuentra una credencial en logs, SQLite, trazas, respuestas,
  capturas ni mensajes de error.
- **SC-004**: Toda llamada externa registra uso y costo, o `unknown` con motivo; el presupuesto
  bloquea el 100 % de las llamadas que exceden el saldo.
- **SC-005**: La regresión local de Ollama conserva el comportamiento actual y pasa sin cambios
  funcionales.
- **SC-006**: La comparación reproducible reporta tiempo, citas, estructura, recomendaciones y costo
  por proveedor, con mediciones y expectativas separadas.

## Assumptions

- El presupuesto externo no está aprobado; esta preparación no ejecuta llamadas pagadas.
- Ollama sigue siendo el proveedor predeterminado y el único obligatorio para la integración local.
- Los identificadores verificados el 2026-11-22 son `claude-haiku-5-5` y `deepseek-flash`; MUST
  revalidarse al implementar y antes de aceptar porque precios y modelos cambian.
- Claude Haiku 5.5 usa un tokenizador más nuevo; el mismo texto puede contar hasta ~30 % más tokens
  que en generaciones anteriores.
- DeepSeek Flash tiene modo de razonamiento activado por defecto; la implementación decidirá el modo
  por defecto para conservar latencia y estructura, y lo documentará.
- La autorización externa por caso es un registro local explícito; no se infiere de una credencial ni
  de una configuración global.
- No se construye una pantalla de administración en esta funcionalidad.
- La comparación de proveedores es una evaluación pequeña y reproducible, no un benchmark
  estadístico.
