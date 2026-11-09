# Evidencia sintética — 002 US3 (filtros y presentación)

Capturas tomadas con dos instantáneas sintéticas confirmadas (`qualys_synthetic_valid.csv` y
`qualys_synthetic_mixed.csv`) en almacenamiento temporal, sin datos reales y con
`LANGSMITH_TRACING=false`.

| Archivo | Escenario |
|---|---|
| `vulnerabilities-empty-desktop.png` | Caso sin importaciones confirmadas |
| `vulnerabilities-empty-filter-desktop.png` | Importación confirmada con filtros sin coincidencias |
| `vulnerabilities-filters-desktop.png` | Filtro de prioridad conjunta con instantánea histórica |
| `vulnerabilities-fixed-antecedent-desktop.png` | `Fixed` con ambos indicadores positivos como antecedente |
| `vulnerabilities-mobile-390.png` | Sección en móvil 390 |
| `vulnerabilities-mobile-320.png` | Sección en 320 px |

Comprobaciones realizadas:

- El filtro de estado conserva `import_id` y muestra «Estado: Fixed» o «Estado: Revisión manual».
- El filtro de severidad muestra la etiqueta del proyecto y conserva la instantánea elegida.
- El filtro de prioridad devuelve solo los registros con explotabilidad y malware positivos.
- Los filtros de explotabilidad, malware, activo, QID y CVE se combinan sin multiplicar filas.
- La instantánea histórica permanece seleccionada al aplicar y limpiar filtros; la URL conserva
  `import_id` y los parámetros.
- Los estados vacíos distinguen «Sin importaciones confirmadas» de «Sin registros para estos
  filtros» y no afirman ausencia de vulnerabilidades ni riesgo bajo.
- Los valores inválidos muestran un error visible y no cambian la instantánea.
- No hay errores ni advertencias en consola; los recursos locales responden sin fallos.
- El menú muestra únicamente «Vulnerabilidades».

Estas capturas son evidencia de interfaz con datos sintéticos. No constituyen la aceptación integral
T039 ni una verificación de privacidad completa.
