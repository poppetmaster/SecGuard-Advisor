# Handoff — 005 Generador configurable

**Fecha**: 2026-11-22
**Estado**: planificación completa; implementación no iniciada.
**Rama**: `004-qdrant-vector-index` (sin rama 005 creada en esta preparación).

## 1. Qué está listo

- `specs/005-generador-configurable/spec.md`: 4 historias y 33 requisitos funcionales.
- `research.md`: 11 decisiones con fuentes y fecha.
- `plan.md`: arquitectura, constitución, estructura, fases y riesgos.
- `data-model.md`: configuración, columnas/tablas, invariantes y migración.
- `contracts/`: adaptador, configuración, presupuesto y privacidad.
- `quickstart.md`: configuración local, flujo, pruebas y comparación.
- `tasks.md`: 42 tareas en 3 entregas, con dependencias y criterios de cierre.
- `checklists/requirements.md`: completo.
- `docs/planificacion/005-ultimo-resultado.md`: informe autocontenido.
- Constitución y `AGENTS.md`: decisión de mantener Ollama junto a los externos registrada.

## 2. Decisiones clave

1. **Un solo grafo** y un protocolo `Generator`; los adaptadores solo traducen transporte, esquema,
   contexto, uso y errores.
2. **Sin fallback** y sin cambio de proveedor en un turno.
3. **Ollama predeterminado** y siempre disponible; externos requieren credencial, presupuesto y
   autorización por caso.
4. **Datos externos**: solo `public_corpus` o `fictional_case`; `private_case` no se autoriza en 005.
5. **Qualys fuera**: nunca se envían filas, CVE, activos ni derivados. `findings_query` externo solo
   con `origin=synthetic` en `fictional_case`; importados se bloquean.
6. **Contexto**: GGUF solo Ollama; Anthropic `count_tokens`; DeepSeek estimador conservador validado
   contra uso observado.
7. **Costo**: tarifa fechada y versionada; `unknown` si falta uso; nunca cero inventado.
8. **Presupuesto**: reserva antes de la llamada, liquidación con uso observado y reconciliación al
   arrancar; `0` bloquea externos.
9. **Secretos**: `.env` local, `SecretStr`, plantilla vacía y redacción centralizada.
10. **Modelos verificados el 2026-11-22**: `claude-haiku-5-5` y `deepseek-flash`; revalidar antes de
    implementar y aceptar.

## 3. Orden de implementación

1. **Entrega 1 (T001–T014)** — configuración, protocolo, esquema tipado, registro de proveedor/modelo
   y regresión Ollama. No requiere presupuesto externo.
2. **Entrega 2 (T015–T034)** — adaptadores DeepSeek/Anthropic, contexto, costo, presupuesto,
   autorización, redacción, bloqueo de herramienta importada y evidencia.
3. **Entrega 3 (T035–T042)** — comparación, regresión, documentación y aceptación.

## 4. Dependencias que bloquean la implementación externa

- Presupuesto aprobado (`SECGUARD_EXTERNAL_BUDGET_USD` > 0).
- Credenciales locales para la comparación.
- Confirmación del alcance `public_corpus`/`fictional_case`.
- Revalidación de identificadores y precios.

Sin ellas, la Entrega 1 puede implementarse y la Entrega 2 puede avanzar contra servidores simulados;
las pruebas externas reales deben omitirse con motivo.

## 5. Riesgos

| Riesgo | Mitigación |
|---|---|
| Fuga de contenido privado | Autorización por caso, minimización y pruebas de denegación |
| Esquema incompatible | `ToolDecision` tipado y pruebas de contrato por proveedor |
| Contexto mal medido | Medición por proveedor y margen; reducción antes de enviar |
| Costo real mayor | Reserva conservadora, diferencia registrada, sin promesa de tope exacto |
| Secreto en error | Redacción centralizada y pruebas de escaneo |
| Modelo/precio cambia | Tarifa fechada y revalidación obligatoria |
| Divergencia entre proveedores | Mismo grafo, mismas pruebas y comparación reproducible |

## 6. Cómo reanudar

1. Leer `spec.md`, `plan.md`, `tasks.md` y `005-ultimo-resultado.md`.
2. Confirmar presupuesto y alcance con el responsable.
3. Implementar la Entrega 1 en orden T001–T014, con prueba antes de implementación.
4. No ejecutar llamadas pagadas hasta que el presupuesto esté aprobado.
5. No modificar `storage/`, `storage/demo`, Chroma, Qdrant ni datos existentes.
6. Mantener `LANGSMITH_TRACING=false` salvo autorización independiente.

## 7. Archivos

- `specs/005-generador-configurable/` (todos los artefactos).
- `docs/planificacion/005-ultimo-resultado.md`.
- `docs/planificacion/handoff-005.md`.
- `.specify/memory/constitution.md` (fila de decisión 2026-11-22).
- `AGENTS.md` (nota de preparación de 005).
- `.specify/feature.json` apunta a 005.
