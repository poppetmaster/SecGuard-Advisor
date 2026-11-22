# Contract: Privacy and data boundary (005)

**Fecha**: 2026-11-22

## Regla base

Una credencial no autoriza el envío de datos. Todo proveedor externo exige una autorización
explícita por caso, vigente y revocable, antes de construir o enviar el prompt.

## Autorización externa

`ExternalProcessingAuthorization` registra:

- `case_id`
- `scope`: `public_corpus` o `fictional_case` (nunca `private_case` en 005)
- `policy_version`
- `authorized_by` (identidad declarada; no autenticación)
- `authorized_at`, `revoked_at`, `note`

Sin una fila vigente:

- No se llama al proveedor.
- No se llama al contador de tokens externo.
- El turno falla con `external_processing_blocked` (HTTP 403).

## Contenido permitido

| Elemento | Proveedor externo |
|---|---|
| Corpus público | Permitido con autorización `public_corpus` |
| Documentos ficticios del caso | Permitido con autorización `fictional_case` |
| Documentos privados del caso | Bloqueado en 005 |
| Pregunta del usuario | Solo si el caso está autorizado; se minimiza |
| Historial de conversación | Solo turnos permitidos; se reduce por contexto y política |
| Fragmentos documentales | Solo de los espacios permitidos |
| Contexto declarado del caso | Solo si está en el alcance autorizado |
| Registros Qualys, filas, CVE, activos, resultados derivados | **Nunca** |
| Resultados de `findings_query` sintéticos | Solo en `fictional_case` y `origin=synthetic` |
| Resultados de `findings_query` importados o mixtos | **Nunca** |
| Filas Qualys, CVE, activos y derivados | **Nunca** |
| Credenciales | Nunca como contenido; solo cabecera de autenticación |

## Herramientas

- Con proveedor externo, `findings_query` solo se ejecuta en un caso `fictional_case` con
  `origin=synthetic`. Un resultado importado, mixto o de un caso privado falla con
  `external_tool_blocked` antes de ejecutar la herramienta.
- La alternativa para hallazgos importados es usar Ollama.
- No se envía un resultado de herramienta importado «anonimizado» sin política aprobada.

## Minimización y redacción

Antes de cualquier salida externa:

- Eliminar rutas absolutas, secretos, identificadores de infraestructura y metadatos internos.
- Enviar solo los fragmentos seleccionados, no el documento completo ni el CSV.
- No incluir `Results` de Qualys, filas crudas, ni el manifiesto.
- No incluir el contenido de `storage/`, checkpoints ni claves.
- Registrar en la ejecución qué política y autorización se aplicaron, sin el contenido.

## LangSmith

- Política independiente.
- Activar un proveedor externo no habilita LangSmith ni amplía su contenido permitido.
- La traza sigue enviando solo metadatos acotados; no pregunta, prompts, documentos, argumentos ni
  resultados.
- `LANGSMITH_TRACING=false` sigue siendo el valor seguro por defecto.

## Afirmaciones prohibidas

- No se declara retención cero.
- No se declara ausencia de entrenamiento.
- No se declara garantía de privacidad.
- Solo se afirma lo que la documentación del proveedor y la configuración aplicada permitan
  verificar, con fecha y fuente.
