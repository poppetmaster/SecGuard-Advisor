# 005 — Último resultado (preparación documental)

**Fecha**: 2026-11-22 (America/Bogota, `-05`)
**Rama**: `004-qdrant-vector-index` (no se creó una rama de 005 en esta preparación)
**Estado**: **planificación completa; nada implementado, nada aceptado.**
**Alcance**: paquete documental de 005, listo para revisión previa a implementación.

## Dictamen

El paquete de 005 está **listo para implementar por entregas**, no para declarar la funcionalidad
disponible. Se generaron especificación, investigación, plan, modelo de datos, contratos, quickstart,
tareas y el análisis de consistencia documental. No se instalaron dependencias, no se modificó código
de producto, no se ejecutaron llamadas pagadas y no se tocaron datos existentes.

Prerequisito para implementar: aprobar un presupuesto externo y decidir si se autoriza el alcance
`fictional_case` para las primeras pruebas. Sin presupuesto, el proveedor externo queda bloqueado por
configuración y la entrega 1 (Ollama) sigue siendo la única operativa.

## Decisiones autorizadas registradas

- Ollama local se mantiene disponible con el modelo actual.
- Se añaden adaptadores para DeepSeek y Anthropic (Claude Haiku); no se selecciona un proveedor.
- EmbeddingGemma sigue local y Qdrant sigue siendo el índice documental.
- La selección es explícita por configuración local; no hay fallback ni cambio en un turno.
- El archivo con secretos no se versiona; se entrega plantilla sin credenciales.
- No se añaden otros proveedores, Telegram, informes nuevos ni P1–P4.
- La decisión se registró en `.specify/memory/constitution.md` (fila 2026-11-22) y en `AGENTS.md`.

## Identificadores y tarifas verificados

Verificación realizada el **2026-11-22** en documentación oficial. Debe revalidarse antes de
implementar y antes de aceptar, porque modelos y precios cambian.

| Proveedor | Identificador de API | Contexto / salida | Tarifa base |
|---|---|---|---|
| Anthropic | `claude-haiku-5-5` | 1M / 128K | Entrada $0.10/MTok (prompt ≤100k); salida $0.50/MTok |
| DeepSeek | `deepseek-flash` | 1M / 384K | Entrada cache miss $0.15/MTok off-peak y $0.30 peak; salida $0.60/$1.20; cache hit $0.003/$0.006 |

Fuentes:

- <https://platform.claude.com/docs/en/models/overview>
- <https://platform.claude.com/docs/en/models/haiku-5-5/overview>
- <https://platform.claude.com/docs/en/build-with-claude/token-counting>
- <https://platform.claude.com/docs/en/build-with-claude/structured-outputs>
- <https://api-docs.deepseek.com/quick_start/pricing>
- <https://api-docs.deepseek.com/quick_start/token_usage>
- <https://api-docs.deepseek.com/guides/json_mode>
- <https://api-docs.deepseek.com/guides/thinking_mode>

No se asumió que «Haiku 5.5» o «DeepSeek V4.1 Flash» fueran identificadores de API. Los
identificadores usados son los que la documentación oficial publica.

## Artefactos creados

```text
specs/005-generador-configurable/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── provider-adapter.md
│   ├── configuration.md
│   ├── budget.md
│   └── privacy.md
├── checklists/requirements.md
└── tasks.md
docs/planificacion/005-ultimo-resultado.md
docs/planificacion/handoff-005.md
```

También se actualizó `.specify/feature.json` para apuntar a 005.

## Entregas y tareas

| Entrega | Tareas | Cierre |
|---|---|---|
| 1. Configuración y contrato común, conservando Ollama | T001–T014 | Arranque con `ollama` sin cambios; configuración externa incompleta falla claro; selección única; esquema tipado; proveedor/modelo registrados. |
| 2. Adaptadores externos y controles de datos, contexto y costos | T015–T034 | DeepSeek/Anthropic contra servidor simulado; contexto por proveedor; presupuesto con reserva/liquidación; bloqueo de datos privados; sin secretos. |
| 3. Comparación, regresión y documentación | T035–T042 | Comparación reproducible; regresión completa; aceptación solo con evidencia; documentación final. |

Detalle completo en [tasks.md](../../specs/005-generador-configurable/tasks.md).

## Hallazgos de diseño relevantes

1. **`ToolDecision.arguments` debe ser tipado.** Un `dict` libre no produce un esquema útil para
   Anthropic Structured Outputs. Se define un esquema acotado compatible con `findings_query`.
2. **El tokenizador GGUF no sirve para externos.** Anthropic tiene conteo gratuito; DeepSeek
   devuelve uso observado y publica tokenizador fuera de línea. La primera entrega usa un estimador
   conservador para DeepSeek y valida contra el uso observado.
3. **DeepSeek JSON Output puede devolver contenido vacío.** Se trata como salida inválida y se aplica
   la reparación acotada existente.
4. **La herramienta de hallazgos necesita una regla explícita.** Con proveedor externo solo se
   permite `findings_query` en `fictional_case` con `origin=synthetic`; datos importados o mixtos se
   bloquean con `external_tool_blocked`.
5. **El presupuesto es local.** Se reserva antes de la llamada y se liquida con el uso observado; no
   se promete un tope exacto del proveedor.
6. **La autorización externa es por caso.** Una credencial no autoriza el envío. Sin autorización
   vigente no se llama ni siquiera al contador de tokens externo.

## Análisis de consistencia documental (única ejecución)

Se aplicó una revisión de consistencia sobre `spec.md`, `plan.md` y `tasks.md` con la constitución.

### Hallazgos corregidos

| Hallazgo | Corrección |
|---|---|
| `ToolDecision.arguments` libre era incompatible con Anthropic | Esquema tipado y acotado (FR-010, T006–T007) |
| La prohibición total de herramientas externas contradecía el principio IV | Regla acotada: solo `fictional_case` + `origin=synthetic`; importados bloqueados (FR-021/FR-031) |
| Faltaba un requisito explícito de bloqueo de herramienta importada | FR-031 y T027–T028 |
| Faltaba un requisito de alcance de autorización | FR-032 |
| Faltaba un requisito de identidad de modelo | FR-033 |
| El plan usaba `db/migrations/` inexistente | Corregido a `alembic/versions/` |
| La aceptación no estaba en la regresión | T040 incluye aceptación ASGI |
| El marker `external` no tenía tarea | T039 |

### Resultado

- No quedan conflictos CRITICAL con la constitución.
- No quedan requisitos funcionales sin tarea asociada.
- No quedan contradicciones entre spec, plan y tasks.
- Persisten dependencias externas que no son defectos documentales: presupuesto aprobado,
  credenciales y decisión de alcance para datos ficticios.

## Verificación realizada

- Lectura de `AGENTS.md`, constitución y código de generación, presupuesto, configuración,
  persistencia y trazas.
- Verificación de documentación oficial de Anthropic y DeepSeek (fecha y fuentes arriba).
- Comprobación de la estructura de Spec Kit y de los artefactos de 004 para consistencia de estilo.
- **No** se ejecutaron pruebas de la aplicación, migraciones, instalaciones ni llamadas externas.

## Pendientes que requieren información del usuario

1. **Presupuesto externo**: monto autorizado y si se permite gasto por ejecución. Sin esto,
   `SECGUARD_EXTERNAL_BUDGET_USD=0` bloquea los proveedores externos.
2. **Alcance de las primeras pruebas externas**: confirmar que se limitan a corpus público y casos
   ficticios (`public_corpus`/`fictional_case`), sin datos privados.
3. **Credenciales**: decidir si se proporcionarán claves locales para la comparación; no se solicitan
   en esta preparación.
4. **Revalidación de modelos**: confirmar los identificadores y precios al iniciar la implementación.
5. **Proveedor definitivo**: no se selecciona en 005; la comparación sustenta una decisión posterior.

## Limitaciones

- No hay implementación, pruebas de la aplicación ni aceptación.
- La comparación entre proveedores no se ejecutó y no se presentan resultados.
- Los precios están fechados y pueden cambiar.
- El modo embebido de Qdrant y la aceptación de 004 no se reabren.
- 003 sigue suspendida; 004 permanece cerrado.

## Próximo paso

Revisar este paquete y, si se aprueba, comenzar por la **Entrega 1 (T001–T014)**: configuración y
contrato común conservando Ollama. La entrega 1 no requiere presupuesto externo.
