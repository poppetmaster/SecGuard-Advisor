# Feature Specification: Importación de hallazgos Qualys y consulta con findings_query

**Feature Branch**: `002-qualys-findings-import`

**Created**: 2026-11-09

**Status**: Draft

**Input**: Importar el CSV filtrado de Qualys ya verificado, conservarlo como instantánea del caso,
previsualizarlo, confirmarlo y consultarlo mediante `findings_query` con severidad, estado,
indicadores de explotabilidad/malware, snapshots y procedencia, sin mezclar orígenes ni convertir los
registros en documentos RAG.

## Contexto verificado del insumo

Datos agregados de verificación, sin filas ni valores de activos:

- CSV filtrado: 1.355.926 bytes; SHA-256
  `f55ab562f2fe5a41654f5c256a0ba9a281b446ebbe608514e06d0100af934e34`.
- Manifiesto: SHA-256 de salida `f55ab562f2fe5a41654f5c256a0ba9a281b446ebbe608514e06d0100af934e34`;
  662 registros; 41 columnas; UTF-8 con BOM; coma; encabezado en el primer registro; multilínea
  conservado; sin preámbulo, pie ni registros `Fixed`.
- Estados: `Active` 631, `New` 10, `Re-Opened` 21, `Fixed` 0.
- Columnas: `IP`, `Network`, `DNS`, `NetBIOS`, `Tracking Method`, `OS`, `IP Status`, `QID`, `Title`,
  `Vuln Status`, `Type`, `Severity`, `Port`, `Protocol`, `FQDN`, `SSL`, `First Detected`,
  `Last Detected`, `Times Detected`, `Date Last Fixed`, `First Reopened`, `Last Reopened`,
  `Times Reopened`, `CVE ID`, `Vendor Reference`, `Bugtraq ID`, `Threat`, `Impact`, `Solution`,
  `Exploitability`, `Associated Malware`, `Results`, `PCI Vuln`, `Ticket State`, `Instance`,
  `Category`, `Associated Tags`, `QDS`, `ARS`, `ACS`, `TruRisk Score`.
- `Severity` contiene enteros 1–5. `QDS`, `ARS`, `ACS` y `TruRisk Score` son métricas del proveedor,
  no CVSS.
- Fechas con patrón `MM/DD/YYYY HH:MM:SS`; zona horaria no declarada.
- `CVE ID` usa una lista separada por comas; 179 registros tienen más de un CVE.
- No hay filas exactamente duplicadas. `QID + IP + Port + Protocol` produce 10 grupos con más de una
  fila y 11 filas adicionales; no se usa como identidad de vulnerabilidad.
- `Port` y `Protocol` están vacíos en 459 registros; `CVE ID` en 388; `Results` en 2.
- `Exploitability` no está vacío en 129 registros. `Associated Malware` no está vacío en 8.
- Las estructuras observadas de `Exploitability` usan bloques con `Source`, `Reference`,
  `Description` y `Link`. `Associated Malware` usa bloques con `Malware ID`, `Type`, `Platform`,
  `Link`, `Risk`, `Source` y `Aliases`.
- Con la regla propuesta, 8 registros tienen ambos indicadores positivos (7 `Active`, 1 `New`);
  121 tienen solo explotabilidad positiva; 0 tienen solo malware positivo; 533 y 654 quedan
  indeterminados por campo vacío. Estos totales son agregados, no filas.
- Los 662 registros no se presentan como 662 vulnerabilidades únicas.

## Clarifications

### Session 2026-11-09

- Q: ¿Existe una identidad estable de vulnerabilidad entre reportes? → A: No se afirma. Cada registro
  pertenece a una instantánea concreta y conserva su posición lógica. El mismo hash de archivo en el
  mismo caso no duplica; un archivo distinto crea una instantánea nueva. Las filas que comparten
  QID, IP, puerto y protocolo se conservan y se informan como posible repetición.
- Q: ¿Cómo se consultan y conservan las importaciones posteriores? → A: Se conservan instantáneas
  confirmadas independientes. `findings_query` consulta por defecto la última confirmada según la
  secuencia local y permite seleccionar una anterior, mostrando siempre la instantánea consultada.
  No se suman instantáneas silenciosamente ni se interpreta una ausencia como remediación.
- Q: ¿Qué escala de severidad se usa? → A: Convención de presentación del proyecto: 1 Informativa,
  2 Baja, 3 Media, 4 Alta, 5 Crítica. Se conservan valor original, nivel validado, etiqueta y política
  de correspondencia. No es CVSS, QDS, TruRisk ni P1–P4.
- Q: ¿Qué estados se admiten? → A: `Active`, `New`, `Re-Opened` y `Fixed`. Los desconocidos se
  conservan con su valor original, se identifican como «Revisión manual», aparecen en vista previa y
  resumen, no se convierten y no bloquean la importación por sí solos.
- Q: ¿Cómo se determina la prioridad por explotabilidad y malware? → A: Solo se activa la bandera
  conjunta cuando ambos campos tienen evidencia positiva. Se conservan indicadores separados, valores
  originales, evaluación, motivo y versión de regla. Un campo vacío o indeterminado no es positivo.
- Q: ¿El manifiesto es obligatorio en cada importación futura? → A: No. Se usa para verificar el
  insumo de referencia; el producto calcula hash, bytes y filas y conserva el hash del manifiesto
  cuando se aporta.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Importar una instantánea y consultar sus registros (Priority: P1)

Una persona autorizada abre un caso, carga el CSV filtrado y su manifiesto de referencia, revisa la
vista previa, confirma la importación y consulta los registros mediante `findings_query`. La consulta
usa por defecto la última instantánea confirmada y muestra siempre cuál consultó.

**Why this priority**: es el recorrido mínimo que hace consultables los datos reales del caso sin
mezclarlos con documentos ni con otras importaciones.

**Independent Test**: con el CSV filtrado y su manifiesto, un caso vacío muestra la vista previa
esperada, confirma la importación y responde una consulta de conteo por activo con cifras que
coinciden con un recálculo independiente sobre la instantánea.

**Acceptance Scenarios**:

1. **Given** un caso autorizado sin importaciones, **When** la persona carga el CSV y el manifiesto y
   confirma, **Then** el sistema registra una instantánea con hash, fecha, versión del adaptador,
   cantidades y estado, y los registros quedan asociados solo a ese caso.
2. **Given** una instantánea confirmada, **When** la persona pregunta por conteos agrupados por
   activo, **Then** `findings_query` responde con el total y los grupos de esa instantánea,
   identificando snapshot, origen e importación.
3. **Given** el mismo archivo ya confirmado en el mismo caso, **When** se vuelve a cargar y confirmar,
   **Then** no se crean registros nuevos ni se alteran los conteos y la operación se informa como
   idempotente.

---

### User Story 2 - Conservar y elegir instantáneas (Priority: P2)

Una persona importa un archivo distinto y necesita comparar sin que el sistema sume registros de
instantáneas diferentes. Puede consultar la última instantánea o seleccionar una anterior; la
interfaz y el resultado indican siempre qué instantánea se usó. La ausencia de un registro en una
instantánea posterior no se interpreta como remediación.

**Why this priority**: sin snapshots explícitos, dos archivos distintos inflarían los conteos o
borrarían la historia.

**Independent Test**: importar el archivo base y luego un archivo sintético distinto; confirmar que
existen dos instantáneas, que la consulta por defecto usa la segunda y que seleccionar la primera
devuelve sus propios totales sin sumarlos.

**Acceptance Scenarios**:

1. **Given** dos instantáneas confirmadas, **When** se consulta sin selección explícita, **Then** se
   usa la última confirmada y el resultado muestra su identificador y secuencia.
2. **Given** dos instantáneas confirmadas, **When** se selecciona una anterior, **Then** el resultado
   usa solo esa instantánea y muestra la selección.
3. **Given** una instantánea posterior sin un registro de la anterior, **When** se consulta, **Then**
   el sistema no lo presenta como corregido ni como remediación.

---

### User Story 3 - Consultar estado, severidad e indicadores con procedencia (Priority: P3)

Una persona consulta registros importados y sintéticos en el mismo caso y necesita distinguir origen,
estado, severidad, prioridad conjunta e indicadores. La interfaz muestra el motivo de prioridad y no
solo un color. Los conteos son recalculables y conservan la procedencia histórica.

**Why this priority**: la prioridad operativa y la separación de escalas evitan conclusiones erróneas
y permiten auditar cada cifra.

**Independent Test**: con un caso que contiene datos sintéticos e importados, una consulta sin filtro
de origen muestra el desglose por origen; una consulta filtrada devuelve solo el origen solicitado;
un registro con ambos indicadores positivos muestra la bandera y su motivo; uno con un solo indicador
muestra el indicador sin la bandera conjunta.

**Acceptance Scenarios**:

1. **Given** un caso con hallazgos sintéticos e importados, **When** se consulta sin filtro de origen,
   **Then** el resultado informa totales por origen y no presenta una cifra única sin etiqueta.
2. **Given** un registro importado con ambos indicadores positivos, **When** se consulta, **Then** se
   muestra la bandera «Prioritaria: explotabilidad y malware» con motivo y versión de regla.
3. **Given** un registro con un solo indicador positivo, **When** se consulta, **Then** se muestra
   ese indicador, sin atribuirle la bandera conjunta.
4. **Given** un registro `Fixed` con ambos indicadores positivos, **When** se consulta, **Then** se
   informa como antecedente prioritario reportado, no como remediación pendiente.

---

### Edge Cases

- Archivo con BOM, comas dentro de comillas, comillas escapadas o campos multilínea.
- Encabezado ausente, desordenado, con columnas faltantes o con columnas adicionales.
- Archivo sin filas, con filas vacías, con una sola fila o con más de 10.000 registros.
- Estado `Fixed` o un estado desconocido.
- `Severity` ausente, no numérica o fuera de 1–5.
- QID no numérico, fecha inválida o CVE con formato inválido.
- `Port` o `Protocol` vacíos; `CVE ID` vacío; `Results` multilínea o vacío.
- Varias filas con la misma combinación `QID + IP + Port + Protocol`.
- Un registro con muchos CVE; un CVE repetido en varios registros.
- Mismo archivo reimportado; archivo distinto con registros ya vistos.
- `Exploitability` vacío, con `N/A`, `None`, `No`, con una fuente reconocida o con estructura no
  reconocida.
- `Associated Malware` vacío, con `N/A`, con `Malware ID` real o con estructura no reconocida.
- Ambos indicadores positivos; solo uno positivo; ambos negativos/no informados; ambos indeterminados.
- `Fixed` con ambos indicadores positivos; estado desconocido con ambos indicadores positivos.
- Consulta de una instantánea anterior; ausencia de un registro en la instantánea más reciente.
- Caso con datos sintéticos e importados y filtro de severidad sin origen explícito.
- Importación interrumpida, fallo durante la confirmación o reintento.
- Caso A intenta consultar o confirmar una importación del caso B.
- Resultado vacío, detalle truncado y recálculo posterior de detalle.
- Archivo que supera los límites de tamaño, filas, campo o CVE.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema MUST asociar cada importación al caso autorizado resuelto por el servidor; el
  CSV no puede declarar ni cambiar el caso.
- **FR-002**: El sistema MUST aceptar únicamente el formato del archivo suministrado: UTF-8 con BOM,
  coma, encabezado en el primer registro, 41 columnas en el orden verificado y campos multilínea.
- **FR-003**: El sistema MUST calcular y registrar SHA-256, bytes y cantidad de filas del CSV; cuando
  se aporte el manifiesto de referencia, MUST comparar hash, bytes, filas, columnas y conteos de
  estado, y rechazar la importación si no coinciden. El manifiesto no es obligatorio para cada
  importación futura.
- **FR-004**: El sistema MUST leer comas, comillas, comillas escapadas y campos multilínea sin
  convertir una fila en varias ni perder contenido.
- **FR-005**: El sistema MUST clasificar las columnas en obligatorias, opcionales y desconocidas. Para
  este archivo, `IP`, `QID`, `Title`, `Vuln Status`, `Severity`, `First Detected` y `Last Detected`
  son obligatorias; `CVE ID`, `Port`, `Protocol`, `Results` y los identificadores de red son
  opcionales; una columna faltante, adicional o reordenada MUST rechazar el archivo.
- **FR-006**: El sistema MUST conservar, para cada fila, los valores originales de las 41 columnas y
  una representación normalizada de los campos que se consultan; la normalización no puede destruir
  el valor original.
- **FR-007**: El sistema MUST modelar cada importación como una instantánea independiente. Cada fila
  MUST pertenecer a una importación y conservar su posición lógica; el sistema no puede afirmar una
  identidad estable de vulnerabilidad entre reportes.
- **FR-008**: El mismo archivo, según su hash y dentro del mismo caso, MUST ser idempotente: no crea
  filas, CVEs, grupos ni conteos nuevos.
- **FR-009**: Un archivo distinto MUST crear una instantánea nueva; las instantáneas confirmadas MUST
  conservarse como evidencia histórica y no pueden sobrescribirse.
- **FR-010**: El sistema MUST conservar filas diferentes aunque compartan QID, IP, puerto y protocolo;
  MUST informar posibles repeticiones y no puede eliminar filas por esa coincidencia.
- **FR-011**: La vista previa MUST mostrar filas detectadas, válidas, inválidas estructurales,
  posibles repeticiones y conteos por estado, además de la comparación con el manifiesto cuando se
  aporte, antes de escribir datos.
- **FR-012**: El sistema MUST exigir una confirmación explícita después de la vista previa; ninguna
  fila puede incorporarse antes de esa confirmación.
- **FR-013**: La política por defecto MUST ser rechazo completo ante error estructural, de encabezado,
  hash o cantidad. La aceptación parcial solo puede existir si la persona la elige explícitamente y ve
  las filas omitidas, sus motivos y los totales resultantes. Ningún descarte puede ser silencioso.
- **FR-014**: El sistema MUST validar valores ausentes, tipos, longitudes, QID numérico, severidad
  entera, fechas y CVEs; cada fila inválida MUST tener número de fila y motivo.
- **FR-015**: El sistema MUST admitir los estados `Active`, `New`, `Re-Opened` y `Fixed`. Los estados
  desconocidos MUST conservarse con su valor original, identificarse como «Revisión manual»,
  aparecer en la vista previa y el resumen, y no bloquear la importación por sí solos. Errores
  estructurales que impiden interpretar la fila son distintos de un estado desconocido.
- **FR-016**: Las consultas MUST separar `pending_known` (`Active`, `New`, `Re-Opened`), `fixed`
  (`Fixed`) y `manual_review` (estado desconocido). El usuario puede consultar todos, pero los
  conteos MUST identificar el grupo aplicado; `Fixed` y «Revisión manual» no se presentan como
  vulnerabilidades activas.
- **FR-017**: El sistema MUST aplicar exactamente la convención de presentación del proyecto:
  1 Informativa, 2 Baja, 3 Media, 4 Alta, 5 Crítica. MUST conservar el valor original de `Severity`,
  el nivel numérico validado, la etiqueta del proyecto y el identificador de la política de
  correspondencia.
- **FR-018**: La escala 1–5 MUST NOT equipararse a CVSS, QDS, TruRisk ni prioridad P1–P4. Un valor
  ausente o fuera de 1–5 MUST recibir un tratamiento explícito de validación y no puede recibir una
  etiqueta inventada.
- **FR-019**: El sistema MUST conservar las fechas originales y una forma normalizada del patrón
  `MM/DD/YYYY HH:MM:SS`; no puede convertir a UTC ni inventar una zona horaria no declarada.
- **FR-020**: El sistema MUST dividir `CVE ID` por comas, validar el formato `CVE-AAAA-NNNN`, conservar
  todos los CVE de un registro y contabilizar el registro una sola vez aunque tenga varios CVE.
- **FR-021**: El sistema MUST evaluar `Exploitability` y `Associated Malware` por separado y conservar
  sus valores originales y una evaluación `positiva`, `negativa_no_informada` o `indeterminada`.
- **FR-022**: `Exploitability` MUST considerarse positiva cuando exista al menos un bloque
  estructurado con `Source` y `Reference`, `Link` o `Description` que no sea un marcador negativo
  (`N/A`, `None`, `No`, «no conocido», «no detectado»). Un campo vacío MUST ser indeterminado; un
  campo con solo marcadores negativos MUST ser negativo/no informado; una estructura no reconocida
  MUST ser indeterminada y requerir revisión manual.
- **FR-023**: `Associated Malware` MUST considerarse positiva cuando exista al menos un `Malware ID`
  distinto de `N/A`, `None` o `No`, acompañado de `Type`, `Risk` o `Link`. Un campo vacío MUST ser
  indeterminado; un campo con solo marcadores negativos MUST ser negativo/no informado; una estructura
  no reconocida MUST ser indeterminada y requerir revisión manual.
- **FR-024**: Una fila MUST marcarse «Prioritaria: explotabilidad y malware» solo cuando ambos campos
  tengan evaluación positiva. La bandera MUST conservar motivo y versión de regla. Un solo indicador
  positivo MUST conservarse y mostrarse, pero no atribuye la bandera conjunta.
- **FR-025**: La prioridad MUST distinguir contexto: `Active`, `New` o `Re-Opened` con ambos
  indicadores positivos es prioridad de atención; `Fixed` con ambos es antecedente prioritario
  reportado, sin presentarlo como remediación pendiente; estado desconocido con ambos es revisión
  manual del estado mostrando los indicadores.
- **FR-026**: La bandera de prioridad MUST NOT modificar la severidad, constituir P1–P4, demostrar
  explotación efectiva en la organización ni ejecutar remediación.
- **FR-027**: `findings_query` MUST consultar por defecto la última instantánea confirmada del caso
  según la secuencia local de confirmación y MUST permitir seleccionar una instantánea anterior.
  Siempre MUST mostrar la instantánea consultada. No puede sumar instantáneas silenciosamente.
- **FR-028**: `findings_query` MUST aceptar filtros de instantánea, estado, severidad numérica,
  etiqueta de severidad, prioridad, indicadores, activo, QID, CVE, origen, agrupación, detalle y
  límite, conservando el alcance y los filtros existentes compatibles.
- **FR-029**: Los resultados MUST distinguir origen `synthetic` e `imported`, incluir el desglose por
  origen y, para importados, snapshot e importación. MUST evitar conversiones silenciosas entre
  escalas de severidad.
- **FR-030**: Si el caso contiene ambos orígenes y se aplica un filtro de severidad sin origen
  explícito, el sistema MUST devolver un error de filtro ambiguo y pedir el origen, en lugar de
  convertir escalas o mezclar etiquetas.
- **FR-031**: Los filtros, totales, grupos, orígenes, snapshots, importaciones y truncamiento MUST
  conservarse en el resumen histórico de la ejecución y ser reproducibles.
- **FR-032**: Si la ejecución recalcula el detalle, la interfaz MUST distinguirlo del resultado
  histórico original y etiquetarlo como consulta actual.
- **FR-033**: Un resultado vacío MUST declarar que no hay registros para esa consulta y no puede
  presentarse como ausencia de vulnerabilidades ni riesgo bajo.
- **FR-034**: `findings_query` MUST conservar el alcance impuesto por el servidor, el esquema estricto,
  la ausencia de `case_id` controlado por el modelo y la prohibición de SQL o tablas arbitrarias.
- **FR-035**: Los registros importados MUST alimentar `findings_query` y no deben convertirse en
  fragmentos del RAG documental ni en citas.
- **FR-036**: La interfaz MUST ofrecer un punto de entrada de importación dentro del caso, separado de
  la carga de PDF o Markdown, con formulario, validación, vista previa, confirmación, resumen,
  errores y reintento; no se añade un dashboard ni se rediseña la aplicación.
- **FR-037**: La interfaz MUST mostrar snapshot, estado, severidad numérica y etiqueta, indicadores,
  bandera de prioridad y **motivo** de la prioridad; no puede comunicar la prioridad solo con color.
- **FR-038**: La interfaz MUST conservar recursos locales, diseño adaptable, navegación existente,
  indicadores de carga y prevención de doble envío.
- **FR-039**: El CSV real, sus filas, IP, nombres de activos, resultados, indicadores y contenido no
  pueden copiarse al repositorio, fixtures, logs, respuestas externas ni trazas de LangSmith. La
  operación de importación es local; la traza externa solo puede registrar metadatos acotados.
- **FR-040**: Las pruebas y fixtures MUST usar datos sintéticos representativos del formato, con BOM,
  comas, comillas, multilínea, estados, CVEs múltiples, valores `N/A`/`None`/`No`, campos vacíos,
  indicadores indeterminados y ambos/solo uno positivos. MUST incluir fixtures para `Fixed`, estados
  desconocidos y la regla conjunta.
- **FR-041**: El sistema MUST informar que el soporte se limita al formato suministrado y no debe
  afirmar compatibilidad con cualquier CSV de Qualys, otros reportes, Tenable o conectores API.
- **FR-042**: La importación y la consulta MUST conservar el aislamiento, la memoria, las citas, la
  revisión humana por cita, el presupuesto de contexto y la evidencia histórica existentes.
- **FR-043**: Una cita no revisada MUST seguir pendiente de respaldo semántico; la importación de
  hallazgos no puede aprobar citas ni convertir un control automático en revisión humana.
- **FR-044**: El sistema MUST impedir que una importación de un caso sea visible o confirmable desde
  otro caso y MUST devolver no encontrado para recursos ajenos.
- **FR-045**: Cada importación MUST registrar caso, hash, bytes, filas, fecha, versión del adaptador,
  versión de la política de severidad, versión de la regla de prioridad, estado, cantidades y errores;
  cada fila MUST referenciar su importación y su posición lógica.

### Key Entities

- **Instantánea de importación**: lote inmutable asociado a un caso, con hash, bytes, filas, fecha,
  versión del adaptador, políticas, estado, cantidades y errores.
- **Fila de instantánea**: registro de una importación con posición lógica, valores originales y
  normalizados, estado, severidad, indicadores, prioridad, activo, CVEs y procedencia.
- **CVE del registro**: identificador público asociado a una fila; varios CVE no multiplican conteos.
- **Caso**: alcance autorizado que contiene documentos, conversación, hallazgos sintéticos e
  instantáneas importadas.
- **Selección de consulta**: snapshot elegido o último confirmado, estado, severidad, prioridad,
  indicadores, activo y demás filtros aplicados.
- **Resultado de consulta**: totales, grupos, origen, snapshot, importaciones, truncamiento y detalle,
  con distinción entre resumen histórico y recálculo actual.
- **Ejecución y herramienta**: registro histórico de la consulta, sus filtros, procedencia y estado.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Con el CSV filtrado y su manifiesto, la vista previa informa 662 filas, 41 columnas,
  631 `Active`, 10 `New`, 21 `Re-Opened`, 0 `Fixed` y coincidencia de hash con el manifiesto.
- **SC-002**: La confirmación incorpora exactamente las filas válidas y muestra por separado las
  inválidas estructurales; ninguna fila desaparece sin motivo y sin conteo.
- **SC-003**: Reimportar el mismo archivo en el mismo caso produce cero filas nuevas y cero cambios en
  los conteos.
- **SC-004**: Importar un archivo distinto crea una instantánea nueva; la anterior se conserva; la
  consulta por defecto usa la última y la selección de la anterior devuelve sus propios totales sin
  sumarlos.
- **SC-005**: Las 10 agrupaciones y 11 filas adicionales de `QID + IP + Port + Protocol` se conservan y
  se informan como posibles repeticiones; no se eliminan ni se presentan como identidad única.
- **SC-006**: Un registro con varios CVE cuenta una sola vez; una consulta por uno de sus CVE devuelve
  el registro y no una fila por CVE.
- **SC-007**: El 100 % de los registros importados conserva `Severity` original, nivel 1–5 validado,
  etiqueta del proyecto y política aplicada; un valor ausente o fuera de 1–5 queda en validación
  explícita, sin etiqueta inventada ni equivalencia con CVSS/QDS/TruRisk/P1–P4.
- **SC-008**: Las consultas separan `pending_known`, `fixed` y `manual_review`; `Fixed` y «Revisión
  manual» no se presentan como activos y los conteos identifican el filtro aplicado.
- **SC-009**: En el archivo de referencia, la regla propuesta evalúa 129 registros con explotabilidad
  positiva, 8 con malware positivo y 8 con ambos; 121 tienen solo explotabilidad y 0 solo malware;
  533 y 654 quedan indeterminados por campo vacío. La bandera conjunta aparece exactamente en 8.
- **SC-010**: Un registro con ambos indicadores positivos muestra la bandera y su motivo; uno con un
  solo indicador muestra ese indicador sin la bandera conjunta; un campo vacío o indeterminado no se
  presenta como positivo.
- **SC-011**: Un caso con datos sintéticos e importados devuelve desglose por origen; un filtro de
  severidad sin origen en un caso mixto se rechaza como ambiguo, sin conversión silenciosa.
- **SC-012**: El 100 % de los registros importados conserva snapshot, importación, hash, fecha,
  versión del adaptador, política de severidad y regla de prioridad consultables.
- **SC-013**: Una consulta de un caso no devuelve registros, importaciones ni mensajes de otro caso;
  un recurso ajeno responde no encontrado.
- **SC-014**: Un resultado vacío informa «sin registros para esta consulta» y no afirma ausencia de
  vulnerabilidades.
- **SC-015**: La interfaz completa seleccionar caso → cargar CSV → previsualizar → confirmar →
  consultar, muestra el motivo de prioridad, conserva indicadores de carga y evita el doble envío.
- **SC-016**: Los logs, respuestas y trazas externas no contienen filas, IP, activos, resultados ni
  indicadores reales; solo metadatos acotados.
- **SC-017**: El sistema rechaza con motivo un archivo que supere los límites de tamaño, filas, campo
  o CVE, sin dejar una importación parcial silenciosa.
- **SC-018**: El soporte de `Fixed` y de estados desconocidos se acredita con fixtures sintéticos; el
  archivo de referencia no contiene `Fixed` y no se usa para inventar esa evidencia.

## Assumptions

- El único insumo de referencia es el CSV filtrado descrito; no se soportan reportes con
  preámbulo/pie, otros formatos de Qualys, Tenable ni conectores API.
- El manifiesto se usa para verificar el insumo de referencia; no es obligatorio para cada importación
  futura. El producto conserva el hash del manifiesto cuando se aporta.
- La política por defecto es rechazo completo ante errores estructurales; la aceptación parcial es una
  elección explícita.
- La severidad 1–5 es una convención de presentación del proyecto, no una denominación oficial de
  Qualys ni una equivalencia con CVSS, QDS, TruRisk o P1–P4.
- Los estados desconocidos son datos válidos para conservar y revisar, no errores estructurales.
- La interpretación de indicadores se basa en bloques estructurados y marcadores negativos; los
  valores no reconocidos quedan en revisión manual.
- Los datos reales no se usan en fixtures ni se envían a servicios externos.
- Los límites de referencia son 10 MiB, 10.000 filas, 20.000 caracteres por campo y 1.000 CVE por
  registro.
- La revisión humana por cita y las validaciones recomendadas del primer incremento no bloquean este
  trabajo.

## Ambigüedades restantes

No queda una decisión de negocio bloqueante. La interpretación de valores no reconocidos de
`Exploitability` y `Associated Malware` se resuelve como `indeterminada` y revisión manual, sin
inventar evidencia. La acreditación de `Fixed` y de estados desconocidos con fixtures sintéticos es
una cobertura de prueba pendiente de ejecución, no una ambigüedad de especificación.
