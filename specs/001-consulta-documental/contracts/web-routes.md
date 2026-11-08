# Contrato de rutas web

Aplicación servida en `127.0.0.1`. Todas las rutas de caso reciben `case_id` en la ruta; el
servidor lo resuelve y construye el `CaseScope` **antes** de cualquier lectura. Ningún formulario,
cabecera o argumento del modelo puede sustituir ese alcance.

Las respuestas son HTML. Los formularios funcionan sin JavaScript; HTMX solo reemplaza fragmentos.
Para métodos no seguros se valida el origen de la petición (`Origin`/`Referer`); una petición
cruzada se rechaza con `403`. No hay autenticación en este incremento; el servidor escucha solo en
loopback.

## Rutas

| Método | Ruta | Entrada | Salida | Estados |
|---|---|---|---|---|
| GET | `/` | — | Redirección a `/cases` | 303 |
| GET | `/cases` | — | Lista de casos con fecha y marca de sintético | 200 |
| GET | `/cases/new` | — | Formulario de creación | 200 |
| POST | `/cases` | `title`, `description`, `ai_application`, `data_processed`, `assets[]`, `restrictions` | Redirección al caso creado | 303, 422 |
| GET | `/cases/{case_id}` | — | Espacio de trabajo: contexto, documentos y conversación | 200, 404 |
| GET | `/cases/{case_id}/documents` | — | Fragmento con la lista de documentos y estados | 200, 404 |
| POST | `/cases/{case_id}/documents` | `file`, `origin` (`case_evidence`), `title?`, `declared_version?`, `declared_date?` | Fragmento con la fila del documento y su estado | 201, 409, 413, 415, 422 |
| GET | `/cases/{case_id}/documents/{document_id}` | — | Detalle con versiones, páginas legibles y procedencia | 200, 404 |
| POST | `/cases/{case_id}/documents/{document_id}/retry` | — | Fragmento con el estado reiniciado | 202, 404, 409 |
| GET | `/cases/{case_id}/documents/{document_id}/versions/{version_id}/fragments/{chunk_id}` | `quote?` | Visor del fragmento con la cita resaltada | 200, 404 |
| GET | `/cases/{case_id}/chat` | — | Panel de conversación con historial | 200, 404 |
| POST | `/cases/{case_id}/chat/messages` | `question` | Fragmento con pregunta, respuesta, citas y referencia a la ejecución | 200, 422, 409, 429, 503, 504 |
| POST | `/cases/{case_id}/runs/{run_id}/retry` | — | Fragmento con la nueva ejecución y su estado; reutiliza la pregunta original | 202, 404, 409, 429 |
| POST | `/cases/{case_id}/messages/{message_id}/citations/{citation_id}/review` | `status` (`supported`/`not_supported`), `note?` | Fragmento con el estado de revisión de la cita | 200, 404, 409, 422 |
| GET | `/cases/{case_id}/runs/{run_id}` | — | Evidencia de ejecución | 200, 404 |
| GET | `/healthz` | — | JSON `{status, database, ollama}` sin secretos | 200, 503 |
| GET | `/static/{path}` | — | Recurso local | 200, 404 |

## Formularios

### Crear caso — `POST /cases`

| Campo | Tipo | Obligatorio | Regla |
|---|---|---|---|
| `title` | texto | Sí | No vacío tras recortar; máximo 200 caracteres |
| `description` | texto largo | No | Vacío = desconocido |
| `ai_application` | texto | No | Vacío = desconocido |
| `data_processed` | texto | No | Vacío = desconocido |
| `assets` | texto, uno por línea | No | Cada línea no vacía crea un activo del caso |
| `restrictions` | texto largo | No | Vacío = desconocido |

`context_is_synthetic` se fija en `1` y `synthetic_notice` en el texto educativo aprobado. El
usuario no puede desactivarlo en este incremento.

### Cargar documento — `POST /cases/{case_id}/documents`

| Campo | Tipo | Obligatorio | Regla |
|---|---|---|---|
| `file` | archivo | Sí | PDF con texto o Markdown; máximo configurable (20 MB por defecto) |
| `origin` | selección | Sí | Solo `case_evidence` en esta ruta |
| `title` | texto | No | Por defecto, nombre del archivo |
| `declared_version` | texto | No | Se conserva tal cual |
| `declared_date` | fecha | No | ISO-8601; se conserva tal cual |

Respuestas:

- `201`: documento aceptado, estado `pending` o `processing`.
- `409`: contenido idéntico ya presente en el caso; se devuelve el documento existente.
- `413`: excede el tamaño permitido.
- `415`: tipo no admitido o contenido real distinto de la extensión.
- `422`: nombre o campos inválidos.

### Preguntar — `POST /cases/{case_id}/chat/messages`

| Campo | Tipo | Obligatorio | Regla |
|---|---|---|---|
| `question` | texto | Sí | No vacío; máximo 2000 caracteres |

- `409`: ya hay una consulta en curso para ese caso; se informa sin encolar.
- `429`: hay una generación en curso en el sistema (otro caso) y no se obtuvo el turno global dentro
  de la espera acotada definida por `SECGUARD_GENERATION_QUEUE_TIMEOUT_SECONDS` (segundos; 5 por
  defecto); no se crea ejecución ni mensaje.
- `503`: el generador no está disponible; la pregunta queda registrada y la ejecución en `failed`.
- `504`: se agotó el tiempo del turno; la ejecución queda en `timeout`.

La consulta activa se libera al terminar en éxito, error, timeout o reinicio. Una segunda consulta
del mismo caso no se ejecuta en paralelo ni se encola. La desconexión del cliente no libera la
ejecución antes de que la generación termine.

Tres casos distintos:

1. **Pregunta nueva** después de un turno exitoso: crea mensaje y ejecución nuevos, aunque el texto
   se repita.
2. **Reintento** de una operación fallida: ver la sección siguiente.
3. **Envío duplicado** con una ejecución activa: `409`, sin mensaje ni ejecución nuevos.

### Reintentar un turno — `POST /cases/{case_id}/runs/{run_id}/retry`

- Solo se acepta para una ejecución `failed`, `timeout` o `interrupted` **y sin respuesta
  persistida**; en otro caso, `409`.
- Reutiliza el mensaje de pregunta original. **No** crea un mensaje de usuario nuevo.
- Crea una ejecución nueva con `attempt_no` incrementado y `retry_of_run_id`.
- Si el caso ya tiene una consulta activa, `409`. Si el sistema está generando para otro caso, `429`
  tras la espera acotada de `SECGUARD_GENERATION_QUEUE_TIMEOUT_SECONDS` (segundos; 5 por defecto).

### Revisar el respaldo semántico — `POST /cases/{case_id}/messages/{message_id}/citations/{citation_id}/review`

| Campo | Tipo | Obligatorio | Regla |
|---|---|---|---|
| `status` | selección | Sí | `supported` o `not_supported` |
| `note` | texto | No | Observación del revisor; máximo 500 caracteres |

Registra autor y fecha del servidor. El autor se toma de `SECGUARD_REVIEWER_NAME`; si esa
configuración está vacía, la petición se rechaza con `409` y no se escribe ninguna revisión. Es una
identidad local declarada, no un mecanismo de autenticación. No adjudica prioridades P1–P4 ni
aprueba informes. Una cita `unreviewed` se muestra como pendiente y no se presenta como
fundamentada.

## Respuestas de error

| Código | Cuándo | Qué ve el usuario |
|---|---|---|
| 403 | Origen no permitido | «La solicitud no proviene de esta aplicación» |
| 404 | Caso, documento, versión o ejecución inexistente en el alcance | «No encontrado en este caso» |
| 409 | Duplicado, ejecución en curso, reintento inválido o identidad de revisor no configurada | Explicación y acción disponible |
| 429 | Generación en curso en otro caso y espera agotada | «El sistema está ocupado; intentá de nuevo» |
| 413 | Archivo demasiado grande | Límite aplicado |
| 415 | Tipo no admitido o contenido falso | Motivo concreto |
| 422 | Campo inválido | Error junto al campo |
| 503 | Modelo no disponible | «El modelo local no responde» y opción de reintentar |
| 504 | Tiempo agotado | «La consulta excedió el tiempo» y ejecución registrada |
| 500 | Fallo interno | Mensaje genérico con `run_id` o `event_id`, sin traza |

## Reglas de alcance en rutas

- `case_id` se toma de la ruta y se valida contra `cases`. Si no existe, `404`; no se revela si el
  recurso existe en otro caso.
- Un `document_id` de otro caso produce `404`, no `403`: no se confirma la existencia.
- Un `run_id` de otro caso produce `404`.
- Un `message_id` o un `citation_id` de otro caso producen `404`.
- Ninguna ruta acepta `case_id` por cadena de consulta ni por cuerpo.
