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
| POST | `/cases/{case_id}/vulnerabilities/imports/validate` | Valida el CSV, crea un `staged` y devuelve/redirige a la vista previa |
| GET | `/cases/{case_id}/vulnerabilities/imports/{import_id}` | Vista previa del `staged`; 404 si no pertenece al caso |
| POST | `/cases/{case_id}/vulnerabilities/imports/{import_id}/confirm` | Confirma el `staged`; idempotente si ya está confirmado |
| POST | `/cases/{case_id}/vulnerabilities/imports/{import_id}/cancel` | Cancela un `staged`; no toca la instantánea vigente |
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

La validación es server-side y produce un `import_id` `staged`. El cliente no envía contadores,
hashes, filas normalizadas ni resultados de validación.

La vista previa muestra:

- Nombre original del archivo y SHA-256 (prefijo visible; valor completo en detalle local).
- Filas detectadas, válidas, inválidas estructurales, advertencias y revisión manual.
- Distribución por estado: `Active`, `New`, `Re-Opened`, `Fixed`, desconocidos.
- Distribución por severidad 1–5 y etiqueta del proyecto.
- Prioridad conjunta: ambos, solo explotabilidad, solo malware, ninguno, indeterminados.
- Posibles repeticiones por combinaciones parciales (sin afirmar identidad).
- Errores y advertencias con número de fila y motivo; sin valores sensibles en el mensaje.
- Comparación con el manifiesto cuando se aportó.
- Efecto de confirmar: snapshot que pasará a ser el último confirmado y conteos esperados.

La vista previa no incorpora filas a la consulta. No muestra el contenido completo de `Results`; la
tabla de preview se limita a campos clave y un máximo de filas por página.

## Confirmación

- Solo se confirma un `staged` del caso.
- La confirmación usa el contenido persistido por la validación; no reenvía el archivo ni acepta
  contadores del cliente.
- Una confirmación repetida devuelve el mismo snapshot y no duplica.
- Si el mismo hash ya está confirmado en el caso, responde con la importación existente (idempotente).
- Si hay errores estructurales y la política es rechazo completo, el botón está deshabilitado y se
  explica el motivo.
- Si hay filas inválidas y la persona elige aceptación parcial, debe confirmar esa elección y ver las
  filas omitidas; no hay descarte silencioso.
- Al confirmar, el snapshot recibe `confirmed_sequence` local y pasa a ser el último por defecto.

## Cancelar y expiración

- Cancelar un `staged` lo marca `cancelled`; se eliminan sus filas/issues en la limpieza.
- No modifica la instantánea vigente ni las confirmadas.
- Un `staged` abandonado expira a las 24 h (configurable); al volver a la URL se informa «validación
  expirada» y se ofrece cargar de nuevo.
- Un `confirmed` no se cancela desde la interfaz; es evidencia histórica.

## Historial y selector

- «Historial de importaciones» lista snapshots confirmados, cancelados/fallidos recientes y su estado.
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
- El estado vacío distingue «sin registros para estos filtros» de «sin importaciones confirmadas».
- El detalle recalculado se etiqueta como consulta actual; no reemplaza el resumen histórico.

## Errores y estados

| Situación | Respuesta visible |
|---|---|
| Archivo ausente o extensión no admitida | 422 con motivo |
| Archivo demasiado grande | 413 con límite |
| Encabezado/columnas ausentes o adicionales | 422 con columnas esperadas y detectadas, sin filas |
| CSV ilegible o BOM/encoding inválido | 422 con motivo |
| Hash/manifiesto no coincide | 422/409 con hash calculado y esperado |
| Validación expirada | 410 con opción de cargar de nuevo |
| Confirmación de un snapshot ya confirmado | 200 idempotente con enlace |
| Confirmación de otro caso | 404 |
| Conflicto de secuencia/concurrencia | reintento seguro o 409 con mensaje |
| Fallo interno | 500 con mensaje comprensible; sin traza ni filas |

No se exponen rutas absolutas, valores de filas, IP, activos, resultados ni stack traces.

## Accesibilidad y presentación

- Formulario con `label`, foco visible, texto de ayuda y errores asociados.
- Indicador de carga y botón deshabilitado; sin doble envío.
- Tabla con encabezados, scroll horizontal en móvil y alternativa de tarjetas si no cabe.
- Objetivos de 390 px y 320 px sin desbordamiento de página.
- Se reutilizan shell, iconos locales, Tailwind/Flowbite y navegación existente.
- No se añade dashboard ni se rediseña la aplicación.

## Privacidad

- El CSV no se guarda como archivo en el repositorio; los valores originales viven en SQLite local.
- El nombre del archivo y los metadatos se guardan localmente para procedencia; no se envían a
  LangSmith.
- La vista previa no renderiza `Results` completo.
- Los logs no incluyen filas, IP, activos, resultados ni indicadores; solo IDs, códigos y conteos.
- La importación no realiza llamadas a servicios externos.
