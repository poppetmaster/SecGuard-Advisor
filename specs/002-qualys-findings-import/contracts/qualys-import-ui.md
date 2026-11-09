# Contrato de interfaz — «Vulnerabilidades» e importación Qualys

## Terminología

- La sección visible se llama **«Vulnerabilidades»**.
- Menú del caso: Resumen, Documentos, Vulnerabilidades, Consulta documental.
- «Documentos» sigue siendo la carga de PDF y Markdown.
- `findings_query` y los nombres internos no cambian.
- Se distingue «registros de vulnerabilidades» de «vulnerabilidades únicas».

## Rutas

| Método | Ruta | Respuesta |
|---|---|---|
| GET | `/cases/{case_id}/vulnerabilities` | Sección con snapshot por defecto, resumen, tabla, filtros, selector e historial |
| GET | `/cases/{case_id}/vulnerabilities/imports` | Historial de importaciones del caso |
| GET | `/cases/{case_id}/vulnerabilities/imports/new` | Formulario «Cargar reporte de Qualys» |
| POST | `/cases/{case_id}/vulnerabilities/imports/validate` | Valida el CSV: `staged` si todo es válido, `rejected` si hay error bloqueante; devuelve/redirige a la vista previa |
| GET | `/cases/{case_id}/vulnerabilities/imports/{import_id}` | Vista previa del `staged` o `rejected`; 404 si no pertenece al caso |
| POST | `/cases/{case_id}/vulnerabilities/imports/{import_id}/confirm` | Confirma solo un `staged`; idempotente si ya está confirmado; 409 si está `rejected` |
| POST | `/cases/{case_id}/vulnerabilities/imports/{import_id}/cancel` | Cancela un `staged` o `rejected`; no toca la instantánea vigente |
| GET | `/cases/{case_id}/vulnerabilities?import_id=...&filters...` | Tabla de una instantánea seleccionada |

Todas las rutas resuelven el caso en el servidor. Un `import_id` de otro caso responde 404, nunca 403
con existencia confirmada.

## Formulario

- Campo `file` obligatorio, `multipart/form-data`, acepta `.csv` y `text/csv`.
- No hay campo de ruta local.
- No se solicita el manifiesto: el producto calcula hash/bytes/filas. Si la aceptación aporta el
  manifiesto, se usa fuera del formulario para verificar el insumo de referencia.
- Muestra límites: 10 MiB, 10.000 filas, 20.000 caracteres por campo, 1.000 CVE por registro.
- Botón «Validar archivo».
- Indicador de carga con el componente `pending` existente.
- Deshabilita el envío mientras está pendiente; un doble clic produce una sola validación.
- Cancelar vuelve a la sección sin modificar la instantánea vigente.

## Validación y vista previa

La validación es server-side y produce un `import_id` en estado `staged` o `rejected`. `staged`
significa que todo el archivo es válido y confirmable; `rejected` significa que hay al menos un error
estructural, de encabezado, contenido obligatorio, hash, cantidad o límite, y no se puede confirmar.
El cliente no envía contadores, hashes, filas normalizadas ni resultados de validación.

La vista previa muestra:

- Nombre original del archivo y SHA-256 (prefijo visible; valor completo en detalle local).
- Filas detectadas, válidas, inválidas estructurales, advertencias y revisión manual, y el estado
  `staged` o `rejected`.
- Distribución por estado: `Active`, `New`, `Re-Opened`, `Fixed`, desconocidos.
- Distribución por severidad 1–5 y etiqueta del proyecto.
- Explotabilidad: positivo, negativo/no informado e indeterminado. Malware: positivo, negativo/no
  informado e indeterminado. Ambos positivos: cantidad conjunta. Las dos distribuciones no se suman
  como grupos excluyentes.
- Posibles repeticiones por combinaciones parciales (sin afirmar identidad).
- Errores y advertencias con número de fila y motivo; sin valores sensibles en el mensaje. Un archivo
  `rejected` muestra cantidades y motivos, no una vista de filas válidas.
- Efecto de confirmar: snapshot que pasará a ser el último confirmado y conteos esperados.

La vista previa web normal no recibe manifiesto y no promete una comparación. La comparación es una
capacidad del servicio de validación/aceptación local; no se añade un campo de formulario ni una ruta
HTTP para el manifiesto.

La vista previa no incorpora filas a la consulta. No muestra el contenido completo de `Results`; la
tabla de preview se limita a campos clave y un máximo de filas por página.

## Confirmación

- Solo se confirma un `staged` del caso. Un `rejected` no se puede confirmar por ningún control.
- La confirmación usa el contenido persistido por la validación; no reenvía el archivo ni acepta
  contadores del cliente.
- Una confirmación repetida devuelve el mismo snapshot y no duplica.
- Si el mismo hash ya está confirmado en el caso, responde con la importación existente (idempotente).
- Si hay cualquier error bloqueante, el botón de confirmación no existe o está deshabilitado y se
  explica el motivo. No hay un control para «aceptar solo filas válidas» ni una confirmación parcial.
- Un fallo de integridad contra el manifiesto, cuando el servicio de aceptación lo recibió, también
  deja el archivo en `rejected`.
- Al confirmar, el snapshot recibe `confirmed_sequence` local y pasa a ser el último por defecto.

## Cancelar y expiración

- Cancelar un `staged` o `rejected` lo marca `cancelled`; se eliminan sus filas/issues en la limpieza.
- No modifica la instantánea vigente ni las confirmadas.
- Un `staged` o `rejected` abandonado expira a las 24 h (configurable); al volver a la URL se informa
  «validación expirada» y se ofrece cargar de nuevo.
- Un `confirmed` no se cancela desde la interfaz; es evidencia histórica.

## Manifiesto

- No es un archivo del formulario ni requiere una ruta HTTP nueva.
- La aceptación local puede pasar una ruta de manifiesto al servicio de validación.
- `absent`: no se aportó manifiesto; el CSV válido sigue a `staged` y no hay comparación.
- `matched`: el manifiesto es válido y coincide en hash, bytes, filas, columnas y conteos.
- `mismatch`: el manifiesto es válido pero no coincide; la importación queda `rejected` y no se
  confirma.
- `invalid`: el manifiesto está malformado; la importación queda `rejected` y no se confirma.
- La vista previa web no muestra una comparación que no recibió.

## Historial y selector

- «Historial de importaciones» lista snapshots confirmados y validaciones `staged`/`rejected`/
  canceladas/fallidas recientes con su estado.
- Cada fila muestra fecha, hash corto, filas, estados, severidad, prioridad y secuencia.
- El selector de la sección principal permite elegir un snapshot confirmado anterior.
- La sección siempre muestra el snapshot consultado; no suma snapshots.
- Si no hay snapshots confirmados, muestra el CTA de carga y un estado vacío explicativo.
- La ausencia de un registro en el snapshot actual no se etiqueta como corregido ni remediado.

## Tabla de registros

Columnas visibles: activo, título, QID, estado, severidad numérica + etiqueta, prioridad, indicadores,
CVE, primera/última detección. El motivo de prioridad se muestra como texto, no solo color.

Filtros: snapshot, estado (`pending_known`, `fixed`, `manual_review`, `all`), severidad 1–5, prioridad,
explotabilidad, malware, activo, QID, CVE, detalle/límite. Los filtros y conteos se muestran junto a
la tabla.

- `Fixed` y «Revisión manual» se muestran en grupos separados; no se suman a pendientes activos.
- La tabla no usa `Results` completo.
- El estado vacío distingue «sin registros para estos filtros» de «sin importaciones confirmadas»;
  ninguno afirma ausencia de vulnerabilidades ni riesgo bajo.
- El detalle recalculado se etiqueta como **«Consulta actual»**; no reemplaza el resumen histórico.

## Errores y estados

| Situación | Respuesta visible |
|---|---|
| Archivo ausente o extensión no admitida | 422 con motivo |
| Archivo demasiado grande | 413 con límite |
| Encabezado/columnas ausentes o adicionales | 200 con preview `rejected`, columnas esperadas/detectadas y sin filas confirmables |
| CSV ilegible, BOM/encoding inválido o fila inválida | 200 con preview `rejected` y motivo; no se confirma |
| Archivo vacío o sin filas | 200 con preview `rejected`, `empty_file`, `csv_bytes=0` y sin filas |
| Validación expirada | 410 con opción de cargar de nuevo |
| Confirmación de un snapshot ya confirmado | 200 idempotente con enlace |
| Confirmación de un `rejected` | 409; no se modifica nada |
| Confirmación de otro caso | 404 |
| Conflicto de secuencia/concurrencia | reintento seguro o 409 con mensaje |
| Fallo interno | 500 con mensaje comprensible; sin traza ni filas |

El manifiesto no genera códigos HTTP en la interfaz porque no se recibe por una ruta web. Sus estados
(`absent`, `matched`, `mismatch`, `invalid`) se registran en el servicio de validación/aceptación.
No se exponen rutas absolutas, valores de filas, IP, activos, resultados ni stack traces.

## Accesibilidad y presentación

- Formulario con `label`, foco visible, texto de ayuda y errores asociados; navegación por teclado,
  cierre con Escape, foco inicial/restauración en el menú móvil y etiquetas accesibles.
- Indicador de carga y botón deshabilitado; sin doble envío.
- Tabla con encabezados, scroll horizontal en móvil y alternativa de tarjetas si no cabe.
- Objetivos de 390 px y 320 px sin desbordamiento de página.
- Se reutilizan shell, iconos locales, Tailwind/Flowbite y navegación existente.
- No se añade dashboard ni se rediseña la aplicación.

## Privacidad

- El CSV no se guarda como archivo en el repositorio; los valores originales de filas `staged`/
  `confirmed` viven en SQLite local. Un `rejected` no conserva filas de vulnerabilidad, solo issues y
  resumen agregado.
- El nombre del archivo y los metadatos se guardan localmente para procedencia; no se envían a
  LangSmith.
- La vista previa no renderiza `Results` completo. Las plantillas escapan todo el contenido del CSV
  (título, activo, resultados, indicadores); no se usa `|safe` ni se inyecta HTML del archivo.
- Los logs no incluyen filas, IP, activos, resultados ni indicadores; solo IDs, códigos y conteos.
- La importación no realiza llamadas a servicios externos.
