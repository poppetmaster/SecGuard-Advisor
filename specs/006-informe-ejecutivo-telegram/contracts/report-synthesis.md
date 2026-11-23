# Contrato — Síntesis del informe (`report-synthesis-v1`)

**Alcance**: define la salida de la síntesis opcional del informe, su validación y su representación.
No autoriza llamadas pagadas ni sustituye el informe factual.

## 1. Esquema

```json
{
  "schema_version": "report-synthesis-v1",
  "summary": {
    "text": "Texto breve en español",
    "claim_refs": ["cards.pending.value"]
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
`focus` y `recommendations` pueden ser listas vacías. `summary.text` no puede estar vacío.

## 2. Reglas de cifras y afirmaciones

1. **Las cifras se renderizan desde el dataset**, no desde el texto del modelo. La plantilla toma
   `value`, `unit` y `denominator` de la ruta indicada en `claim_refs`.
2. **No se prohíben todos los dígitos.** Se permiten identificadores válidos:
   - `report_id`, `report_version_number`, secuencia de snapshot;
   - `QID <números>` y `CVE-AAAA-NNNN`;
   - fechas ISO (`AAAA-MM-DD`) y años de una norma;
   - identificadores de fragmento o cita.
3. **Números libres**: cualquier token numérico que no sea un identificador permitido ni provenga de
   un `claim_ref` se rechaza. No se acepta un número suelto aunque exista en el dataset.
4. **Tipo de afirmación**: el `claim_ref` declara `metric_type` (`count`, `ratio`, `comparison`) y su
   `denominator`. Un conteo no puede presentarse como porcentaje sin denominador; una comparación
   requiere ambos lados.
5. **Semántica**: que un número exista en el dataset no valida la frase. El validador comprueba que la
   ruta, el tipo, la unidad y el denominador correspondan a la afirmación. Una afirmación cuantitativa
   sin `claim_ref` se rechaza.
6. **Identificadores**: se permiten solo los patrones anteriores; no se aceptan códigos internos,
   rutas, IP, hosts ni nombres de activos.

## 3. Procedencia y referencias documentales

| `basis` | Requisito | Presentación |
|---|---|---|
| `csv_fact` | `claim_refs` no vacío y todos resuelven | Hecho calculado |
| `documentary` | `evidence_refs` no vacío; cada cita existe y el validador la acepta | Referencia documental |
| `agent_proposal` | Sin `claim_refs` cuantitativos; puede tener `caveat` | Propuesta del agente |

### Límite de la validación de citas

La validación de una cita comprueba **existencia, identidad y correspondencia con el fragmento**. No
demuestra que la cita implique semánticamente la recomendación. Por tanto:

- una cita válida no convierte automáticamente una recomendación en «respaldada»;
- si no hay revisión semántica, se muestra «referencia documental; respaldo semántico no verificado»;
- una recomendación sin respaldo comprobado se muestra como `agent_proposal`;
- no se afirma que una cita «demuestra» la recomendación.

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
- Fallback factual por error de proveedor, presupuesto o esquema.
- `test_report_synthesis.py` es la prueba base; `test_automatic_synthesis_policy.py` amplía el caso
  automático sin duplicar la validación.
