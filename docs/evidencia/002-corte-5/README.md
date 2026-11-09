# Evidencia sintética — 002 corte final

Capturas de la sección «Vulnerabilidades» tomadas con dos instantáneas sintéticas confirmadas
(`qualys_synthetic_valid.csv` y `qualys_synthetic_mixed.csv`) en almacenamiento temporal, sin datos
reales y con `LANGSMITH_TRACING=false`.

| Archivo | Escenario |
|---|---|
| `vulnerabilities-empty-desktop.png` | Caso sin importaciones confirmadas |
| `vulnerabilities-history-desktop.png` | Historial con dos instantáneas confirmadas |
| `vulnerabilities-filters-desktop.png` | Instantánea histórica con filtro de prioridad |
| `vulnerabilities-fixed-antecedent-desktop.png` | `Fixed` con ambos indicadores como antecedente |
| `vulnerabilities-manual-review-desktop.png` | Agregado de revisión manual con etiqueta y motivos |
| `vulnerabilities-empty-filter-desktop.png` | Importación confirmada con filtros sin coincidencias |
| `vulnerabilities-mobile-390.png` | Sección en móvil 390 |
| `vulnerabilities-mobile-320.png` | Sección en 320 px |

Comprobaciones de navegador (Playwright MCP, servidor real y fixtures):

- carga, validación, vista previa, confirmación, cancelación e historial;
- selección de la instantánea #1 y persistencia de `import_id` y filtros en la URL;
- filtros de estado, severidad y prioridad; `Fixed` antecedente y prioridad conjunta;
- ambos estados vacíos y error visible de severidad inválida;
- doble clic en «Validar archivo»: un solo `POST /imports/validate`;
- menú móvil: apertura, foco en «Cerrar menú», Escape y retorno de foco a «Abrir menú»;
- escritorio 1440, móvil 390 y 320;
- consola sin errores ni advertencias; recursos locales sin respuestas 4xx/5xx.

Las capturas son evidencia de interfaz con datos sintéticos. No sustituyen la aceptación real ni una
auditoría externa de privacidad.
