# Evidencia sintética — 002 US1

Capturas tomadas con el CSV sintético `qualys_synthetic_valid.csv` y el fixture de encabezado
inválido, sobre un almacenamiento temporal fuera del repositorio y con `LANGSMITH_TRACING=false`.
No contienen filas, IP, activos ni resultados reales.

| Archivo | Escenario |
|---|---|
| `vulnerabilities-empty-desktop.png` | Sección sin importaciones confirmadas |
| `vulnerabilities-form-desktop.png` | Formulario con solo el campo CSV |
| `vulnerabilities-form-mobile-390.png` | Formulario en móvil |
| `vulnerabilities-preview-desktop.png` | Vista previa `staged` |
| `vulnerabilities-preview-mobile-390.png` | Preview en móvil |
| `vulnerabilities-preview-mobile-320.png` | Preview en 320 px |
| `vulnerabilities-confirmed-desktop.png` | Snapshot confirmado y tabla |
| `vulnerabilities-confirmed-mobile-390.png` | Snapshot confirmado en móvil |
| `vulnerabilities-confirmed-mobile-320.png` | Snapshot confirmado en 320 px |
| `vulnerabilities-rejected-desktop.png` | Archivo rechazado con motivos |
| `vulnerabilities-rejected-mobile-320.png` | Rechazo en móvil |
| `vulnerabilities-mobile-menu-320.png` | Menú móvil con foco y cierre por Escape |

Comprobaciones Playwright: foco inicial en «Cerrar menú», `aria-expanded`, cierre con Escape y
restauración del foco; sin desbordamiento horizontal a 320/390 px; consola sin errores; formulario
con guarda de doble envío.
