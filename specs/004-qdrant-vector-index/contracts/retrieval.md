# Contract: Retrieval and citations over Qdrant

**Scope**: comportamiento de consulta después de la migración. No implementa código.

## Query scopes

Cada consulta busca únicamente:

1. el alias activo del corpus público permitido;
2. el alias activo del caso actual.

Nunca busca en otro caso, en una generación parcial ni en una colección sin alias.

## Versions

- Búsquedas nuevas: solo fragmentos de la versión vigente disponible.
- Versiones superadas: no se indexan para búsquedas nuevas.
- Citas históricas: se resuelven desde SQLite por `chunk_id` y `version_id`, aunque la versión no
  esté en Qdrant.
- Un documento no disponible no se indexa; su cita histórica sigue resolviendo si el fragmento
  persistido existe.

## Score and threshold

- Qdrant usa similitud coseno; mayor score es más relevante.
- La aplicación aplica un umbral calibrado para Qdrant, no el 0.35 de Chroma.
- El umbral propuesto y el observado se registran por separado.
- No se exige igualdad exacta de orden con Chroma.

## Result resolution

1. Qdrant devuelve point ID, score y payload.
2. La aplicación toma `payload.chunk_id` y resuelve `DocumentChunk`, `DocumentVersion` y
   `Document` en SQLite.
3. Descarta el resultado si el fragmento no existe, la versión no está disponible, el documento no
   pertenece al alcance o la versión no es la vigente para una búsqueda nueva.
4. Devuelve documento, versión, página/sección, localizador, procedencia y score.
5. Una cita histórica se valida contra el fragmento persistido y su versión, no contra Qdrant.

## Empty and error behavior

- Sin resultados: `empty`/ausencia de evidencia; no se inventa cita.
- Qdrant inaccesible: error explícito; no se usa Chroma.
- Alias ausente: error de índice no disponible; no se consulta una generación parcial.
- Configuración incompatible: error explícito; no se devuelven resultados parciales.
- Registros Qualys: nunca aparecen en resultados documentales.

## No changes

- No se cambia la memoria, la conversación, la semántica de `findings_query` ni la revisión humana.
- No se cambia el modelo de embeddings en 004.
