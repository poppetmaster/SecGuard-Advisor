# Evidencia sintética — 002 US2

Capturas tomadas con dos instantáneas sintéticas confirmadas (`qualys_synthetic_valid.csv` y
`qualys_synthetic_second.csv`) en almacenamiento temporal, sin datos reales y con
`LANGSMITH_TRACING=false`.

| Archivo | Escenario |
|---|---|
| `vulnerabilities-selector-desktop.png` | Selector con la última instantánea predeterminada |
| `vulnerabilities-selector-historical-desktop.png` | Instantánea anterior seleccionada, etiqueta «Histórica» |
| `vulnerabilities-selector-mobile-390.png` | Selector histórico en móvil 390 |
| `vulnerabilities-selector-mobile-320.png` | Selector histórico en 320 px |
| `vulnerabilities-history-desktop.png` | Historial con estado, fecha, filas y secuencia |
| `vulnerabilities-history-mobile-320.png` | Historial en móvil 320 |

Comprobaciones: la última confirmada es la predeterminada; la selección persiste por `import_id` al
recargar; los conteos cambian entre instantáneas sin sumarse; no hay desbordamiento horizontal a
320/390 px; la consola no registra errores y los recursos locales responden 200. El menú muestra
únicamente «Vulnerabilidades».
