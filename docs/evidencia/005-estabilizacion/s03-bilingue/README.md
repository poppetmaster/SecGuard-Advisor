# S03 — evaluación bilingüe (versión nueva)

**Versión del evaluador**: `005-s03-bilingual-v2`
**Datos**: respuestas conservadas de la evaluación histórica de 30 escenarios y de la pasada
focalizada con 4096 tokens. **No se repitieron llamadas pagadas.**

## Criterio propuesto

La pregunta de S03 exige «al menos dos riesgos» y una recomendación. El criterio histórico exigía
literalmente `prompt injection`, `sensitive information` y `supply chain`. El nuevo evaluador
comprueba conceptos equivalentes en español e inglés:

- al menos **dos riesgos OWASP distintos** (inyección de prompts, información sensible, cadena de
  suministro, agencia excesiva, salida insegura, fuga de prompt, envenenamiento de datos, consumo
  ilimitado, desinformación, debilidades de embeddings);
- al menos una recomendación o control;
- al menos una cita aceptada por el validador.

Una respuesta vacía se deja **sin determinar**; no se convierte en aprobada ni en fallo por falta de
texto. Los resultados históricos no se reescriben: se muestra el resultado antiguo y el nuevo.

## Resultados

| Muestra | Proveedor | Resultado histórico | Resultado v2 | Conceptos detectados |
|---|---|---|---|---|
| Histórica 30 | Ollama | fallido | fallido | prompt injection; sin segundo riesgo |
| Histórica 30 | DeepSeek | fallido | **sin determinar** | sin respuesta conservada |
| Histórica 30 | Claude | fallido | **sin determinar** | sin respuesta conservada |
| Focalizada 4096 | DeepSeek | fallido | **aprobado v2** | prompt injection, excessive agency |
| Focalizada 4096 | Claude | fallido | **aprobado v2** | prompt injection, excessive agency, insecure output |

El resultado histórico y el criterio original quedan intactos. La aprobación v2 no borra el fallo
histórico ni se presenta como una nueva evaluación funcional completa; es un recálculo explícito
sobre respuestas ya conservadas.

## Artefactos

- `s03-recalculado.json`: fila por muestra con ambos resultados, conceptos, citas y extracto.
- `resumen.json`: resumen de la versión y criterios.

## Límites

- El evaluador es una comprobación de conceptos, no una revisión semántica humana.
- Si una respuesta no se conservó, queda sin determinar.
- El criterio histórico y las métricas anteriores siguen siendo la referencia de la evaluación
  original.
