# Contrato — Síntesis del informe (`report-synthesis-v1`)

**Alcance**: define la salida de la síntesis opcional del informe, su validación y su representación.
No autoriza llamadas pagadas ni sustituye el informe factual. Los hechos cuantitativos y sus
conclusiones se generan de forma determinista desde el dataset; el modelo solo puede proponer prosa
identificada.

## 1. Esquema

```json
{
  "schema_version": "report-synthesis-v1",
  "summary": {
    "text": "",
    "claim_refs": []
  },
  "focus": [
    {
      "text": "Foco de atención",
      "basis": "csv_fact",
      "claim_refs": ["cards.critical_pending.value"],
      "evidence_refs": []
    }
  ],
  "recommendations": [
    {
      "text": "Recomendación propuesta",
      "basis": "agent_proposal",
      "claim_refs": [],
      "evidence_refs": [],
      "caveat": "Propuesta del agente; no es un hecho del CSV."
    }
  ],
  "limitations": ["Limitación o dato faltante"]
}
```

Campos obligatorios: `schema_version`, `summary`, `focus`, `recommendations`, `limitations`.
`summary` y `focus` son ignorados para los hechos: la aplicación los reemplaza por plantillas
deterministas del dataset. `recommendations` es la única prosa libre y se presenta como propuesta.
`summary`/`focus` pueden venir vacíos; si traen texto, también se validan.

## 2. Reglas de cifras y afirmaciones

1. **Las cifras se renderizan desde el dataset**, no desde el texto del modelo. Las tarjetas,
gráficas, resumen y focos usan plantillas deterministas vinculadas a métricas; la prosa del modelo
no produce cifras ni hechos cuantitativos.
2. **No se prohíben todos los dígitos.** Se permiten identificadores válidos:
   - `report_id`, `report_version_number`, secuencia de snapshot;
   - `QID <números>` y `CVE-AAAA-NNNN`;
   - fechas ISO (`AAAA-MM-DD`) y años de una norma;
   - identificadores de fragmento o cita.
3. **Números libres**: cualquier token numérico que no sea un identificador permitido ni provenga de
   un `claim_ref` se rechaza. No se acepta un número suelto aunque exista en el dataset.
4. **Contradicciones**: si un texto contiene una fórmula de ausencia («sin», «no hay», «ninguna»,
   «cero») sobre una categoría cuya métrica es positiva, la síntesis se rechaza. Ejemplo obligatorio:
   con `cards.critical_pending.value = 2`, «Sin vulnerabilidades críticas pendientes» no es válido.
5. **Todos los campos de texto**: resumen, focos, recomendaciones, limitaciones y `caveat` se validan
   contra números libres, IP, nombres internos, hosts y contradicciones. Las limitaciones no son una
   vía para introducir contenido prohibido.
6. **Identificadores**: se permiten solo los patrones anteriores; no se aceptan códigos internos,
   rutas, IP, hosts ni nombres de activos.

## 3. Procedencia y referencias documentales

| `basis` | Requisito | Presentación |
|---|---|---|
| `csv_fact` | `claim_refs` no vacío y todos resuelven; el texto no introduce cifras | Hecho calculado |
| `documentary` | `evidence_refs` no vacío; cada cita existe y está en el alcance permitido | Referencia documental propuesta |
| `agent_proposal` | Sin cifras libres; puede tener `caveat` | Propuesta del agente |

### Límite de la validación de citas

La validación de una cita comprueba **existencia, identidad y correspondencia con el fragmento**. No
demuestra que la cita implique semánticamente la recomendación. Por tanto:

- una cita válida no convierte automáticamente una recomendación en «respaldada»;
- si no hay revisión semántica, se muestra «referencia documental; respaldo semántico no verificado»;
- una recomendación sin respaldo comprobado se muestra como `agent_proposal`;
- no se afirma que una cita «demuestra» la recomendación;
- una referencia inexistente o fuera de alcance se rechaza y produce fallback factual; no se vuelve
  válida por cambiar la etiqueta a `agent_proposal`.

## 4. Fallback factual

Si la síntesis falla, no cumple el esquema, no cabe en presupuesto, el proveedor no está autorizado o
la validación numérica/referencial falla:

- `synthesis_status` queda en `not_requested`, `unavailable` o `failed`;
- se conserva el informe factual con cifras, gráficas, limitaciones y cobertura;
- se muestra «Sin síntesis de IA»;
- no se inventan explicaciones ni recomendaciones;
- no se realiza una llamada externa si no hay autorización y presupuesto.

## 5. Pruebas mínimas

- Síntesis válida con `csv_fact` y `claim_refs` que resuelven.
- Número libre rechazado; identificador `QID`/`CVE`/versión permitido.
- Conteo presentado como proporción sin denominador: rechazado.
- `documentary` sin cita: rechazado.
- Cita existente pero sin respaldo semántico: se muestra como referencia con advertencia o propuesta,
  nunca como respaldo verificado.
- `agent_proposal` sin cifras: aceptado y rotulado.
- Contradicción de ausencia con métrica positiva: rechazada.
- Limitación con IP o cifra libre: rechazada.
- Cita inexistente: rechazada; cita existente: propuesta con advertencia.
- Fallback factual por error de proveedor, presupuesto o esquema.
- `test_report_synthesis.py` es la prueba base; `test_automatic_synthesis_policy.py` amplía el caso
  automático sin duplicar la validación.
