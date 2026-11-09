# Feature Specification: Importación de hallazgos Qualys y consulta con findings_query

**Feature Branch**: `002-qualys-findings-import`

**Created**: 2026-11-09

**Status**: Draft

**Input**: Importar el CSV filtrado de Qualys ya verificado (662 registros, 41 columnas, UTF-8 con
BOM, coma y campos multilínea), previsualizarlo, confirmarlo en el caso activo y consultarlo mediante
`findings_query`, conservando aislamiento, procedencia, presupuesto, evidencia histórica y protección
de datos del primer incremento.

## Contexto verificado del insumo

Estos datos son agregados de verificación, no filas del archivo:

- CSV filtrado: 1.355.926 bytes; SHA-256
  `f55ab562f2fe5a41654f5c256a0ba9a281b446ebbe608514e06d0100af934e34`.
- Manifiesto: SHA-256 de salida `f55ab562f2fe5a41654f5c256a0ba9a281b446ebbe608514e06d0100af934e34`;
  662 registros; 41 columnas; UTF-8 con BOM; coma; encabezado en el primer registro; multilínea
  conservado; sin preámbulo, pie ni registros `Fixed`.
- Estados: `Active` 631, `New` 10, `Re-Opened` 21.
- Columnas: `IP`, `Network`, `DNS`, `NetBIOS`, `Tracking Method`, `OS`, `IP Status`, `QID`, `Title`,
  `Vuln Status`, `Type`, `Severity`, `Port`, `Protocol`, `FQDN`, `SSL`, `First Detected`,
  `Last Detected`, `Times Detected`, `Date Last Fixed`, `First Reopened`, `Last Reopened`,
  `Times Reopened`, `CVE ID`, `Vendor Reference`, `Bugtraq ID`, `Threat`, `Impact`, `Solution`,
  `Exploitability`, `Associated Malware`, `Results`, `PCI Vuln`, `Ticket State`, `Instance`,
  `Category`, `Associated Tags`, `QDS`, `ARS`, `ACS`, `TruRisk Score`.
- `Severity` contiene valores enteros 1–5. `QDS`, `ARS`, `ACS` y `TruRisk Score` son métricas del
  proveedor, no CVSS.
- `First Detected`, `Last Detected`, `Date Last Fixed`, `First Reopened` y `Last Reopened` usan el
  patrón `MM/DD/YYYY HH:MM:SS`; la zona horaria no está declarada.
- `CVE ID` usa una lista separada por comas; 179 registros tienen más de un CVE. No hay filas
  exactamente duplicadas.
- La clave `QID + IP + Port + Protocol` produce 10 grupos con más de una fila y 11 filas adicionales;
  no es suficiente por sí sola para identificar un hallazgo. `QID + IP + Port + Protocol +
  First Detected` es única en este archivo, pero su estabilidad entre archivos no está demostrada.
- `Port` y `Protocol` están vacíos en 459 registros; `CVE ID` en 388; `Results` en 2. `Results`
  contiene campos multilínea en 305 registros.
- El producto no debe tratar los 662 registros como 662 hallazgos únicos hasta resolver la identidad.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Importar el CSV filtrado y consultar sus hallazgos (Priority: P1)

Una persona autorizada abre un caso, carga el CSV filtrado y su manifiesto, revisa una vista previa
con cantidades y validaciones, confirma la importación y luego consulta los hallazgos del caso
mediante `findings_query`. La consulta devuelve conteos y grupos reproducibles, con la procedencia de
la importación y sin mezclar silenciosamente datos sintéticos e importados.

**Why this priority**: es el recorrido mínimo que entrega valor: los datos reales del caso pasan a
ser consultables con el mismo control de alcance y evidencia que ya existe.

**Independent Test**: con el CSV filtrado y su manifiesto, un caso vacío muestra la vista previa
esperada, confirma la importación y responde una consulta de conteo por activo con cifras que
coinciden con un recálculo independiente sobre los registros importados.

**Acceptance Scenarios**:

1. **Given** un caso autorizado sin hallazgos importados, **When** la persona carga el CSV y el
   manifiesto y confirma, **Then** el sistema registra una importación con hash, fecha, versión del
   adaptador, cantidades y estado, y los hallazgos quedan asociados solo a ese caso.
2. **Given** una importación confirmada, **When** la persona pregunta por conteos agrupados por
   activo, **Then** `findings_query` responde con el total y los grupos calculados sobre los
   registros importados, identificando su origen e importación.
3. **Given** el mismo CSV ya importado, **When** se vuelve a cargar y confirmar, **Then** no se crean
   hallazgos, CVEs ni conteos duplicados y la importación se informa como idempotente.

---

### User Story 2 - Reimportar y actualizar sin duplicar (Priority: P2)

Una persona carga un archivo posterior que contiene hallazgos ya registrados y hallazgos nuevos. El
sistema reconcilia la identidad, actualiza solo lo que corresponde y muestra cuántos registros fueron
nuevos, actualizados, sin cambios, rechazados o ambiguos. Nunca descarta filas en silencio.

**Why this priority**: el valor operativo depende de que las reimportaciones no inflen los conteos ni
pierdan cambios de estado.

**Independent Test**: importar el archivo base, reimportar el mismo archivo y luego un archivo
sintético con un registro conocido modificado y uno nuevo; los conteos no se duplican y el resumen
distingue nuevos, actualizados y ambiguos.

**Acceptance Scenarios**:

1. **Given** una importación previa, **When** se reimporta el mismo contenido, **Then** el resumen
   informa cero nuevos y cero actualizados, y los conteos no cambian.
2. **Given** una importación previa, **When** un archivo posterior contiene un registro con la misma
   identidad confirmada y un estado o detección distinta, **Then** el sistema actualiza el registro
   existente, conserva su historia y no incrementa el total de hallazgos.
3. **Given** un archivo posterior con una fila cuya identidad es ambigua, **When** se previsualiza,
   **Then** la fila se marca como ambigua y no se incorpora hasta que exista una decisión explícita.

---

### User Story 3 - Consultar con procedencia y evidencia histórica (Priority: P3)

Una persona consulta hallazgos sintéticos e importados en el mismo caso y necesita saber qué origen
tiene cada cifra. La respuesta y la ejecución conservan la importación, los filtros, los totales y la
distinción entre resultado histórico y detalle recalculado.

**Why this priority**: la trazabilidad y la separación de orígenes evitan conclusiones erróneas y
permiten auditar el resultado.

**Independent Test**: con un caso que contiene datos sintéticos e importados, una consulta sin filtro
de origen muestra el desglose por origen; una consulta filtrada devuelve solo el origen solicitado;
la ejecución histórica conserva el resumen original.

**Acceptance Scenarios**:

1. **Given** un caso con hallazgos sintéticos e importados, **When** se consulta sin filtro de origen,
   **Then** el resultado informa total y desglose por origen, sin presentar una cifra única sin
   etiqueta.
2. **Given** una consulta con detalle limitado, **When** se abre la ejecución, **Then** el resumen
   histórico conserva filtros, totales, grupos, importaciones y truncamiento; el detalle recalculado
   se etiqueta como consulta actual.
3. **Given** una consulta sin coincidencias, **When** se muestra el resultado, **Then** se declara que
   no hay hallazgos registrados para esa consulta y no se afirma ausencia de vulnerabilidades.

---

### Edge Cases

- Archivo con BOM, comas dentro de comillas, comillas escapadas o campos multilínea.
- Encabezado ausente, desordenado, con columnas faltantes o con columnas adicionales.
- Archivo con una sola fila, sin filas, con filas vacías o con más de 10.000 registros.
- Estado `Fixed` o un estado desconocido en un archivo posterior.
- Severidad numérica fuera de 1–5, QID no numérico, fecha inválida o CVE con formato inválido.
- `Port` o `Protocol` vacíos; `CVE ID` vacío; `Results` multlínea o vacío.
- Varias filas con la misma combinación `QID + IP + Port + Protocol`.
- Un hallazgo con muchos CVE; un CVE repetido en varios hallazgos.
- Reimportación del mismo archivo, archivo posterior con un registro conocido y archivo con un
  registro nuevo.
- Importación interrumpida antes de confirmar, fallo durante la confirmación o reintento posterior.
- Caso A intenta consultar o confirmar una importación del caso B.
- Caso con datos sintéticos e importados y consulta sin filtro de origen.
- Resultado vacío, detalle truncado y recálculo posterior de detalle.
- Intento de enviar contenido del CSV a trazas externas o a registros no autorizados.
- Archivo que supera el límite de tamaño, filas o longitud de campo.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema MUST asociar cada importación al caso autorizado resuelto por el servidor;
  el CSV no puede declarar ni cambiar el caso.
- **FR-002**: El sistema MUST aceptar únicamente el formato del archivo suministrado: UTF-8 con BOM,
  coma, encabezado en el primer registro, 41 columnas en el orden verificado y campos multilínea.
- **FR-003**: El sistema MUST verificar el hash SHA-256, el tamaño, la cantidad de registros, las 41
  columnas y los conteos de estado contra el manifiesto asociado antes de confirmar; una diferencia
  MUST rechazar la importación con un motivo comprensible.
- **FR-004**: El sistema MUST leer comas, comillas, comillas escapadas y campos multilínea sin
  convertir una fila en varias ni perder contenido.
- **FR-005**: El sistema MUST clasificar las columnas en obligatorias, opcionales y desconocidas. Para
  este archivo, `IP`, `QID`, `Title`, `Vuln Status`, `Severity`, `First Detected` y `Last Detected`
  son obligatorias; `CVE ID`, `Port`, `Protocol`, `Results` y los identificadores de red son
  opcionales; una columna faltante, adicional o reordenada MUST rechazar el archivo.
- **FR-006**: El sistema MUST conservar, para cada fila, los valores originales de las 41 columnas y
  una representación normalizada de los campos que se consultan; la normalización no puede destruir
  el valor original.
- **FR-007**: El sistema MUST tratar la `Severity` numérica como severidad de Qualys, no como CVSS,
  QDS, TruRisk ni prioridad P1–P4. La semántica de los valores 1–5 y su exposición o filtro quedan
  sujetas a la clarificación registrada al final de esta especificación. [NEEDS CLARIFICATION: ¿qué
  significan los valores 1–5 y cómo deben exponerse y filtrarse en findings_query?]
- **FR-008**: El sistema MUST aceptar únicamente los estados `Active`, `New` y `Re-Opened` para este
  incremento. `Fixed` y cualquier estado desconocido MUST rechazarse de forma explícita; si un
  archivo posterior los contiene, el resumen MUST informarlos sin incorporarlos en silencio.
- **FR-009**: El sistema MUST validar valores ausentes, tipos, longitudes, QID numérico, severidad
  entera, fechas y CVEs; cada fila inválida MUST tener número de fila y motivo, y no puede
  descartarse sin registro.
- **FR-010**: La vista previa MUST mostrar filas detectadas, válidas, inválidas, rechazadas y posibles
  duplicados, además de los conteos por estado y la comparación con el manifiesto, antes de escribir
  datos.
- **FR-011**: El sistema MUST exigir una confirmación explícita después de la vista previa; ninguna
  fila puede incorporarse antes de esa confirmación.
- **FR-012**: La política por defecto MUST ser rechazo completo ante un error estructural, de
  encabezado, de hash o de cantidad. La aceptación parcial solo puede existir si la persona la elige
  explícitamente y ve las filas omitidas, sus motivos y los totales resultantes.
- **FR-013**: El sistema MUST definir una identidad de hallazgo antes de contar o deduplicar. La
  evidencia de este archivo muestra que `QID + IP + Port + Protocol` no es suficiente; la identidad
  definitiva entre archivos queda sujeta a la clarificación registrada al final. [NEEDS CLARIFICATION:
  ¿cuál es la identidad estable de un hallazgo entre archivos?]
- **FR-014**: El sistema MUST marcar como posibles duplicados las filas que compartan la identidad
  candidata o una combinación parcial relevante; no puede eliminarlas solo por compartir IP, QID,
  puerto y protocolo.
- **FR-015**: El sistema MUST ser idempotente para el mismo contenido: mismo hash de archivo y misma
  versión de adaptador no crean nuevos hallazgos, CVEs, grupos ni conteos.
- **FR-016**: El sistema MUST definir el comportamiento de un archivo posterior que contiene
  hallazgos ya registrados: nuevos, actualizados, sin cambios, ambiguos y rechazados deben informarse
  por separado. La política exacta de actualización queda sujeta a la clarificación registrada al
  final. [NEEDS CLARIFICATION: ¿un hallazgo ya registrado se actualiza en el mismo registro, se
  conserva como versión histórica o se rechaza como duplicado?]
- **FR-017**: El sistema MUST conservar las fechas originales y una forma normalizada del patrón
  `MM/DD/YYYY HH:MM:SS`; no puede convertir a UTC ni inventar una zona horaria no declarada.
- **FR-018**: El sistema MUST dividir `CVE ID` por comas, validar el formato `CVE-AAAA-NNNN`, conservar
  todos los CVE de un hallazgo y contabilizar el hallazgo una sola vez aunque tenga varios CVE.
- **FR-019**: Cada importación MUST registrar caso, hash del CSV, hash del manifiesto, fecha de
  importación, versión del adaptador, estado, cantidades y errores; cada hallazgo importado MUST
  referenciar su importación y conservar procedencia.
- **FR-020**: Un fallo o interrupción MUST dejar un estado de importación explícito; el reintento MUST
  ser seguro y no puede duplicar filas ya confirmadas.
- **FR-021**: El sistema MUST imponer límites explícitos y configurables de tamaño de archivo, número
  de filas, longitud de campo y cantidad de CVE por hallazgo; un archivo que los exceda MUST
  rechazarse con el límite aplicado. Como referencia para este incremento: 10 MiB, 10.000 filas,
  20.000 caracteres por campo y 1.000 CVE por hallazgo.
- **FR-022**: Los registros importados MUST alimentar `findings_query` y no deben convertirse en
  fragmentos del RAG documental ni en citas.
- **FR-023**: `findings_query` MUST conservar el alcance impuesto por el servidor, el esquema estricto,
  la ausencia de `case_id` controlado por el modelo y la prohibición de SQL o tablas arbitrarias.
- **FR-024**: Los resultados de `findings_query` MUST identificar el origen (`synthetic` o `imported`)
  y, para los importados, la importación y su procedencia. Si el caso contiene ambos orígenes, el
  resultado MUST incluir un desglose por origen y no puede presentar una mezcla silenciosa.
- **FR-025**: Los filtros, totales, grupos, origen, importaciones y truncamiento MUST ser
  reproducibles y conservarse en el resumen histórico de la ejecución.
- **FR-026**: Si la ejecución recalcula el detalle, la interfaz MUST distinguirlo del resultado
  histórico original y etiquetarlo como consulta actual.
- **FR-027**: Un resultado vacío MUST declarar que no hay hallazgos registrados para esa consulta y no
  puede presentarse como ausencia de vulnerabilidades ni riesgo bajo.
- **FR-028**: La interfaz MUST ofrecer un punto de entrada de importación dentro del caso, separado de
  la carga de PDF o Markdown, con formulario, validación, vista previa, confirmación, resumen,
  errores y reintento; no se añade un dashboard ni se rediseña la aplicación.
- **FR-029**: La interfaz MUST conservar los recursos locales, el diseño adaptable, la navegación
  existente, los indicadores de carga y la prevención de doble envío.
- **FR-030**: El CSV real, sus filas, IP, nombres de activos, resultados y contenido no pueden
  copiarse al repositorio, fixtures, logs, respuestas externas ni trazas de LangSmith. La operación
  de importación es local; la traza externa solo puede registrar metadatos acotados como hash,
  cantidades, estado e identificador de importación.
- **FR-031**: Las pruebas y fixtures MUST usar datos sintéticos representativos del formato, con BOM,
  comas, comillas, multilínea, estados, CVEs múltiples y errores controlados; no pueden derivarse del
  archivo real.
- **FR-032**: El sistema MUST informar que el soporte se limita al formato suministrado y no debe
  afirmar compatibilidad con cualquier CSV de Qualys, otros reportes, Tenable o conectores API.
- **FR-033**: La importación y la consulta MUST conservar el aislamiento, la memoria, las citas, la
  revisión humana por cita, el presupuesto de contexto y la evidencia histórica ya existentes.
- **FR-034**: Una cita no revisada MUST seguir pendiente de respaldo semántico; la importación de
  hallazgos no puede aprobar citas ni convertir un control automático en revisión humana.
- **FR-035**: El sistema MUST impedir que una importación de un caso sea visible o confirmable desde
  otro caso, y MUST devolver un resultado de no encontrado para recursos ajenos.

### Key Entities

- **Importación de hallazgos**: lote asociado a un caso, con hash del CSV, hash del manifiesto, fecha,
  versión del adaptador, estado, cantidades y errores.
- **Hallazgo importado**: registro de un caso con identidad candidata, valores originales y
  normalizados, estado, severidad numérica, métricas del proveedor, fechas, activo y procedencia.
- **CVE del hallazgo**: identificador público asociado a un hallazgo; varios CVE pertenecen al mismo
  hallazgo y no multiplican los conteos.
- **Caso**: alcance autorizado que contiene documentos, conversación, hallazgos sintéticos e
  importados.
- **Resultado de consulta**: totales, grupos, origen, importaciones, truncamiento y detalle, con
  distinción entre resumen histórico y recálculo actual.
- **Ejecución y herramienta**: registro histórico de la consulta, sus filtros, procedencia y estado.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Con el CSV filtrado y su manifiesto, la vista previa informa 662 filas detectadas, 41
  columnas, 631 `Active`, 10 `New`, 21 `Re-Opened` y coincidencia de hash con el manifiesto.
- **SC-002**: La confirmación incorpora exactamente las filas válidas y muestra por separado las
  inválidas o rechazadas; ninguna fila desaparece sin motivo y sin conteo.
- **SC-003**: Reimportar el mismo archivo produce cero hallazgos nuevos, cero CVEs nuevos y cero
  cambios en los conteos consultados.
- **SC-004**: La vista previa identifica los 10 grupos y 11 filas adicionales que aparecen al usar
  `QID + IP + Port + Protocol` como clave, y no los elimina silenciosamente.
- **SC-005**: Un hallazgo con varios CVE cuenta una sola vez; una consulta filtrada por uno de sus
  CVE devuelve el hallazgo y no una fila por CVE.
- **SC-006**: Un archivo posterior con un hallazgo conocido y uno nuevo informa, respectivamente,
  actualización y alta, sin aumentar el total por el registro conocido. Si la identidad no está
  confirmada, el sistema bloquea la incorporación ambigua con una decisión explícita.
- **SC-007**: Una consulta en un caso con datos sintéticos e importados devuelve un desglose por
  origen y jamás una cifra única sin etiqueta.
- **SC-008**: El 100 % de los hallazgos importados conserva importación, hash, fecha, versión del
  adaptador y procedencia consultables.
- **SC-009**: Una consulta de un caso no devuelve hallazgos, importaciones ni mensajes de otro caso;
  un recurso ajeno responde no encontrado.
- **SC-010**: Un resultado vacío informa «sin hallazgos registrados para esta consulta» y no afirma
  ausencia de vulnerabilidades.
- **SC-011**: La interfaz completa el recorrido seleccionar caso → cargar CSV → previsualizar →
  confirmar → consultar, conserva los indicadores de carga y no duplica el envío.
- **SC-012**: Los logs, respuestas y trazas externas no contienen filas del CSV, IP, nombres de
  activos, resultados ni contenido real; solo metadatos acotados.
- **SC-013**: El sistema rechaza con un motivo comprensible un archivo que supere los límites de
  tamaño, filas, campo o CVE, sin dejar una importación parcial silenciosa.
- **SC-014**: Los 662 registros no se presentan como 662 hallazgos únicos hasta que la identidad esté
  confirmada; la interfaz y el resumen usan «registros» y muestran la política aplicada.

## Assumptions

- El único insumo de este incremento es el CSV filtrado y verificado descrito arriba; no se soportan
  reportes con preámbulo/pie, otros formatos de Qualys, Tenable ni conectores API.
- El archivo se procesa localmente; el manifiesto se usa para verificar integridad y cantidades en la
  aceptación. El producto calcula y muestra hash, bytes y cantidades, y conserva el hash del manifiesto
  cuando se le proporciona.
- La política por defecto es rechazo completo; la aceptación parcial es una elección explícita.
- Las fechas se conservan como `MM/DD/YYYY HH:MM:SS`; la zona horaria es desconocida y no se inventa.
- La severidad numérica de Qualys no se traduce a CVSS, QDS, TruRisk ni P1–P4.
- Los datos reales no se usan en fixtures ni se envían a servicios externos.
- La revisión humana por cita y las validaciones recomendadas del primer incremento no bloquean este
  trabajo.
- Se conserva la interfaz existente y sus recursos locales; no se introduce un dashboard ni se
  rediseña la aplicación.

## Clarifications needed

Las siguientes decisiones de negocio no pueden resolverse con los datos disponibles:

1. **Identidad estable**: ¿la identidad de un hallazgo entre archivos debe ser
   `QID + IP + Port + Protocol + First Detected`, otra combinación de columnas, o un identificador
   estable que no está en este CSV? El archivo no demuestra que `First Detected` sea inmutable ante
   reaperturas o cambios de estado.
2. **Actualización posterior**: cuando un archivo posterior contiene un hallazgo ya registrado, ¿debe
   actualizarse en el mismo registro, conservarse como una nueva versión histórica, o rechazarse como
   duplicado? ¿Qué transición corresponde a `Fixed` o a un estado desconocido?
3. **Severidad**: ¿qué significan los valores numéricos 1–5 de `Severity` y cómo deben exponerse y
   filtrarse en `findings_query`? ¿Se mantiene el filtro por etiqueta existente, se agrega un filtro
   numérico, o ambos?

Hasta resolverlas, la especificación exige que el sistema no invente equivalencias, no descarte filas
ambiguas y bloquee la confirmación cuando la identidad o la actualización no estén definidas.
