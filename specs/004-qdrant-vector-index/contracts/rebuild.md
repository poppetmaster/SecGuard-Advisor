# Contract: Qdrant rebuild

**Scope**: reconstrucción limpia desde SQLite. No implementa código.

## Trigger

Comando explícito, por ejemplo `make qdrant-rebuild` o
`uv run python scripts/rebuild_qdrant.py`. No se ejecuta automáticamente al arrancar la aplicación.

## Preconditions

- Qdrant 1.20.0 responde en `/readyz`.
- `qdrant-client==1.20.0` es compatible con el servidor.
- SQLite existe y conserva documentos, versiones y fragmentos.
- El modelo de embeddings local `embeddinggemma` está disponible con dimensión 768.
- No hay otra reconstrucción activa (lock de mantenimiento).
- El almacenamiento de prueba es separado de la instancia del usuario.

## Steps

1. Validar versión, conexión y compatibilidad.
2. Leer SQLite y seleccionar documentos/versiones vigentes disponibles.
3. Validar texto, metadatos, modelo y dimensión de cada fragmento.
4. Regenerar embeddings con el mismo modelo local, por lotes.
5. Crear una colección de generación nueva por alcance.
6. Subir puntos con UUIDv5 determinista y payload de procedencia.
7. Comparar el conjunto de `chunk_id` esperado contra Qdrant; verificar conteos y muestras.
8. Cambiar el alias activo solo si la validación es completa.
9. Conservar la generación anterior para recuperación.
10. Escribir un reporte JSON de reconstrucción.

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

## Concurrency

- La reconstrucción toma un lock local de mantenimiento.
- La ingesta concurrente recibe un error explícito de “reconstrucción en curso”; no escribe a medias.
- Las consultas siguen usando el alias anterior hasta el cambio.
- No hay escritura dual.

## Explicit non-goals

- Migrar o exportar vectores de Chroma.
- Escribir en Chroma.
- Comparar Chroma/Qdrant.
- Retornar a Chroma.
- Borrar archivos, bases o colecciones ajenas.
- Crear tablas SQLite nuevas.
