# Evidencia — 006 Corte A: informe ejecutivo web y PDF

**Fecha**: 2026-11-23  
**Alcance**: T001–T034 (Setup, Foundational y Corte A). No incluye contactos, envíos, reglas
automáticas ni Telegram.

## 1. Qué se implementó

- Sección **Informe ejecutivo** dentro del caso, con historial de versiones.
- Selección explícita de una instantánea Qualys confirmada y filtros opcionales.
- Dataset canónico inmutable por versión, calculado en SQLite y persistido en
  `report_versions.dataset_json`.
- Tarjetas de pendientes, críticas, altas, activos, explotabilidad, malware, ambos indicadores,
  Fixed y revisión manual.
- Cuatro gráficas ECharts con títulos-conclusión y tablas alternativas.
- PDF local de 3 páginas con composición de impresión, gráficas SVG y tablas de soporte.
- Historial y descarga del PDF persistido.
- Síntesis opcional `report-synthesis-v1` con `claim_refs`, propuestas identificadas y fallback
  factual. No se usó ningún proveedor externo real.

## 2. Comandos ejecutados y resultados

```bash
uv sync --locked
uv run python scripts/check_pdf_runtime.py
node scripts/render_report_charts.mjs --check
make assets
make check
uv run pytest tests/integration/test_report_pdf.py tests/acceptance/test_report_browser.py -q
uv run pre-commit run --all-files
```

| Comando | Resultado observado |
|---|---|
| `uv sync --locked` | Entorno reproducible; `playwright` 1.65.2 instalado como dependencia Python |
| `scripts/check_pdf_runtime.py` | `PDF runtime OK (chrome, 9130 bytes)` |
| `render_report_charts.mjs --check` | `ECharts SSR OK (2790 bytes)` |
| `make assets` | Tailwind y recursos vendorizados recompilados |
| `make check` | **786 passed, 40 deselected** |
| PDF + navegador (integración) | **2 passed**; PDF real de 3 páginas y recorrido de escritorio/móvil |
| `pre-commit run --all-files` | Todos los hooks en verde |

La prueba de PDF usa pypdf solo para páginas, texto extraíble y estructura. La inspección visual se
realizó por separado sobre las páginas renderizadas como imágenes.

## 3. Artefactos

- `pdf-muestra.pdf`: PDF ejecutivo de muestra con datos ficticios (3 páginas).
- `pdf-pages/page-1.png`, `page-2.png`, `page-3.png`: páginas renderizadas para inspección visual.
- `browser-desktop.png`: vista de escritorio.
- `browser-mobile.png`: vista móvil con contenido.
- `browser-mobile-nav.png`: menú móvil desplegado.

La inspección visual comprobó:

- páginas 1–3 sin recortes ni solapamientos;
- tarjetas y gráficas completas;
- tablas de activos y detalle técnico legibles;
- sin páginas vacías;
- títulos y conclusiones consistentes con el dataset;
- PDF comprensible sin abrir la aplicación.

## 4. Pruebas

- `tests/unit/test_canonical_json.py`
- `tests/unit/test_error_codes.py`
- `tests/unit/test_report_privacy.py`
- `tests/unit/test_report_aliasing.py`
- `tests/unit/test_report_metrics.py`
- `tests/unit/test_report_dataset.py`
- `tests/unit/test_report_charts.py`
- `tests/unit/test_report_artifacts.py`
- `tests/unit/test_report_service.py`
- `tests/unit/test_report_synthesis.py`
- `tests/unit/test_reports_migration.py`
- `tests/contract/test_report_routes.py`
- `tests/contract/test_report_isolation.py`
- `tests/contract/test_report_concordance.py`
- `tests/integration/test_report_pdf.py`
- `tests/acceptance/test_report_browser.py`
- `tests/acceptance/test_report_journey.py`

## 5. Cómo probarlo localmente

1. Confirmá una importación Qualys en un caso. Podés usar el CSV ficticio
   `tests/fixtures/files/qualys_synthetic_valid.csv` desde **Vulnerabilidades**.
2. Abrí **Informe ejecutivo** en la barra lateral del caso.
3. Elegí **Generar informe**, seleccioná la instantánea confirmada y generá la versión.
4. Revisá tarjetas, gráficas y tablas; usá **Descargar PDF** y **Vista de impresión**.
5. Regenerá para comprobar que se crea otra versión y que el historial conserva la anterior.

Comandos de arranque:

```bash
uv run alembic upgrade head
make dev
# o, para una instancia de demostración separada:
make demo-prepare
make demo
```

No se modifica `storage/` ni `storage/demo` durante las pruebas automatizadas; usan `tmp_path`.

## 6. Límites

- No se implementaron contactos, envíos, reglas automáticas ni Telegram; no se declara Telegram
  implementado.
- No hubo llamadas pagadas ni envíos reales.
- La síntesis se probó con dobles y con el fallback factual; no se consumieron créditos externos.
- La recuperación automática con `generation_key` queda preparada en el esquema, pero su flujo
  completo pertenece al Corte C.
- La aceptación visual se registró con capturas y revisión de páginas; no sustituye una revisión
  semántica humana.
