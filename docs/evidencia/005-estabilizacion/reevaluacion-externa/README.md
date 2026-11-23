# Reevaluación externa focalizada 005

**Fecha**: 2026-11-23
**Rama**: `005-generador-configurable`
**Tipo**: pasada focalizada, separada de la evaluación histórica de 30 escenarios.
**Autorización**: llamadas reales a DeepSeek y Claude para esta reevaluación, con tope adicional
conjunto de **0,10 USD**.

## 1. Alcance y admisión de gasto

Escenarios ejecutados una sola vez:

- DeepSeek: S03, S04 y S10.
- Claude: S02, S03, S04, S07 y S10.

Preflight:

- Tope adicional: **0,10 USD**.
- Presupuestos configurados conservados: 5 USD global y 5 USD por turno; no se aumentaron.
- Peor caso estimado con 4 500 tokens de entrada, 1 200 de salida y 5 llamadas por escenario:
  **0,047175 USD**, por debajo del tope.
- Instancia temporal con corpus público y casos ficticios; sin CSV Qualys ni derivados.
- No se usó fallback entre proveedores ni se repitieron escenarios fallidos.

Consumo real:

- Costo conocido de solicitudes: **0,010526 USD**.
- Ledger liquidado: **0,010870 USD**.
- Solicitudes registradas: **16**; todas con uso observado; **0** con costo desconocido.
- Presupuesto adicional consumido: **0,010870 USD** de 0,10 USD.
- No se hicieron llamadas fuera de los escenarios indicados.

## 2. Resultados por escenario

| Proveedor | Escenario | Resultado | Estado | Salida | Error | ms | Solicitudes | Tokens E/S/C | Costo conocido | Citas |
|---|---|---|---|---|---|---|---|---|---|---|
| DeepSeek | S03 | fallido | failed | error | `schema_mismatch` | 7 437 | 2 | 6 673 / 1 213 / 2 048 | 0,001428 USD | 0 |
| DeepSeek | S04 | fallido | failed | error | `schema_mismatch` | 6 707 | 2 | 5 935 / 1 213 / 2 688 | 0,001223 USD | 0 |
| DeepSeek | S10 | **aprobado** | succeeded | answered | — | 4 725 | 2 | 3 458 / 833 / 2 688 | 0,000624 USD | 7 |
| Claude | S02 | fallido | failed | error | `truncated_content` | 57 137 | 2 | 10 314 / 1 219 / 0 | 0,001641 USD | 0 |
| Claude | S03 | fallido | succeeded | answered | — | 22 834 | 2 | 10 958 / 1 026 / 0 | 0,001609 USD | 4 |
| Claude | S04 | fallido | failed | error | `schema_mismatch` | 7 857 | 2 | 9 981 / 1 219 / 0 | 0,001608 USD | 0 |
| Claude | S07 | fallido | failed | error | `schema_mismatch` | 9 600 | 2 | 8 892 / 1 315 / 0 | 0,001203 USD | 0 |
| Claude | S10 | fallido | failed | error | `truncated_content` | 10 732 | 2 | 5 807 / 1 219 / 0 | 0,001190 USD | 0 |

Detalle por llamada: `llamadas.csv`. Detalle estructurado: `resultados.json`. Resumen de consumo:
`resumen.json`.

## 3. Diagnóstico observado

**Causa concreta observada:** las seis generaciones fallidas consumieron exactamente **1 200
tokens de salida**, el límite configurado. El diagnóstico seguro registrado distingue dos motivos:

- `schema_mismatch`: DeepSeek S03/S04 y Claude S04/S07. La respuesta llegó al tope y no cumplió el
  esquema (no es un problema del parser).
- `truncated_content`: Claude S02/S10. El proveedor informó finalización por longitud y el JSON
  quedó incompleto.

Por tanto, el límite de salida es una restricción común, pero no todos los fallos se clasifican
como truncamiento puro. Los casos exitosos consumieron 820 tokens (DeepSeek S10) y 1 007 tokens
(Claude S03); los fallidos quedaron justo en el tope. La captura de uso corregida permitió verlo; en
la evaluación histórica el uso se perdía tras el parseo fallido.

- La decisión de herramienta consumió 13 tokens en DeepSeek y 19/43 en Claude; no fue el cuello de
  botella.
- **No se aumentó el límite de 1 200 tokens** durante esta reevaluación. Por tanto, los escenarios
  que necesitan más salida siguen fallando por truncamiento.
- **Claude S03** sí produjo una respuesta con 4 citas y terminó `answered`; el criterio existente
  la marca fallida porque no contiene las palabras clave exigidas por S03. No se cambió el criterio.
- **Claude S07** no ejecutó `findings_query`; solo hizo decisión y generación, y esta última se
  truncó. La ruta de herramienta externa no quedó validada en esta pasada.
- **DeepSeek S10** es el único escenario aprobado: respuesta, citas y estructura de informe.
- No hubo reparaciones ni llamadas a `findings_query` en esta pasada; `llamadas.csv` muestra solo
  decisión y generación.

## 4. Separación de la evaluación histórica

Esta pasada es una **evaluación focalizada distinta**, no una repetición de los 30 escenarios:

- `casos.json` declara `version=005-reevaluation-v1` y el plan con los 8 escenarios.
- `resultados-deepseek.json` y `resultados-anthropic.json` permiten importarla como una evaluación
  separada.
- Importación explícita:

```bash
uv run python scripts/import_evaluation_005.py \
  --evidence-dir docs/evidencia/005-estabilizacion/reevaluacion-externa \
  --storage-dir <almacenamiento>
```

El panel la mostrará como **005-reevaluation-v1**, con su propia muestra; no se mezcla con
`005-evaluation-v1` ni se presenta como comparación completa.

## 5. Dictamen

- **T039 no se cierra.** La infraestructura externa está lista y esta pasada es real, pero la
  cobertura es focalizada y varios escenarios siguen fallando por truncamiento.
- **005 no se declara aceptada para proveedores externos.**
- **No se avanza a 006** con este estado.
- Próximo paso necesario: decidir y aprobar un límite de salida externo suficiente (por ejemplo,
  por encima de los 1 200 tokens actuales) o reducir el esquema/prompt; no se cambia el criterio ni
  se oculta el fallo. La decisión de presupuesto/límite queda pendiente.
- El informe breve local de Ollama y la corrección de citas ya están verificados; no se extrapolan
  a los externos.

## 6. Pruebas y artefactos

- **Ejecutadas**: 8 escenarios externos (16 solicitudes reales); `make check` **736 passed**, 38
  deselected; integraciones afectadas **8 passed**.
- **Omitidas**: pruebas externas de pytest (`1 skipped`, 785 deselected) por falta de la variable de
  autorización de esa suite; corrida completa de 30 escenarios; S08; reintentos del arnés.
- **Fallidas**: 6 escenarios (DeepSeek S03/S04; Claude S02/S04/S07/S10). Claude S03 terminó
  `answered` con 4 citas, pero no cumple el criterio de palabras clave existente.
- Reevaluación real: 0 solicitudes con costo desconocido; véase `llamadas.csv`.
- Sin claves, prompts ni contenido privado en este directorio.
