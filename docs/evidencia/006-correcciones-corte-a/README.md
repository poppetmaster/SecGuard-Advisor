# Evidencia — Correcciones funcionales del Corte A de 006

**Fecha**: 2026-11-23  
**Alcance**: generación, validación, presupuesto/contexto/privacidad y recuperación de artefactos del
informe ejecutivo. No se implementó el Corte B ni Telegram.

## 1. Problemas corregidos

### 1.1 Controles de la síntesis

- La síntesis externa ahora exige:
  - autorización vigente del caso (`ensure_external_allowed`);
  - alcance `fictional_case` (no sirve una autorización genérica ni `public_corpus` para Qualys);
  - procedencia real `synthetic_public` en la instantánea y caso sintético declarado;
  - presupuesto disponible y reserva previa (`begin_call`);
  - control de contexto del proveedor (`build_prompt_counter` + `check_prompt`);
  - permiso de concurrencia (`GenerationSlot`).
- Una instantánea Qualys privada (`private_qualys`) nunca se envía a un proveedor externo; se genera
  el informe factual local.
- La creación del proveedor está dentro del `try`; un fallo de inicialización produce fallback
  factual, libera la reserva si no hubo envío y registra evidencia.
- Se registran tokens, duración, modelo, proveedor, tarifa y costo calculado; si falta información,
  el costo queda `unknown` con motivo.
- Ollama no tiene límite monetario; conserva contexto, timeout y concurrencia.

### 1.2 Validación del contenido

- El resumen y los focos del modelo ya no se presentan como hechos: la aplicación los reemplaza por
  plantillas deterministas del dataset.
- Las recomendaciones son propuestas (`agent_proposal`). Una referencia documental válida se conserva
  como referencia, con la advertencia de que no se verificó respaldo semántico.
- Se validan resumen, focos, recomendaciones, limitaciones y `caveat`:
  - números libres;
  - IP y hosts internos;
  - nombres internos de activos y título sensible;
  - contradicciones de ausencia cuando la métrica es positiva.
- Regresión obligatoria: con `cards.critical_pending.value = 2`, «Sin vulnerabilidades críticas
  pendientes» se rechaza y cae al informe factual.
- Una cita inexistente o fuera del alcance se rechaza; no se vuelve válida cambiando su etiqueta a
  `agent_proposal`.

### 1.3 Transacciones y recuperación de artefactos

- `report_versions.status` distingue `generating`, `ready` y `failed`; solo `ready` se lista, previsualiza
  o descarga.
- La generación usa transacciones cortas: reserva/creación de versión, lectura de dataset, renderizado
  y síntesis fuera de transacción, y publicación final en otra transacción.
- Las gráficas y el PDF se preparan en un área temporal de la generación y se publican solo cuando el
  resultado completo está validado.
- Un fallo parcial limpia únicamente los archivos de esa versión; una versión `ready` anterior nunca se
  sobrescribe.
- `generation_key` es idempotente y se comprueba contra el caso; una versión `failed` con la misma clave
  se limpia y se reutiliza.
- El permiso de concurrencia evita dos generaciones simultáneas; la numeración conserva la restricción
  única y reintenta de forma acotada.

## 2. Pruebas añadidas

- `tests/unit/test_report_synthesis.py`:
  - autorización/procedencia privada y pública;
  - presupuesto agotado;
  - reserva, liquidación y registro de consumo;
  - contexto excedido;
  - fallo de inicialización del proveedor;
  - afirmación contradictoria;
  - limitaciones con IP o cifra libre;
  - cita inexistente y cita real;
  - fallback factual.
- `tests/unit/test_report_service.py`:
  - fallo del segundo artefacto y reintento sin `FileExistsError`;
  - primera versión intacta;
  - `generation_key` ligado al caso;
  - bloqueo por concurrencia.
- `tests/unit/test_reports_migration.py`:
  - `report_versions.status` y `qualys_imports.provenance` en migración temporal;
  - upgrade/downgrade.

## 3. Comandos y resultados observados

```bash
uv run pytest tests/unit/test_report_synthesis.py tests/unit/test_report_service.py tests/unit/test_reports_migration.py -q
make check
uv run pytest tests/integration/test_report_pdf.py tests/acceptance/test_report_browser.py -q
uv run pre-commit run --all-files
```

| Comprobación | Resultado |
|---|---|
| Pruebas focalizadas de síntesis/servicio/migración | **21 passed** |
| `make check` | **786 passed, 40 deselected** |
| PDF real + navegador | **2 passed** |
| Migración temporal | upgrade/downgrade OK |
| `pre-commit run --all-files` | Todos los hooks en verde |

## 4. Evidencia visual

- `docs/evidencia/006-correcciones-corte-a/pdf-muestra.pdf` (3 páginas)
- `docs/evidencia/006-correcciones-corte-a/pdf-pages/page-1.png`, `page-2.png`, `page-3.png`
- `docs/evidencia/006-correcciones-corte-a/browser-desktop.png`
- `docs/evidencia/006-correcciones-corte-a/browser-mobile.png`
- `docs/evidencia/006-correcciones-corte-a/browser-mobile-nav.png`

## 5. Límites

- Los proveedores externos se probaron con dobles; no hubo claves reales, llamadas pagadas ni envíos.
- La autorización externa sobre Qualys queda bloqueada salvo procedencia `synthetic_public` explícita.
- La validación de citas comprueba existencia/alcance; no demuestra respaldo semántico.
- No se implementaron T035–T081 ni Telegram.
