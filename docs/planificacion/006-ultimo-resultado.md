# 006 — Último resultado

**Fecha**: 2026-11-23  
**Estado**: Corte A implementado y validado localmente. T001–T034 completadas; T035–T081 pendientes.
Sin contactos, envíos, reglas automáticas ni Telegram. Sin llamadas pagadas ni mensajes reales.

## 1. Implementación del Corte A

Se implementó el informe ejecutivo dentro del caso:

- sección **Informe ejecutivo** con historial de versiones;
- selección explícita de una instantánea Qualys confirmada y filtros opcionales;
- dataset canónico inmutable por versión, calculado en SQLite y persistido en
  `report_versions.dataset_json`;
- tarjetas de pendientes, críticas, altas, activos, explotabilidad, malware, ambos indicadores,
  Fixed y revisión manual;
- cuatro gráficas ECharts con títulos-conclusión y tablas alternativas;
- PDF local de 3 páginas con composición de impresión, gráficas SVG y detalle técnico;
- historial y descarga del PDF persistido;
- síntesis opcional `report-synthesis-v1` con `claim_refs`, propuestas identificadas y fallback
  factual.

## 2. Tareas

**Completadas**: T001–T034 (Setup, Foundational y Corte A).

**Pendientes**: T035–T081 (contactos, envío manual, reglas automáticas, recuperación y aceptación
integrada). No se inició T035.

Las migraciones del Corte A son `d8e9f0a1b2c3` (tablas de informe y `runs`) y `e2f3a4b5c6d7`
(`report_versions.status` y `qualys_imports.provenance`). `generation_key` queda preparado para C.

## 3. Verificación observada

| Comprobación | Resultado |
|---|---|
| `uv sync --locked` | Entorno reproducible; `playwright` 1.65.2 |
| `uv run python scripts/check_pdf_runtime.py` | `PDF runtime OK (chrome, 9130 bytes)` |
| `node scripts/render_report_charts.mjs --check` | `ECharts SSR OK (2790 bytes)` |
| `make assets` | Tailwind y recursos recompilados |
| `make check` | **786 passed, 40 deselected** |
| PDF real + navegador | **2 passed** (`test_report_pdf.py`, `test_report_browser.py`) |
| `pre-commit run --all-files` | Todos los hooks en verde |
| Correcciones focalizadas de síntesis/servicio/migración | **21 passed** |

La prueba de PDF usa pypdf para páginas, texto y estructura. La inspección visual se hizo sobre las
páginas renderizadas como imágenes; no se atribuye a pypdf.

## 4. Evidencia

- `docs/evidencia/006-corte-a/README.md`
- `docs/evidencia/006-corte-a/pdf-muestra.pdf` (3 páginas)
- `docs/evidencia/006-corte-a/pdf-pages/page-1.png`, `page-2.png`, `page-3.png`
- `docs/evidencia/006-corte-a/browser-desktop.png`
- `docs/evidencia/006-corte-a/browser-mobile.png`
- `docs/evidencia/006-corte-a/browser-mobile-nav.png`
- `docs/evidencia/006-correcciones-corte-a/README.md` y artefactos de la revisión

## 5. Hallazgos del análisis

Los 21 hallazgos documentales del análisis quedaron resueltos antes de implementar: generación
recuperable (`generation_key`), revalidación por componente, dependencias/paralelismo, propiedad de
pruebas, contrato de síntesis, separación pypdf/inspección visual y defaults de top 5/título. El
detalle está en `docs/planificacion/006-analisis.md`.

## 6. Defectos actuales y verificaciones no ejecutadas

**Defectos abiertos del Corte A**: ninguno observado tras las correcciones de la revisión.

Se corrigieron tres defectos reportados: controles de síntesis, validación de afirmaciones/contenido y
transacciones/recuperación de artefactos. La evidencia y las pruebas están en
`docs/evidencia/006-correcciones-corte-a/`.

**Verificaciones futuras no ejecutadas**:

- envío real de Telegram;
- contactos, consentimiento y reglas automáticas (Cortes B/C);
- llamadas pagadas y presupuesto;
- evaluación semántica humana;
- rendimiento formal de informe/PDF;
- navegadores distintos de Chrome local.

No son defectos del Corte A ni aprobaciones.

## 7. Límites

- No se implementaron contactos, envíos, reglas automáticas ni Telegram; no se declara Telegram
  implementado.
- La síntesis se probó con dobles y fallback; no se consumieron créditos externos.
- El PDF se genera con Chrome local y ECharts SSR con Node; no hay CDN.
- El título sensible se excluye del PDF por defecto (`include_case_title=false`); la vista web local
  conserva el contexto del caso.
- El top 5 de activos es el valor predeterminado y declara el recorte.

## 8. Siguiente paso

Revisar la evidencia y decidir si se autoriza el Corte B (T035–T056). No ejecutar `/speckit.implement`.
