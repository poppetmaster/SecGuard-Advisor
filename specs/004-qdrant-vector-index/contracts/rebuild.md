# Contract: Qdrant rebuild

**Scope**: reconstrucción limpia desde SQLite. No implementa código.

## Trigger

Comando explícito, por ejemplo `make qdrant-rebuild` o
`uv run python scripts/rebuild_qdrant.py`. No se ejecuta automáticamente al arrancar la aplicación.

El comando y su reporte local son la **interfaz operativa** de estado y avance de la reconstrucción.
No se exige una pantalla web de administración en 004; la interfaz web solo presenta los errores de
índice de los flujos existentes.

## Preconditions

- Qdrant 1.20.0 responde en `/readyz`.
- `qdrant-client==1.20.0` es compatible con el servidor.
- `SECGUARD_INSTANCE_ID` está definido, validado y coincide con
  `<SECGUARD_STORAGE_DIR>/qdrant-control/instances/<instance_id>.json` y su fingerprint (ruta
  canónica del almacenamiento + `instance_id`).
- SQLite existe y conserva documentos, versiones y fragmentos.
- El modelo de embeddings local `embeddinggemma` está disponible con dimensión 768.
- No hay otra reconstrucción o ingesta activa (lock de instancia).
- El almacenamiento de prueba es separado de la instancia del usuario.

## Steps

1. Validar instancia/namespace, versión, conexión y compatibilidad.
2. Adquirir el lock de archivo de la instancia y registrar `operation=rebuild` con un `attempt_id`,
   `pid` y hora de inicio; si está ocupado, fallar con `ingestion_in_progress` o
   `reconstruction_in_progress` según la operación propietaria.
3. Leer SQLite y seleccionar documentos/versiones vigentes disponibles.
4. Validar texto, metadatos, modelo y dimensión de cada fragmento.
5. Regenerar embeddings con el mismo modelo local, por lotes.
6. Crear una colección de generación nueva por alcance con el namespace de instancia.
7. Subir puntos con UUIDv5 determinista y payload de procedencia.
8. Comparar el conjunto de `chunk_id` esperado contra Qdrant; verificar conteos y muestras.
9. Cambiar el alias activo solo si la validación es completa; si falla, conservar el alias anterior.
10. Conservar la generación anterior para recuperación.
11. Escribir un reporte JSON bajo `<SECGUARD_STORAGE_DIR>/qdrant-control/reports/<instance_id>/` con
    un archivo por ejecución y un `latest.json` con el último resultado terminal.
12. Liberar el lock en `finally`.

## Observable states

| Estado | Fuente | Interpretación |
|---|---|---|
| `not_started` | Sin reporte terminal y sin lock de reconstrucción | No hay reconstrucción registrada; no implica fallo. |
| `in_progress` | Lock tomado por un proceso vivo cuyo registro declara `operation=rebuild` | Reconstrucción en curso; el alias anterior sigue vigente. Un `latest.json` previo describe el intento anterior. |
| `completed` | `status` del último reporte terminal | Alcances validados. |
| `partial` | `status` del último reporte terminal | Parte del alcance quedó sin indexar; el reporte global no declara la reconstrucción completa. |
| `failed` | `status` del último reporte terminal | Error terminal; el alias anterior se conserva. |

Un lock con `operation=ingestion` indica ingesta activa, no reconstrucción en curso. Un lock activo no
es éxito, un reporte ausente no es fallo y un registro de propietario residual con el lock libre se
ignora.

## Status query (read-only)

`uv run python scripts/rebuild_qdrant.py --status` es una consulta de solo lectura.

- Devuelve `state` en `not_started`, `ingestion_in_progress`, `rebuild_in_progress`, `completed`,
  `partial` o `failed`; incluye el propietario del lock si está activo y el último resultado terminal.
- Sin estado registrado devuelve `not_started` y finaliza con éxito (salida 0).
- Metadatos de propietario con el lock libre se ignoran: no representan una operación en curso.
- No inicia reconstrucciones, no genera embeddings, no crea colecciones, no registra instancias, no
  escribe archivos y no cambia aliases. Si el archivo de lock no existe, no se crea.
- El resolvedor único vive en `retrieval/status.py`; la CLI y el reporte lo consumen.
- Si el reporte terminal es ilegible: salida 2, mensaje en `stderr` y JSON con `state: null`,
  `last_terminal: null` y `error: {code, message}`. No se presenta como `not_started`, no se inventa un
  estado terminal y el reporte no se borra, sobrescribe ni repara.
- Si la configuración de instancia falta o es inválida: salida 2, mensaje comprensible en `stderr` y
  JSON con `state: null`, `last_terminal: null` y `error: {code: "instance_configuration_invalid",
  message}`. No se devuelve `not_started` ni se afirma que no existe una operación activa.
- Si el archivo de lock existe pero no puede leerse: salida 2, mensaje comprensible en `stderr` y JSON
  con `state: null`, `last_terminal: null` y `error: {code: "lock_unreadable", message}`. Aplica también cuando el lock está tomado pero su registro
de propietario falta o no puede interpretarse. No se devuelve `not_started` ni se afirma que no existe
una operación activa.
- En los tres casos de error no se crea marcador, lock, directorio ni otro archivo, y no se repara,
  borra ni sobrescribe información.
- El código 2 por argumentos inválidos de la CLI se distingue del código 2 por reporte ilegible por el
  mensaje: el primero imprime el uso y no emite el objeto JSON de estado.

## Atomicity boundary

No existe atomicidad entre Qdrant y SQLite. SQLite decide la disponibilidad de documentos y
versiones. Si el commit en SQLite falla después de escribir puntos o publicar un alias, la versión
queda no disponible, las consultas la excluyen y el reintento converge sin duplicados por la limpieza
`version_id` y los UUIDv5 deterministas. No se declara consistencia a partir de puntos sin versión
disponible.

## Idempotency

- Cada ejecución crea una generación nueva; no duplica puntos en la generación activa.
- Repetir una reconstrucción correcta no cambia el conjunto lógico de fragmentos.
- Un `chunk_id` repetido en SQLite no debe duplicarse; la clave es el `chunk_id`.

## Interruption and partial failure

- Una interrupción deja una generación no activa; el alias no cambia.
- Un fallo parcial reporta fragmentos faltantes/extra y no se declara completado.
- El reintento crea otra generación o reutiliza la generación parcial solo si se valida de nuevo.
- No se borra la generación anterior ni Chroma.

## Incompatibilities

- Modelo o dimensión distinta: fallar antes de escribir; no mezclar.
- Versión de servidor/cliente incompatible: fallar antes de escribir.
- Fragmento sin texto o metadatos: reportar y excluir; no marcar el alcance como completo.
- Fragmento con dimensión o modelo incompatible: reportar y excluir; no mezclar.
- Punto huérfano en Qdrant (sin `chunk_id` correspondiente en SQLite): contar como discrepancia
  (`extra_chunks`), reportar y nunca resolverlo como cita.
- Alias ausente: reportar índice no disponible; no consultar una generación parcial.

## First document vs initial rebuild

- **Primer documento:** la ingesta crea generación/alias del caso cuando el primer documento queda
  validado. No exige ejecutar esta reconstrucción completa.
- **Reconstrucción inicial:** crea una generación nueva para todos los documentos existentes de un
  alcance y cambia el alias. Es mantenimiento, no el flujo normal de alta.
- Un caso sin documentos no requiere colección ni alias; el corpus público sigue disponible.

## Concurrency

- Reconstrucción, ingesta de documentos, `ingest_corpus.py` y `prepare_demo.py` comparten
  `<SECGUARD_STORAGE_DIR>/qdrant-control/locks/<instance_id>.lock`, un lock de archivo exclusivo
  entre procesos (no en memoria). La primitiva vive en `retrieval/instance.py`; los escritores solo la
  usan.
- Mientras posee el lock, el proceso registra `{operation, attempt_id, pid, started_at}` con
  `operation` en `ingestion` o `rebuild`. La autoridad de actividad es el bloqueo real: si el lock
  puede adquirirse, el registro es obsoleto y se ignora, también tras una terminación abrupta.
- Si la reconstrucción tiene el lock, la ingesta recibe `reconstruction_in_progress` (409) y no
  escribe.
- Si la ingesta tiene el lock, la reconstrucción falla con `ingestion_in_progress` (409); no espera
  indefinidamente ni crea una cola.
- Las consultas no toman el lock; usan el alias anterior.
- El sistema operativo libera el lock si el proceso muere; el reporte queda `failed` o `partial`, el
  registro residual se ignora y el alias no cambia.
- Instancias distintas usan locks distintos y pueden trabajar en el mismo servidor Qdrant.

## Explicit non-goals

- Migrar o exportar vectores de Chroma.
- Escribir en Chroma.
- Comparar Chroma/Qdrant.
- Retornar a Chroma.
- Borrar archivos, bases o colecciones ajenas.
- Crear tablas SQLite nuevas.
