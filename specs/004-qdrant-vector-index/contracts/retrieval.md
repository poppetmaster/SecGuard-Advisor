# Contract: Retrieval and citations over Qdrant

**Scope**: comportamiento de consulta después de la migración. No implementa código.

## Query scopes

Cada consulta busca únicamente:

1. el alias activo del corpus público permitido;
2. el alias activo del caso actual, dentro del namespace de instancia.

Nunca busca en otro caso, en otra instancia, en una generación parcial ni en una colección sin
alias.

## Empty scope vs missing index

“Esperado” se calcula desde SQLite (documentos/versiones disponibles e indexables), no desde la
ausencia de alias.

| Estado | Resultado |
|---|---|
| Caso sin documentos privados disponibles | Se omite el alcance privado; se consulta el público. |
| Caso con documentos esperados pero sin alias | `case_index_unavailable`; no se responde solo con público. |
| Público con documentos esperados pero sin alias | `public_index_unavailable`; no se declara falta de evidencia. |
| Público no configurado o vacío | Se omite; el caso puede continuar. |
| Qdrant inaccesible | `qdrant_unavailable`; sin Chroma. |
| Alias presente sin resultados | `empty` normal; no se inventa cita. |

Un fallo de índice nunca se transforma en “no existe evidencia”.

## Versions

- Búsquedas nuevas: solo fragmentos de la versión vigente disponible.
- Versiones superadas: no se indexan para búsquedas nuevas.
- Citas históricas: se resuelven desde SQLite por `chunk_id` y `version_id`, aunque la versión no
  esté en Qdrant.
- Un documento no disponible no se indexa; su cita histórica sigue resolviendo si el fragmento
  persistido existe.

## Score and threshold

- Qdrant usa similitud coseno; mayor score es más relevante.
- La aplicación aplica el umbral calibrado **0.5033** (Qdrant servidor 1.20.0 + `embeddinggemma`), no
  el 0.35 de Chroma.
- Calibración y evaluación usan conjuntos distintos; el umbral se congela antes de la evaluación
  final. El reporte registra modalidad, versión, modelo, dimensión, métrica, `top_k`, umbral, fecha y
  hash del conjunto.
- La evaluación final del Corte 6 pasó con 6/6 recuperaciones, 0 no pertinentes aceptadas, 0 fugas,
  versión vigente y cita histórica válida.
- No se exige igualdad exacta de orden con Chroma.

## Result resolution

1. Qdrant devuelve point ID, score y payload.
2. La aplicación toma `payload.chunk_id` y resuelve `DocumentChunk`, `DocumentVersion` y
   `Document` en SQLite.
3. Descarta el resultado si el fragmento no existe, la versión no está disponible, el documento no
   pertenece al alcance o la versión no es la vigente para una búsqueda nueva.
4. Un punto sin fragmento correspondiente en SQLite se reporta como discrepancia y nunca se convierte
   en cita.
5. Devuelve documento, versión, página/sección, localizador, procedencia y score.
6. Una cita histórica se valida contra el fragmento persistido y su versión, no contra Qdrant.

## Availability and failures

- No existe atomicidad entre Qdrant y SQLite: SQLite decide la disponibilidad de documentos y
  versiones, y una consulta excluye toda versión no disponible aunque sus puntos existan.
- Un fallo de índice detiene la respuesta documental: no se ejecuta la generación, no se produce una
  abstención por falta de evidencia y el paso y la ejecución se registran con el error clasificado.
- Códigos obligatorios: `qdrant_unavailable` (503), `case_index_unavailable` (503),
  `public_index_unavailable` (503) e `instance_namespace_mismatch` (503). El código se conserva en la
  respuesta y en la evidencia; no se degrada a `internal_error`.

## Empty and error behavior

- Sin resultados: `empty`/ausencia de evidencia; no se inventa cita.
- Qdrant inaccesible: error explícito; no se usa Chroma.
- Alias ausente: error de índice no disponible; no se consulta una generación parcial.
- Configuración incompatible: error explícito; no se devuelven resultados parciales.
- Registros Qualys: nunca aparecen en resultados documentales.

## Namespace and instance

- La consulta usa `SECGUARD_INSTANCE_ID` y los alias de esa instancia.
- Un namespace incompatible es un error de configuración, no una consulta vacía.
- Dos instancias con el mismo `case_id` no comparten alias, colecciones ni resultados.
- El corpus público de una instancia no es visible desde otra.

## No changes

- No se cambia la memoria, la conversación, la semántica de `findings_query` ni la revisión humana.
- No se cambia el modelo de embeddings en 004.
