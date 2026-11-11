# Contract: Qdrant rebuild

**Scope**: reconstrucción limpia desde SQLite. No implementa código.

## Trigger

Comando explícito, por ejemplo `make qdrant-rebuild` o
`uv run python scripts/rebuild_qdrant.py`. No se ejecuta automáticamente al arrancar la aplicación.

## Preconditions

- Qdrant 1.20.0 responde en `/readyz`.
- `qdrant-client==1.20.0` es compatible con el servidor.
- `SECGUARD_INSTANCE_ID` está definido, validado y coincide con
  `storage/qdrant/instances/<instance_id>.json` y el hash del storage.
- SQLite existe y conserva documentos, versiones y fragmentos.
- El modelo de embeddings local `embeddinggemma` está disponible con dimensión 768.
- No hay otra reconstrucción o ingesta activa (lock de instancia).
- El almacenamiento de prueba es separado de la instancia del usuario.

## Steps

1. Validar instancia/namespace, versión, conexión y compatibilidad.
2. Adquirir el lock de archivo de la instancia; si está ocupado, fallar con
   `ingestion_in_progress`.
3. Leer SQLite y seleccionar documentos/versiones vigentes disponibles.
4. Validar texto, metadatos, modelo y dimensión de cada fragmento.
5. Regenerar embeddings con el mismo modelo local, por lotes.
6. Crear una colección de generación nueva por alcance con el namespace de instancia.
7. Subir puntos con UUIDv5 determinista y payload de procedencia.
8. Comparar el conjunto de `chunk_id` esperado contra Qdrant; verificar conteos y muestras.
9. Cambiar el alias activo solo si la validación es completa; si falla, conservar el alias anterior.
10. Conservar la generación anterior para recuperación.
11. Escribir un reporte JSON bajo `storage/qdrant/reports/<instance_id>/`.
12. Liberar el lock en `finally`.

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
- Punto huérfano en Qdrant: reportar; no resolverlo como cita.
- Alias ausente: reportar índice no disponible; no consultar una generación parcial.

## First document vs initial rebuild

- **Primer documento:** la ingesta crea generación/alias del caso cuando el primer documento queda
  validado. No exige ejecutar esta reconstrucción completa.
- **Reconstrucción inicial:** crea una generación nueva para todos los documentos existentes de un
  alcance y cambia el alias. Es mantenimiento, no el flujo normal de alta.
- Un caso sin documentos no requiere colección ni alias; el corpus público sigue disponible.

## Concurrency

- Reconstrucción e ingesta comparten `storage/qdrant/locks/<instance_id>.lock`, un lock de archivo
  exclusivo entre procesos (no en memoria).
- Si la reconstrucción tiene el lock, la ingesta recibe `reconstruction_in_progress` y no escribe.
- Si la ingesta tiene el lock, la reconstrucción falla con `ingestion_in_progress`; no espera
  indefinidamente ni crea una cola.
- Las consultas no toman el lock; usan el alias anterior.
- El sistema operativo libera el lock si el proceso muere; el reporte queda `failed` o `partial` y
  el alias no cambia.
- Instancias distintas usan locks distintos y pueden trabajar en el mismo servidor Qdrant.

## Explicit non-goals

- Migrar o exportar vectores de Chroma.
- Escribir en Chroma.
- Comparar Chroma/Qdrant.
- Retornar a Chroma.
- Borrar archivos, bases o colecciones ajenas.
- Crear tablas SQLite nuevas.
