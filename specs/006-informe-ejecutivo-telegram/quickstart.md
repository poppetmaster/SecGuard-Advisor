# Quickstart — Validación de 006

**Estado**: guía de validación planificada. No se ejecutó en este paso; no hay implementación, tareas,
dependencias instaladas, llamadas pagadas ni envíos.

## Prerrequisitos

- Python 3.14.6 y `uv`; Node ≥26.11.1 con `npm ci` ejecutado (ECharts 5.6.0 local).
- Esquema migrado: `uv run alembic upgrade head`.
- Almacenamiento separado para pruebas: `SECGUARD_ACCEPTANCE_DIR` o `tmp_path`.
- `TELEGRAM_BOT_TOKEN` ficticio y `SECGUARD_TELEGRAM_TRANSPORT=stub` para todas las pruebas.
- `LANGSMITH_TRACING=false`.
- Playwright instalado en el entorno de implementación y Chrome disponible, o Chromium empaquetado.
- Node participa en el renderizado local de las gráficas del PDF mediante ECharts SSR; no es solo un
  requisito de build de Tailwind.
- El gate de Playwright/Chrome se ejecuta **antes** de implementar el renderizado del PDF.

## Comandos base

```bash
make install                 # uv sync --locked, hooks, npm ci
uv run alembic upgrade head  # tablas nuevas
make check                   # lint + formato + pruebas
uv run pytest tests/unit -q
uv run pytest tests/contract -q
uv run pytest tests/integration -q
uv run pytest tests/acceptance -q
```

No se ejecuta `make dev` contra `storage/` real durante la aceptación; se usa un directorio temporal.

## Escenario A — Informe ejecutivo web y PDF

### A0. Gate de renderizado

```bash
uv run python scripts/check_pdf_runtime.py
node scripts/render_report_charts.mjs --check
```

**Esperado**: el navegador lanza y Node puede renderizar un SVG de prueba. Si falla, el Corte A se
detiene y se reevalúa el motor; no se implementa un PDF degradado.

### A1. Datos y snapshot

1. Crear un caso ficticio y confirmar una importación Qualys de prueba con severidades 1–5, estados
   `pending_known`, `fixed` y `manual_review`, indicadores positivos/negativos/indeterminados y al
   menos dos activos sin identificación.
2. Generar el informe desde el snapshot confirmado.

**Esperado**: `report_version` con `dataset_sha256`, tarjetas y cuatro gráficas; top 5 de activos por
  defecto con recorte declarado; cero envíos.

### A2. Concordancia SQLite → tarjetas → gráficas → PDF

```bash
uv run pytest tests/contract/test_report_concordance.py -q
```

**Esperado**:

- cada valor de tarjeta coincide con la consulta SQL y con el texto del HTML y del PDF;
- los denominadores declarados coinciden;
- ningún conteo se multiplica por CVE (caso con varias filas CVE por vulnerabilidad);
- `manual_review` aparece una vez y no se suma a las distribuciones;
- `exploitability` y `malware` no se suman;
- la tabla alternativa repite los valores de la gráfica.

### A3. PDF: comprobaciones automáticas e inspección visual

```bash
uv run pytest tests/integration/test_report_pdf.py -q
```

**Comprobaciones automáticas con pypdf**:

- 2–3 páginas A4;
- extracción de texto por página sin páginas vacías;
- presencia de objetos embebidos de las gráficas;
- identificador de versión, snapshot y títulos extraíbles;
- sin enlaces a localhost.

pypdf **no** detecta recortes, espacios, solapamientos ni legibilidad visual. Esas comprobaciones se
realizan en la inspección visual.

**Inspección visual del PDF**: abrir las páginas renderizadas como imágenes con el visor local o la
herramienta disponible; comprobar gráficas completas, sin cortes, espacios, solapamientos, páginas
vacías o texto ilegible; revisar jerarquía, contraste, iconos, etiquetas y unidades. Registrar
capturas/notas en `docs/evidencia/006-corte-a/`. No exige firma ni aprobación humana adicional.

**Revisión de la web**: abrir
`/cases/{case_id}/reports/{report_id}/versions/{version}/preview`; comprobar tooltips, tablas
alternativas y navegación en escritorio y móvil.

### A4. Inmutabilidad e historial

1. Importar y confirmar otro CSV del mismo caso.
2. Abrir el informe anterior y descargar su PDF.

**Esperado**: mismas cifras, mismo `dataset_sha256` y mismo PDF; regenerar crea otra versión.

### A5. Factual y síntesis separadas

Forzar `synthesis_status=failed` (proveedor no disponible o respuesta inválida) y revisar un informe
con síntesis completada.

**Esperado**: el informe factual conserva cifras, gráficas y limitaciones, con rótulo «Sin síntesis de
IA» y sin texto inventado. En el informe sintetizado se distinguen hechos calculados,
`agent_proposal` y respaldo documental; ninguna recomendación inventa números. No hay llamada externa
si no hay presupuesto.

### A6. Privacidad y aislamiento

**Esperado**:

- PDF y mensaje sin IP, nombres internos, Results, filas crudas, CVEs detallados ni título del caso
  sensible (`include_case_title=false`);
- alias `Activo 01..N` y «Otros» con recorte declarado;
- un informe de otro caso no es accesible por URL ni por consulta;
- `chat_id` completo y token no aparecen en logs ni evidencia.

## Escenario B — Contactos y envío manual

### B1. Verificación independiente del informe

1. Registrar contacto con `chat_id` ficticio y estado `unverified`.
2. Con el envío de informes bloqueado, solicitar el código de verificación desde la interfaz.
3. Confirmar el código correcto; repetir con código inválido, expirado, consumido y con demasiados
   intentos.
4. Revisar `contact_verification_challenges`.

**Esperado**: el código se envía aunque el informe esté bloqueado; no se exige consentimiento ni
vínculo para solicitar el código; el desafío guarda solo `code_sha256`, expiración, intentos, consumo,
contacto y `bot_fingerprint`; nunca el código en claro ni el token; máximo 3 solicitudes por ventana y
3 intentos; sin código correcto no hay `verified`; la evidencia registra método, fecha e identidad; el
consentimiento es un paso separado. No se envía ningún mensaje real: todo pasa por el doble.

### B2. Bloqueos de informe

**Esperado**: no se envía un **informe** a contacto no verificado, sin consentimiento, inactivo,
revocado o no vinculado al caso. Cero llamadas de informe al transporte. El envío del código sigue
permitido.

### B3. Confirmación individual

1. Preparar envío, revisar contenido y destinatarios.
2. Editar el informe o cambiar destinatarios antes de confirmar.
3. Confirmar y enviar.

**Esperado**: la confirmación anterior se invalida tras la edición; se construye y guarda
`report-manifest-v1`; el envío solo usa el contenido, PDF, política y destinatarios aprobados; si el
manifiesto recalculado no coincide, la ejecución devuelve `manifest_mismatch` y no llama a Telegram;
se registra el estado por destinatario.

### B4. Doble clic y recarga

**Esperado**: un solo evento por versión y destinatario; el segundo intento devuelve el evento
existente; no se reenvía un componente aceptado; resumen y PDF tienen estados independientes.

### B5. Resultado parcial

Simular aceptación del resumen y fallo del PDF.

**Esperado**: evento `partial`; reintento solo del PDF; el resumen no se reenvía. Si se revoca el
consentimiento entre el resumen y el PDF, el resumen aceptado se conserva y el PDF queda `skipped`.
Un timeout produce `uncertain` y no se reintenta automáticamente; el reinicio conserva el estado.

## Escenario C — Regla automática y recuperación

### C1. Regla desactivada por defecto

**Esperado**: una regla nueva está `draft`; confirmar una importación no genera informe ni envío.

### C2. Activación y disparo

1. Activar una regla con destinatarios verificados, condiciones y `synthesis_policy=factual_only`.
2. Confirmar una importación que coincide.

**Esperado**: se encola la evaluación en la misma transacción de confirmación; se genera el informe
factual; se crea un evento por destinatario identificado como automático; el gasto de IA es cero; la
evaluación guarda `report_version_id`.

### C3. No disparo

**Esperado**: cero envíos desde staging, rechazo, cancelación, vista previa, regla desactivada,
regla modificada sin reactivación, importación no coincidente o destinatario no verificado.

### C4. Cruce manual/automático

1. Enviar manualmente una versión a un contacto.
2. Evaluar una regla que incluye al mismo contacto.

**Esperado**: se reutiliza el evento; no se duplica el envío; el cruce queda en evidencia. Si la regla
se evalúa tras un reinicio, reutiliza la misma `report_version_id` y no crea otra versión.

### C5. Reinicio y timeout incierto

1. Simular solicitud enviada y reinicio antes de la respuesta.
2. Reiniciar la aplicación.

**Esperado**: el componente queda `uncertain`/`interrupted`; no hay reintento automático; la UI pide
revisión; la importación confirmada sigue intacta; la evaluación conserva `generation_key` y la
versión; una interrupción antes de guardar `report_version_id` recupera la versión por la clave y no
crea otra; una interrupción después reutiliza versión y eventos.

### C6. Aceptación integrada con dobles

```bash
uv run pytest tests/acceptance/test_report_notifications_journey.py -q
```

**Esperado**: recorrido A → B → C completo con datos ficticios, navegación en escritorio y móvil,
sin red externa. Regresión de 001–005: `make check` y las integraciones afectadas siguen en verde.

## Matriz de criterios

| Criterio | Escenario |
|---|---|
| SC-001 concordancia web/PDF | A2 |
| SC-002 PDF legible 2–3 páginas | A3 |
| SC-003 cero desde staging/rechazo/vista previa | C3 |
| SC-004 bloqueo de destinatario no verificado | B2 |
| SC-005 sin duplicados ni cruce de modos | B4, C4 |
| SC-006 evidencia de envío automático | C2 |
| SC-007 snapshot histórico inmutable | A4 |
| SC-008 privacidad del contenido | A6 |
| SC-009 fallback factual | A5 |
| SC-010 recorrido manual < 3 minutos | B3 + revisión cronometrada |
| SC-011 manifiesto aprobado y sin envíos con discrepancia | B3 |
| SC-012 verificación sin bloqueo de informe y sin código en claro | B1 |

## Datos y límites de la validación

- Datos ficticios; no se usa el CSV privado ni Qualys real.
- No se envía ningún mensaje real. El envío real de prueba requiere autorización posterior con
  destino y contenido concretos.
- No se ejecutan llamadas pagadas; la síntesis se prueba con dobles o proveedor local.
- `storage/`, `storage/demo`, Chroma y Qdrant no se modifican.
