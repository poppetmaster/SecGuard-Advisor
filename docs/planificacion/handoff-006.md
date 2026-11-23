# Handoff — 006 Informe ejecutivo y notificaciones Telegram

**Fecha**: 2026-11-23  
**Estado**: Corte A implementado y validado localmente. T001–T034 completadas; T035–T081 pendientes.
Sin contactos, envíos, reglas automáticas ni Telegram. Sin llamadas pagadas ni mensajes reales.  
**Rama**: `006-informe-ejecutivo-telegram`.  
**Constitución**: 1.4.0.

## 1. Artefactos implementados

| Archivo / módulo | Contenido |
|---|---|
| `src/secguard_advisor/reports/` | `canonical`, `dataset`, `metrics`, `aliasing`, `charts`, `privacy`, `errors`, `artifacts`, `render`, `synthesis`, `service` |
| `src/secguard_advisor/web/routes/reports.py` | Rutas de historial, formulario, generación, vista, PDF y preview |
| `src/secguard_advisor/web/templates/reports/` | `index`, `new`, `view`, `print`, `_cards`, `_charts`, `_history` |
| `src/secguard_advisor/web/static/js/report-charts.js` | Gráficas ECharts interactivas y tablas alternativas |
| `alembic/versions/d8e9f0a1b2c3_add_reports_and_report_runs.py` | Tablas de informe y extensión de `runs` |
| `alembic/versions/e2f3a4b5c6d7_add_report_status_and_qualys_provenance.py` | Estado de versión y procedencia Qualys |
| `scripts/render_report_charts.mjs` | ECharts SSR a SVG para PDF |
| `scripts/check_pdf_runtime.py` | Gate de Playwright/Chrome |
| `tests/.../test_report_*` | Métricas, dataset, servicio, artefactos, síntesis, rutas, concordancia, PDF, navegador y recorrido |

## 2. Funcionalidad disponible

- Sección **Informe ejecutivo** en la navegación del caso.
- Selección de una instantánea Qualys **confirmada** y filtros opcionales.
- Dataset canónico inmutable por versión; la web y el PDF consumen el mismo dataset.
- Tarjetas: pendientes, críticas, altas, activos, explotabilidad, malware, ambos indicadores, Fixed y
  revisión manual.
- Cuatro gráficas ECharts con conclusión, unidad, denominador y tabla alternativa.
- PDF local de 3 páginas con composición propia, gráficas SVG y detalle técnico.
- Historial de versiones y descarga del PDF persistido.
- Síntesis opcional `report-synthesis-v1`; fallback factual si falla o no está autorizada.

## 3. Tareas

- **Completadas**: T001–T034.
- **Pendientes**: T035–T081.
- No se inició T035. Telegram, contactos, envío manual y reglas automáticas siguen sin implementar.

## 4. Verificación observada

| Comprobación | Resultado |
|---|---|
| `make check` | **786 passed, 40 deselected** |
| PDF real + navegador | **2 passed** |
| `scripts/check_pdf_runtime.py` | PDF runtime OK con Chrome local |
| `render_report_charts.mjs --check` | ECharts SSR OK |
| `make assets` | Recursos recompilados |
| `pre-commit run --all-files` | Todos los hooks en verde |
| Correcciones focalizadas | **21 passed** |

La inspección visual del PDF se realizó sobre páginas renderizadas como imágenes. pypdf solo se usó
para páginas, texto y estructura.

## 5. Evidencia

- `docs/evidencia/006-corte-a/README.md`
- `docs/evidencia/006-corte-a/pdf-muestra.pdf` (3 páginas)
- `docs/evidencia/006-corte-a/pdf-pages/page-1.png`, `page-2.png`, `page-3.png`
- `docs/evidencia/006-corte-a/browser-desktop.png`
- `docs/evidencia/006-corte-a/browser-mobile.png`
- `docs/evidencia/006-corte-a/browser-mobile-nav.png`
- `docs/evidencia/006-correcciones-corte-a/README.md` y artefactos de la revisión

## 6. Cómo probarlo

1. `uv run alembic upgrade head`.
2. `make dev`.
3. Crear un caso y confirmar una importación Qualys; podés usar
   `tests/fixtures/files/qualys_synthetic_valid.csv` desde **Vulnerabilidades**.
4. Abrir **Informe ejecutivo** → **Generar informe** → elegir instantánea → generar.
5. Revisar tarjetas, gráficas, tablas y descargar el PDF.
6. Regenerar para comprobar que se crea otra versión y el historial conserva la anterior.

## 6.1 Correcciones de la revisión

- La síntesis externa exige autorización por alcance, procedencia `synthetic_public`, presupuesto con
  reserva/liquidación, contexto y concurrencia; Qualys privado no sale.
- Resumen y focos son deterministas; la prosa del modelo es propuesta. Se rechazan contradicciones,
  cifras libres, IP/nombres internos y citas inexistentes.
- La generación usa `report_versions.status`, transacciones cortas, área temporal y publicación solo de
  versiones `ready`; un fallo limpia únicamente su versión y el reintento reutiliza `generation_key`.
- Evidencia: `docs/evidencia/006-correcciones-corte-a/`.

## 7. Decisiones técnicas vigentes

- Dataset único persistido por versión; web y PDF no recalculan.
- Métricas en SQLite; sin multiplicación por CVE ni suma de categorías solapadas.
- `Fixed` separado; severidad 1–5 sin P1–P4.
- Top 5 por defecto y título sensible excluido del PDF (`include_case_title=false`).
- PDF con Playwright/Chrome y ECharts SSR con Node; sin CDN.
- Síntesis opcional con `claim_refs`; las citas no se presentan como respaldo semántico automático.
- `generation_key` preparado para recuperación automática del Corte C.

## 8. Límites y pendientes reales

- No se implementaron T035–T081: contactos, envío manual, reglas, Telegram ni recuperación automática.
- No hubo llamadas pagadas, envíos reales ni evaluación externa.
- La aceptación visual es local (Chrome); no cubre otros navegadores.
- La evaluación semántica humana y el rendimiento formal siguen pendientes.
- 005 conserva sus limitaciones documentadas.

## 9. Siguiente paso

Revisar la evidencia del Corte A y decidir si se autoriza T035. No ejecutar `/speckit.implement`.
