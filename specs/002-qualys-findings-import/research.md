# Research — Importación de vulnerabilidades Qualys

## R1. Snapshots independientes, sin identidad estable entre reportes

**Decisión**: cada carga confirmada es una instantánea inmutable, identificada por `import_id` y una
secuencia local por caso. Cada fila conserva `import_id` y `row_number`. No se calcula ni se afirma
una identidad de vulnerabilidad entre archivos.

**Rationale**: el CSV no incluye un identificador estable demostrado. `QID + IP + Port + Protocol`
produce 10 grupos duplicados y 11 filas adicionales; `First Detected` es única en el archivo pero no
se puede probar inmutable ante reaperturas. Afirmar identidad establecería una remediación o
duplicación que los datos no sostienen.

**Alternativas consideradas**:

- Clave natural `QID + IP + Port + Protocol`: rechazada como identidad; se conserva para informar
  posibles repeticiones.
- `QID + IP + Port + Protocol + First Detected`: no se usa para reconciliar entre reportes.
- Identificador externo de Qualys: no está disponible en el CSV.

**Consecuencia**: el mismo hash de archivo en el mismo caso es idempotente; un archivo distinto crea
una instantánea nueva; la ausencia en un snapshot posterior no se interpreta como remediación.

## R2. Tablas nuevas en lugar de extender `findings`

**Decisión**: crear `qualys_imports`, `qualys_vulnerabilities`, `qualys_vulnerability_cves` y
`qualys_import_issues`. No se reutiliza `findings` para registros Qualys.

**Rationale**: `findings` exige `asset_id` y `dataset_id` del dataset sintético, y su severidad está
restringida a `Critical/High/Medium/Low/Info`. Forzar esos campos crearía una identidad de activo y
una escala que el CSV no demuestra. Las tablas separadas preservan la semántica y permiten consultas
por origen sin migrar datos sintéticos.

**Alternativas consideradas**:

- Una columna `origin` y un `dataset_id` nulo en `findings`: obliga a relajar restricciones existentes
  y mezcla dos ciclos de vida.
- Una tabla única de snapshots con JSON: pierde índices y checks útiles para conteos.
- Extender `findings` con `import_id`: deja el modelo sintético acoplado a Qualys.

## R3. Parser CSV estándar, límites y estructura

**Decisión**: usar `csv.DictReader` con `utf-8-sig`, `newline=""`, encabezado exacto de 41 columnas y
lectura acotada por bytes/filas. No se usa pandas ni se abre el reporte original. El archivo se lee
desde el `UploadFile` de FastAPI o desde el fixture de aceptación; no se conserva como archivo en el
repositorio.

**Rationale**: el archivo tiene BOM, comas, comillas y campos multilínea; la biblioteca estándar
respeta RFC 4180 y evita dependencias nuevas. El límite de 10 MiB/10.000 filas es superior al insumo
de referencia y evita cargas desmedidas.

**Alternativas consideradas**:

- `pandas.read_csv`: dependencia pesada para un formato ya acotado.
- Lectura línea a línea propia: no maneja comillas/multilínea con seguridad.
- Guardar el CSV original en `storage/`: no es necesario para consultar y aumenta la exposición de
  datos reales.

## R4. Severidad: convención del proyecto versionada

**Decisión**: conservar `Severity` original, `severity_level` 1–5 y una etiqueta de presentación:
1 Informativa, 2 Baja, 3 Media, 4 Alta, 5 Crítica. La política se identifica con
`project-severity-1-5-v1`. No se usa para CVSS, QDS, ARS, ACS, TruRisk ni P1–P4.

**Rationale**: es una convención de producto explícita, no una denominación oficial de Qualys. La
etiqueta existe para presentación y filtros del proyecto; el valor original queda para auditoría.

**Compatibilidad**: los hallazgos sintéticos conservan sus etiquetas y escala existentes. Un filtro
de severidad en un caso mixto exige `origin`; si falta, se devuelve `ambiguous_severity_filter`.

**Valores inválidos**: ausente o fuera de 1–5 es un error de validación de fila, no una etiqueta
inventada. Una sola fila inválida impide confirmar el archivo: la importación queda `rejected` y no
se crea una instantánea parcial.

## R5. Estados y grupos de consulta

**Decisión**: normalizar `Active`, `New`, `Re-Opened`, `Fixed`; cualquier otro valor se conserva como
`manual_review` con el original. Los grupos de consulta son `pending_known`, `fixed`, `manual_review`
y `all`.

**Rationale**: el archivo de referencia no tiene `Fixed`, pero la especificación exige admitirlo. Un
estado desconocido es un dato válido que requiere revisión, no un error estructural. Mezclar estados
desconocidos con `Active` inflaría pendientes.

**Default de consulta importada**: `pending_known` cuando `origin=imported`; `all` cuando
`origin=all`. El usuario puede pedir `all`, `fixed` o `manual_review`; el resultado siempre muestra el
grupo aplicado. `Fixed` y «Revisión manual» no se presentan como vulnerabilidades activas.

**Alternativas consideradas**: rechazar estados desconocidos (contradice la decisión del responsable);
mapearlos a `Active` (inventa estado); excluirlos silenciosamente (oculta información).

## R6. Explotabilidad, malware y prioridad

**Decisión**: evaluar cada campo por separado y versionar la regla.

**Exploitability**:

- Positiva si existe al menos un bloque estructurado con `Source` y `Reference`, `Link` o
  `Description`, sin que el bloque sea solo un marcador negativo.
- Negativa/no informada si solo hay `N/A`, `None`, `No` o mensajes explícitos de no detección.
- Indeterminada si está vacía o la estructura no se reconoce.

**Associated Malware**:

- Positiva si existe al menos un `Malware ID` distinto de `N/A`, `None` o `No`, acompañado de `Type`,
  `Risk` o `Link`.
- Negativa/no informada si solo hay marcadores negativos.
- Indeterminada si está vacía o la estructura no se reconoce.

**Prioridad**: `priority_flag` solo si ambas evaluaciones son positivas. Se conservan
`exploitability_eval`, `malware_eval`, `priority_flag`, `priority_reason` y
`priority_rule_version = "qualys-evidence-both-v1"`.

**Contexto**: pendiente conocido + ambos positivos = prioridad de atención; `Fixed` + ambos =
antecedente prioritario reportado; estado desconocido + ambos = revisión manual del estado con
indicadores. Un solo indicador positivo se muestra, pero no activa la bandera conjunta.

**Evidencia de referencia (agregada)**: 129 con explotabilidad positiva, 8 con malware positivo, 8 con
ambos (7 `Active`, 1 `New`), 121 con solo explotabilidad, 0 con solo malware, 533/654 indeterminados
por campo vacío. No se usan estos conteos para forzar resultados.

**Alternativas consideradas**: considerar cualquier texto no vacío como positivo (falso positivo);
usar una disyunción (contradice la regla conjunta); interpretar campos vacíos como ausencia (no
demostrable).

## R7. findings_query: composición por origen y snapshot

**Decisión**: extender el esquema estricto con `origin`, `snapshot_id`, `status_group`,
`severity_level`, `priority`, `exploitability`, `malware` y `group_by` adicional. Mantener
`asset`, `qid`, `cve`, `severity` sintética, `detail` y `limit`.

**Composición**:

- `origin=synthetic`: usa el repositorio sintético existente; `severity` conserva las etiquetas
  actuales.
- `origin=imported`: usa la instantánea seleccionada o la última confirmada; `severity_level` usa
  1–5 y la etiqueta del proyecto.
- `origin=all`: devuelve un bloque por origen (`origins[]`) con totales y grupos independientes, sin
  fusionar escalas. `total` puede ser la suma, pero siempre acompañado del desglose.
- Un filtro de severidad con `origin=all` devuelve `ambiguous_severity_filter`.
- `snapshot_id`, `priority`, `exploitability` y `malware` requieren `origin=imported`; usarlos con
  `origin=all` o `origin=synthetic` devuelve `filter_not_applicable`.
- `status_group` con `origin=all` solo admite `all`; cualquier otro valor devuelve
  `origin_required_for_status_filter`. Con `origin=imported` el default es `pending_known`; con
  `origin=all` el default es `all`; con `origin=synthetic` no aplica y devuelve
  `filter_not_applicable`.
- `snapshot_id` debe pertenecer al caso y estar confirmado; si no, `snapshot_not_found`. Una vez
  fijada la instantánea del turno, un `snapshot_id` distinto devuelve `snapshot_locked`.

**Conteos**: `COUNT(*)` sobre la tabla correspondiente con los filtros aplicados; CVE con
subconsulta `EXISTS`/`IN`, nunca join que multiplique filas.

**Alternativas consideradas**: unir sintéticos e importados en una sola tabla (pierde escalas);
convertir etiquetas sintéticas a 1–5 (conversión silenciosa); devolver solo un total agregado
(mezcla silenciosa).

## R8. Fijación del snapshot y reproducibilidad

**Decisión**: en la primera ejecución de `findings_query` de un turno, resolver la última instantánea
confirmada y guardar `selected_import_id` en el estado del grafo. Todas las llamadas posteriores del
mismo turno reutilizan ese id. Un `snapshot_id` distinto devuelve `snapshot_locked`; el modelo no
puede cambiar la instantánea de forma silenciosa. Un turno nuevo puede seleccionar otra importación.
Cada `run_tool_calls` guarda el snapshot usado y el resumen; la respuesta se construye con ese
resultado y no se vuelve a consultar la base al renderizar la evidencia.

**Rationale**: si otra importación se confirma mientras el modelo responde, la respuesta no cambia de
snapshot de forma invisible. La página de ejecución lee el resumen histórico; el detalle recalculado
se etiqueta como consulta actual.

**Alternativas consideradas**: resolver el snapshot al renderizar (puede cambiar el resultado);
consultar de nuevo al mostrar detalle (mezcla historia y actualidad).

## R9. Staging, preview y confirmación

**Decisión**: validar en memoria y persistir una importación en estado `staged` (todo el archivo
válido) o `rejected` (error bloqueante) con sus issues en una transacción corta. Solo `staged`
inserta filas de validación; `rejected` no inserta filas en `qualys_vulnerabilities`. La preview se
lee de SQLite y la confirmación cambia `staged` a `confirmed` dentro de una transacción que asigna
`confirmed_sequence`.

**Rationale**: el preview y la confirmación deben usar exactamente el contenido validado; no se
confía en contadores enviados por el cliente. No se conserva el CSV como archivo; `raw_json` por fila
preserva los valores originales.

**Cancelar/expirar**: una importación `staged` o `rejected` puede pasar a `cancelled` o `expired`;
sus filas/issues se eliminan en la limpieza. Las confirmadas nunca se borran ni se sobrescriben.

**Sin aceptación parcial**: no hay control para importar solo filas válidas. Un error estructural,
de encabezado, contenido obligatorio, hash, cantidad, límite o archivo vacío deja la importación en
`rejected` y no permite confirmar. La persona cancela o carga un archivo corregido. Un archivo vacío
se registra con `csv_bytes=0`, `row_count=0` y `empty_file`.

**Manifiesto**: la comparación es una capacidad del servicio de validación/aceptación, no un campo
del formulario ni una ruta HTTP. Estados: `absent` (sin manifiesto), `matched`, `mismatch`
(manifiesto válido que no coincide) e `invalid` (manifiesto malformado). `mismatch` e `invalid` dejan
la importación en `rejected`; `absent` no impide validar el CSV.

**Idempotencia**: índice único parcial `(case_id, csv_sha256)` para `confirmed`; el servicio reutiliza
un `staged` con el mismo hash o devuelve la confirmación existente. Un `rejected` no bloquea una
carga corregida.

## R10. Concurrencia y secuencia

**Decisión**: `confirmed_sequence` se asigna por caso dentro de la transacción de confirmación como
`max(sequence)+1`; índice único `(case_id, confirmed_sequence)`. Confirmar dos veces la misma
importación devuelve el resultado ya confirmado sin duplicar. Dos archivos distintos pueden crear
snapshots distintos en secuencia.

**Rationale**: la app es de un worker, pero hay concurrencia de solicitudes; la restricción de base
es la garantía final. No se usan locks distribuidos.

## R11. Privacidad y trazabilidad

**Decisión**: la importación es estrictamente local. No se envían a LangSmith ni a otros servicios
filas, IP, DNS, NetBIOS, FQDN, títulos, resultados, indicadores, nombres de archivo ni metadatos
sensibles. La traza manual existente recibe solo identificadores opacos, conteos, estado, versión de
adaptador, duración y versiones de política.

**Riesgo residual**: el prompt del modelo local puede contener activos o títulos importados; la
inferencia es local. Los `Results` largos no se incluyen en el resultado de la herramienta ni en la
vista previa completa. Los logs se redactan con el filtro existente y no se añaden valores de fila.

**Pruebas y orden**: las pruebas usan señuelos sintéticos y payloads capturados; cubren preguntas,
memoria/historial, argumentos/resultados, prompts/respuestas, callbacks, nombres de archivo,
logs/errores y renderizado. La aceptación real con el CSV se ejecuta después de verificar privacidad
y manifiesto, con trazas externas desactivadas.

**Alternativas consideradas**: enviar el CSV a un servicio de parsing (prohibido); trazar el prompt
completo (prohibido); mostrar `Results` completo en preview (exposición innecesaria).

## R12. Interfaz «Vulnerabilidades»

**Decisión**: añadir una sección de caso después de Documentos, con rutas GET/POST y plantillas
propias, reutilizando shell, iconos, `pending`, Tailwind/Flowbite y patrones de tablas existentes.

**Rutas**:

- `GET /cases/{case_id}/vulnerabilities`
- `GET /cases/{case_id}/vulnerabilities/imports`
- `GET /cases/{case_id}/vulnerabilities/imports/new`
- `POST /cases/{case_id}/vulnerabilities/imports/validate`
- `GET /cases/{case_id}/vulnerabilities/imports/{import_id}`
- `POST /cases/{case_id}/vulnerabilities/imports/{import_id}/confirm`
- `POST /cases/{case_id}/vulnerabilities/imports/{import_id}/cancel`

La sección principal muestra el snapshot seleccionado, resumen, tabla, filtros, selector de historial
y CTA de carga. No hay dashboard.

## R13. Migración y compatibilidad

**Decisión**: migración aditiva después de `9c3e4f5a6b7d`; solo crea tablas e índices nuevos. No se
modifican tablas sintéticas, mensajes, citas, ejecuciones ni trazas existentes.

**Rationale**: preservar el primer incremento y permitir rollback de la migración sin tocar datos
sintéticos. Los datos importados son locales y desechables por snapshot; las confirmadas se conservan.

## R14. Pruebas y aceptación local

**Decisión**: pruebas unitarias y de contrato con fixtures sintéticos; integración con SQLite temporal;
aceptación real opcional con el CSV autorizado fuera de Git; Playwright para formulario, preview,
confirmación, historial, selector, tabla, móvil 390/320 y doble envío.

**Fixtures sintéticos**: CSV con BOM, comas, comillas, multilínea, `Active/New/Re-Opened/Fixed`,
estado desconocido, severidades 1–5, varios CVE con longitudes de 4–7 dígitos, ambos/solo
uno/vacío/negativo/indeterminado en indicadores, filas repetidas por combinaciones parciales,
archivo vacío y errores estructurales. Se añaden manifiesto sintético, escenarios de repetición,
evidencia histórica/actual, estados vacíos y una prueba de que los registros no entran en Chroma ni
en citas. El fixture de errores y el archivo vacío deben quedar `rejected` y no confirmarse.

**Aceptación real**: se ejecuta después de las pruebas de privacidad y manifiesto, con
`LANGSMITH_TRACING=false`; leer el CSV desde `../` y pasar la ruta del manifiesto al servicio de
validación de la aceptación local, nunca al formulario ni a una ruta HTTP. Verificar hash y conteos;
importar en almacenamiento temporal; no versionar, no copiar filas a logs ni a documentación; no
enviar a LangSmith. Los conteos 662/129/8/8 son referencias de inspección, no resultados forzados.
Un archivo con error de integridad o manifiesto inválido/discrepante queda `rejected`; no se permite
una aceptación parcial. El resultado se registra como ejecutada aprobada, ejecutada fallida o no
ejecutada con motivo; un skip no acredita la aceptación.

## R15. Riesgos y decisiones pendientes de implementación

- El default `pending_known` para consultas importadas es una decisión de producto del plan; debe
  quedar visible en el resultado.
- La política de rechazo es única: `staged` solo si todo el archivo es válido; `rejected` no se
  confirma ni produce instantánea parcial.
- La etiqueta de activo es de presentación (`FQDN`→`DNS`→`NetBIOS`→`IP`) y no una identidad.
- La fecha no tiene zona horaria; se conserva el valor y se marca la limitación.
- El soporte de `Fixed` y estados desconocidos se acredita con fixtures, no con el archivo de
  referencia.
- P1–P4 y su formulario están diferidos al incremento 3; 002 no los implementa.
- El formato CSV está definido; el adaptador es una implementación de 002, no una decisión pendiente.
- La instantánea fijada en el turno no cambia; un `snapshot_id` distinto devuelve `snapshot_locked`.
- La respuesta del agente debe mencionar snapshot, origen, estado y prioridad cuando corresponda.
