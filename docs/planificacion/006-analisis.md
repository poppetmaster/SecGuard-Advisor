# Análisis de consistencia — 006 Informe ejecutivo y notificaciones Telegram

**Fecha**: 2026-11-23
**Alcance**: `specs/006-informe-ejecutivo-telegram/` contrastado con la constitución 1.4.0,
`AGENTS.md`, `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`,
`tasks.md` y los documentos de seguimiento.
**Modo**: solo lectura sobre los artefactos analizados. No se implementó código, no se instalaron
dependencias, no se ejecutaron migraciones, no hubo llamadas pagadas ni envíos.

**Nota de estado del árbol**: el repositorio ya contenía cambios no comprometidos de los pasos
anteriores (constitución, especificación, plan, diseño y tareas). Esta revisión no modificó esos
artefactos; solo creó este informe y actualizó los dos documentos de seguimiento autorizados.

## 1. Resumen ejecutivo

La funcionalidad está bien delimitada y conserva las decisiones autorizadas: informe desde snapshot
confirmado, verificación separada del envío de informes, manifiesto aprobado, idempotencia por
informe/versión/destinatario y separación de cortes. No se encontró una violación directa de la
constitución 1.4.0; DEL-01 es un riesgo crítico de violación del principio XIV, FR-033 y FR-047 si no se
corrige.

Sin embargo, hay **1 defecto crítico de diseño** y varios defectos altos que afectan la ejecución o la
verificación:

- Una interrupción entre crear la versión del informe y vincularla a la evaluación automática puede
  permitir una segunda versión o un segundo envío. No hay clave de generación ni transacción/recuperación
  definida para ese intervalo.
- Las listas de paralelismo de `tasks.md` contradicen dependencias reales (T013→T014→T015→T016,
  T036→T037, T033 depende de T027–T032).
- La regla de síntesis «prohíbe dígitos» es demasiado amplia y la etiqueta `documentary` no exige
  cita verificada.
- La verificación del PDF mezcla comprobaciones automáticas de pypdf con inspección visual; no hay una
  tarea explícita de inspección visual del PDF.
- Hay archivos de prueba citados como evidencia sin una tarea que los cree, y tareas de implementación
  que parecen duplicar la escritura de tests asignada a otra tarea.

**Dictamen**: **no iniciar el Corte A todavía**. Corregir primero los defectos críticos/altos de
planificación; después el Corte A puede comenzar. Los defectos de B/C pueden corregirse antes de sus
respectivos cortes, salvo la clave de generación de `report_versions`, que pertenece al esquema de A.

## 2. Hallazgos

| ID | Severidad | Ubicación | Hallazgo y consecuencia | Corrección propuesta |
|---|---|---|---|---|
| DEP-01 | **HIGH** | `tasks.md:538-544`, `tasks.md:555-566` | «Corte A: T013/T014/T015/T016 tras T012» los declara paralelos, pero T014 depende de T013, T015 de T014 y T016 de T014+T015. Ejecutarlos en paralelo produce dataset/métricas/alias incompletos y contradice las etiquetas `[P]`. | Secuenciar T013 → T014 → T015 → T016. Solo T013 puede ejecutarse en paralelo con T021 tras T012. Retirar `[P]` de T014, T015 y T016. |
| DEP-02 | **HIGH** | `tasks.md:540-541`, `tasks.md:43`, `tasks.md:63` | «Setup: T001–T006» y «Foundational: T007–T011» se presentan como paralelos, pero T002–T005 dependen de T001, T006 de T002, T011 de T008 y T009/T010 de T004. Las etiquetas `[P]` de T006 y de la cadena T007–T011 son engañosas **en la lista propuesta**. | Batches: T001; luego T002–T005 en paralelo; luego T006. Foundational: T007/T009/T010 tras T004; T008 tras T005; T011 tras T008. Quitar `[P]` donde la dependencia está en el mismo batch. |
| DEP-03 | **HIGH** | `tasks.md:543`, `tasks.md:570-585` | «Tras T035: T036/T037/T038/T039» incluye T037, que depende de T036. Lanzarlos juntos puede crear el desafío antes de que exista el contacto. | Tras T035: T036/T038/T039 en paralelo; T037 después de T036. |
| DEP-04 | **HIGH** | `tasks.md:543`, `tasks.md:579-585` | «T049–T054 en paralelo tras T045» no respeta dependencias: T049 necesita T037/T044, T050 T039/T042, T051 T040/T043, T052 T041, T053 T038/T043/T045 y T054 T045/T047. T047 puede no estar listo. | Reemplazar por batches por dependencia; T054 solo tras T047. Documentar el orden mínimo. |
| DEP-05 | **MEDIUM** | `tasks.md:226`, `tasks.md:542` | T033 está marcada `[P]` y depende de T027–T032; además aparece en «T027–T033 en paralelo». No puede ejecutarse con las pruebas que la alimentan. | Quitar `[P]` de T033 y colocarla después de T027–T032. |
| DEP-06 | **LOW** | `tasks.md:533-534`, `tasks.md:544` | La ruta crítica omite T015 y la notación `T013/T014/T016` sugiere paralelismo donde hay cadena. «T066–T071 tras T064» es seguro pero no mínimo: T067–T070 no dependen de T064. | Escribir la cadena completa T013→T014→T015→T016 y separar los batches reales de C. |
| TST-01 | **HIGH** | `tasks.md:118-134`, `tasks.md:279-298`, `tasks.md:386-410` | Varias tareas de implementación citan como evidencia el mismo archivo que una tarea de prueba posterior: T013→T028, T014→T027, T022→T028, T009→T032, T039/T042→T050, T040→T051, T041→T052, T043→T051, T058→T066, T059/T060→T067, T061→T068, T062→T069, T063→T070, T045→T053/T054. No queda claro si la implementación debe escribir el test o solo ejecutarlo; hay riesgo de doble trabajo y conflicto. | Declarar que las tareas de implementación no escriben tests; su evidencia debe remitir a la tarea de prueba que los crea. Una sola tarea es dueña de cada archivo de test. |
| TST-02 | **HIGH** | `tasks.md:71-168`, `tasks.md:250-298`, `tasks.md:380-410` | Archivos de prueba citados como evidencia sin tarea que los cree: `test_canonical_json.py`, `test_report_aliasing.py`, `test_report_charts.py`, `test_report_artifacts.py`, `test_report_synthesis.py`, `test_report_routes.py`, `test_reports_migration.py`, `test_notifications_manual_migration.py`, `test_notification_rules_migration.py`, `test_telegram_transport.py`, `test_delivery_states.py`. Varios cubren comportamientos centrales. | Añadir tareas de prueba explícitas o ampliar una tarea existente; cada archivo debe tener un único dueño. |
| TST-03 | **MEDIUM** | `tasks.md:164`, `tasks.md:371-375` | SC-009 (fallback factual) y la validación de síntesis no tienen una tarea de prueba dedicada; T021 cita `test_report_synthesis.py`, pero ninguna tarea lo crea. | Asignar T021 a una tarea de prueba de síntesis que cubra respuesta válida, inválida, sin presupuesto, proveedor no autorizado y fallback factual. |
| SYN-01 | **HIGH** | `research.md:85`, `tasks.md:164` | «Prohíbe dígitos en texto generado» impide identificadores válidos (QID, CVE, versión, secuencia) y no garantiza por sí solo que no se inventen cifras. Puede rechazar síntesis correctas o forzar a eliminar referencias útiles. | Sustituir por validación de afirmaciones numéricas: permitir identificadores con patrón/allowlist; rechazar números que no correspondan a una métrica del dataset o a un identificador autorizado. Las cifras se renderizan desde el dataset. |
| SYN-02 | **HIGH** | `research.md:83-87`, `tasks.md:164`, `data-model.md:41` | `basis='documentary'` no exige cita verificada; `evidence_refs` no se valida contra fragmentos/citas. Una etiqueta «documentary» no es evidencia por sí sola y podría presentarse una recomendación sin respaldo. | Exigir `evidence_refs` con `document_chunk_id`/cita y validar con el validador de citas existente; si la cita no existe o no respalda la afirmación, degradar a `agent_proposal` o rechazar. Guardar el resultado de la validación. |
| SYN-03 | **MEDIUM** | `data-model.md:23-47`, `contracts/` | El esquema `report-synthesis-v1` solo aparece en `research.md` y `tasks.md`; no hay contrato canónico en `data-model.md` ni en `contracts/`. Implementaciones distintas pueden validar de forma diferente. | Añadir el esquema y las reglas de validación numérica/referencial a `data-model.md` o a un contrato; incluir el fallback factual y la evidencia. |
| STA-01 | **MEDIUM** | `plan.md:273-277`, `docs/planificacion/006-ultimo-resultado.md:100-101`, `docs/planificacion/handoff-006.md:108-109` | El top 5 se define como valor predeterminado en `plan.md:56`, `plan.md:160` y en el contrato, pero también aparece como decisión pendiente bloqueante. | Tratarlo como valor predeterminado ya establecido. La revisión de producto es opcional y no bloqueante; no debe figurar como pendiente de decisión. |
| STA-02 | **MEDIUM** | `plan.md:277`, `spec.md:234`, `contracts/report-metrics.md:121`, `data-model.md:190` | El título sensible se excluye por defecto en contrato y manifiesto (`include_case_title=false`), pero `plan.md` y los seguimientos lo listan como decisión pendiente; además `FR-020` no menciona el título. | Fijar «excluido por defecto» como decisión vigente; retirarlo de pendientes bloqueantes. Añadir la exclusión del título a `FR-020` en una revisión documental posterior. |
| DEL-01 | **CRITICAL** | `tasks.md:402-410`, `tasks.md:394`, `data-model.md:297`, `spec.md:316` | No hay mecanismo para el intervalo «versión creada → `report_version_id` guardado». Si el proceso cae entre ambos, T061 no puede saber que ya existe una versión y puede crear otra; después, los envíos se duplican. Esto incumple FR-047, FR-033 y el principio XIV (prevenir dobles envíos). | Añadir `generation_key`/`evaluation_id` único en `report_versions` (o crear versión y actualizar la evaluación en una sola transacción) y una recuperación que adopte la versión huérfana por esa clave. Probar el corte entre ambos pasos. |
| DEL-02 | **HIGH** | `tasks.md:279-298`, `tasks.md:407-410` | La revalidación de contacto/consentimiento/manifiesto se declara «antes de enviar», no antes de cada componente. T041 (manual) no la repite antes del PDF; T062 es del corte automático. Una revocación entre resumen y PDF podría permitir el PDF. | Revalidar regla, consentimiento, vínculo y manifiesto inmediatamente antes de cada `send_message`/`send_document`, también en el ejecutor manual. Si cambia, marcar componentes restantes `skipped` con motivo y no llamar. Probar revocación entre componentes. |
| PDF-01 | **HIGH** | `tasks.md:211-213`, `quickstart.md:79-83` | Se atribuyen a pypdf comprobaciones visuales («gráfica no cortada», «texto ≥10 pt»). pypdf puede verificar páginas, texto y objetos embebidos, pero no detecta recortes visuales, espacios ni legibilidad real. | Separar: (a) prueba automática con pypdf para páginas, texto y XObjects; (b) tarea de inspección visual del PDF (abrir el archivo, capturas, revisar cortes, espacios y legibilidad) con firma humana. No presentar la inspección visual como pypdf. |
| PDF-02 | **MEDIUM** | `quickstart.md:34-38` | El comando del gate A0 contiene `...` y no es ejecutable tal como está. | Usar solo `scripts/check_pdf_runtime.py` o un comando completo y reproducible; documentar la salida esperada. |
| PDF-03 | **LOW** | `plan.md:60-61` | Los objetivos de rendimiento (informe ≤10 s, PDF ≤15 s) no tienen tarea de verificación. | Añadir una comprobación de rendimiento con datos ficticios o declararla no bloqueante; no convertirla en requisito de aceptación si no se autoriza. |
| COV-01 | **LOW** | `data-model.md:235-257` | `contact_verification_challenges.status` se describe, pero no tiene una restricción `Check` explícita como las demás tablas. | Añadir `Check(status IN ('pending','consumed','expired','locked'))` y la coherencia con `consumed_at`. |
| COV-02 | **LOW** | `tasks.md:196-232` | T028 agrupa dos archivos de prueba y T049/T050/T066/T067/T068 agrupan dos; reduce trazabilidad y paralelismo. | Mantener un archivo por tarea o declarar explícitamente el dueño de cada archivo; no es un defecto funcional. |

## 3. Dependencias y paralelismo

### 3.1 Cadenas reales del Corte A

```text
T012 → T013 → T014 → T015 → T016 → T017
T012 → T018
T016 → T019
T002 + T017 + T018 + T019 → T020
T013 + T014 + T016 + T018 + T020 + T021 → T022
T022 → T023 → T024/T026
T016 → T025
T027–T032 → T033 → T034
```

No existe un batch «T013/T014/T015/T016 en paralelo». La única paralelización segura tras T012 es
T013 con T021 (y T018), porque T021 depende de T007/T012 y T018 de T012.

### 3.2 Cadenas reales del Corte B

```text
T035 → T036 → T037
T035 → T038
T035 → T039
T038 + T039 + T035 → T040 → T041
T039 + T040 → T042
T041 + T042 → T043
T036 + T037 + T038 → T044
T041 + T042 + T043 → T045
T044 → T046/T048
T045 → T047/T048
T049–T054 según sus dependencias; T054 requiere T047
```

T037 no puede lanzarse con T036; T049–T054 no pueden lanzarse todas «tras T045» sin comprobar T037,
T039/T042, T040/T043, T041 y T047.

### 3.3 Cadenas reales del Corte C

```text
T057 → T058/T059
T059 → T060
T041 + T058 + T059 → T061
T061 → T062 → T063
T058 + T060 → T064 → T065
T066–T071 tras sus dependencias respectivas
T055 + T066–T071 → T072 → T073 → T074 → T075
```

T066–T070 no dependen de T064; T071 depende de T021/T061/T062. La lista «tras T064» es segura pero no
mínima.

### 3.4 Etiquetas `[P]`

- **Correctas**: T036 con T038/T039 tras T035; T046/T048 tras T044; T058/T059 tras T057; T066–T070
  tras sus dependencias.
- **Válidas solo si el batch se forma después de su dependencia**: T002–T005 tras T001; T006 tras
  T002; T037 tras T036; T077 tras T076. La etiqueta no significa que puedan lanzarse junto con la
  tarea de la que dependen.
- **Inválidas**: T014/T015/T016 (cadena) y T033 (depende de T027–T032). La etiqueta `[P]` debe indicar
  que no hay dependencia incompleta en el mismo batch; si la hay, se ejecuta después.

## 4. Responsabilidad de las pruebas

### 4.1 Modelo recomendado

- **Tarea de implementación**: produce el comportamiento y ejecuta la prueba existente; no escribe el
  archivo de prueba.
- **Tarea de prueba**: es dueña del archivo, lo escribe primero, lo ve fallar y luego lo deja en verde.
- **Evidencia de implementación**: comando ejecutado y resultado, no la creación del test.
- **Evidencia de tarea de prueba**: nombres de casos, salida de pytest y cobertura del requisito.

### 4.2 Duplicaciones actuales

| Archivo | Tarea de implementación que lo cita | Tarea de prueba que lo crea | Riesgo |
|---|---|---|---|
| `tests/unit/test_report_dataset.py` | T013 | T028 | Dos dueños potenciales |
| `tests/unit/test_report_service.py` | T022 | T028 | Dos dueños potenciales |
| `tests/unit/test_report_metrics.py` | T014 | T027 | Dos dueños potenciales |
| `tests/unit/test_report_pdf.py` | T020 | T030 | Dos dueños potenciales |
| `tests/unit/test_report_privacy.py` | T009 | T032 | Dos dueños potenciales |
| `tests/unit/test_report_manifest.py` | T039 | T050 | Dos dueños potenciales |
| `tests/unit/test_confirmations.py` | T042 | T050 | Dos dueños potenciales |
| `tests/unit/test_manual_send.py` | T043 | T051 | Dos dueños potenciales |
| `tests/unit/test_delivery_idempotency.py` | T040 | T051 | Dos dueños potenciales |
| `tests/unit/test_delivery_recovery.py` | T041 | T052 | Dos dueños potenciales |
| `tests/unit/test_notification_rules.py` | T058 | T066 | Dos dueños potenciales |
| `tests/unit/test_rule_evaluation.py` | T059 | T067 | Dos dueños potenciales |
| `tests/unit/test_rule_recovery.py` | T061 | T068 | Dos dueños potenciales |
| `tests/unit/test_rule_revalidation.py` | T062 | T069 | Dos dueños potenciales |
| `tests/unit/test_cross_mode_delivery.py` | T063 | T070 | Dos dueños potenciales |

### 4.3 Pruebas sin tarea que las cree

- `tests/unit/test_canonical_json.py` (T007)
- `tests/unit/test_report_aliasing.py` (T015)
- `tests/unit/test_report_charts.py` (T016)
- `tests/unit/test_report_artifacts.py` (T018)
- `tests/unit/test_report_synthesis.py` (T021)
- `tests/contract/test_report_routes.py` (T023)
- `tests/unit/test_reports_migration.py` (T012)
- `tests/unit/test_notifications_manual_migration.py` (T035)
- `tests/unit/test_notification_rules_migration.py` (T057)
- `tests/unit/test_telegram_transport.py` (T038)
- `tests/unit/test_delivery_states.py` (T040)

Consecuencia: esos comportamientos no tienen una verificación identificable o quedan a criterio de la
tarea de implementación. Es un defecto de planificación, no una prueba fallida.

## 5. Síntesis del informe

### 5.1 Regla de dígitos

`research.md:85` y `tasks.md:164` prohíben todos los dígitos en el texto generado. El objetivo
correcto es impedir cifras inventadas o alteradas, no impedir:

- identificadores del informe (`report_id`, `report_version_number`);
- referencias Qualys válidas (`QID`, `CVE-AAAA-NNNN`);
- referencias documentales y números de fragmento/cita;
- años o identificadores de norma.

El texto generado no debe producir cifras nuevas. Las cifras del informe se renderizan desde
`dataset_json`. La validación debe:

1. extraer cada token numérico del texto;
2. aceptarlo si coincide con una clave/valor del dataset o con un patrón de identificador autorizado;
3. rechazar cualquier otro número;
4. no exigir la ausencia total de dígitos.

### 5.2 Referencias documentales

`basis='documentary'` no es evidencia. Debe exigir:

- `evidence_refs` no vacío;
- cada referencia resuelve a un fragmento o cita existente del caso o del corpus autorizado;
- el validador de citas existente acepta la cita;
- la afirmación no excede lo que la cita respalda;
- si falla, la recomendación se degrada a `agent_proposal` o se rechaza, y se registra el motivo.

### 5.3 Recomendaciones propuestas

`agent_proposal` es válido, pero debe mostrarse como propuesta y no como hecho. `csv_fact` debe
referenciar claves del dataset. La UI y el PDF deben separar visualmente:

- hechos calculados;
- respaldo documental verificado;
- propuestas del agente sin respaldo.

El fallback factual («Sin síntesis de IA») sigue siendo válido si la validación falla.

## 6. Estado y decisiones

- **Top 5**: ya es el valor predeterminado en `plan.md:56`, `plan.md:160`, `contracts/report-metrics.md`
  y `tasks.md`. No es una decisión bloqueante. La revisión de producto es opcional.
- **Título sensible**: ya está excluido por defecto en `contracts/report-metrics.md:121`,
  `data-model.md:190` y `contracts/telegram-delivery.md:85` mediante `include_case_title=false`. No es
  una decisión bloqueante. `spec.md` FR-020 no lo menciona; es una omisión documental, no un cambio de
  alcance.
- **Respaldo documental**: sigue siendo una decisión real de alcance para el primer corte; no es un
  defecto. Se puede implementar como `agent_proposal` sin cita y declararlo.
- **Verificaciones futuras**: Playwright/Chrome, renderizado Node, inspección visual del PDF, envío real
  de prueba, llamadas pagadas y presupuesto no son defectos actuales; son comprobaciones no ejecutadas.

### 6.1 AGENTS.md

`AGENTS.md` sigue siendo coherente: declara que Telegram no está implementado, que el producto usa un
solo proceso y un worker, SQLite como fuente de verdad, recursos locales sin CDN y secretos fuera del
repositorio. El diseño de 006 no contradice esas reglas. No se encontró una obligación de AGENTS.md
sin cobertura en las tareas.

## 7. Entrega y recuperación

### 7.1 Corte B

El Corte B contiene:

- `contact_channels`, `contact_case_links`, `contact_verification_challenges`;
- `report_confirmations`;
- `notification_events`, `notification_components`, `notification_attempts`;
- transporte Telegram, manifiesto, confirmación, ejecutor manual y recuperación.

No depende de `notification_rules`. Esto cumple la corrección de independencia.

### 7.2 Verificación vs envío de informe

La separación está bien definida en `spec.md` FR-021/FR-045, `contracts/telegram-delivery.md` y
`tasks.md` T037/T044/T049. El código se envía con `unverified`, sin consentimiento ni vínculo; el
informe exige los tres. No se encontró contradicción.

### 7.3 Manifiesto, invalidación y revalidación

- El manifiesto está definido y compartido por confirmación y ejecución.
- La invalidación por cambio de texto/PDF/política/destinatarios está en T042/T050.
- La revalidación antes de enviar está en T062, pero **no se exige antes de cada componente** y no se
  aplica explícitamente al ejecutor manual T041. Ver DEL-02.

### 7.4 Interrupción entre informe y evaluación

Es el hallazgo **DEL-01**. La versión se crea y luego se guarda `report_version_id`; no hay clave única
de generación ni transacción/recuperación para ese intervalo. Sin corrección, un reinicio puede crear
otra versión o reenviar. La corrección pertenece a la migración de A (T012) y a T061/T068.

### 7.5 Componentes aceptados e inciertos

T040/T041/T052/T063/T068 cubren que un componente aceptado no se reenvía y que un incierto no se
reintenta automáticamente. No se encontró contradicción; la verificación debe ejecutarse con dobles.

## 8. PDF y aceptación

- **Automático**: pypdf puede verificar número de páginas, extracción de texto y presencia de objetos
  embebidos. También puede comprobar que no hay páginas vacías por texto extraído.
- **Visual**: la ausencia de recortes, espacios, solapamientos y legibilidad real requiere abrir el PDF
  y revisarlo, con capturas o rasterización. No debe atribuirse a pypdf.
- **Tarea faltante**: no hay una tarea explícita de inspección visual del PDF. T031 es navegador web;
  T030 es pypdf. Añadir una tarea de inspección visual con firma humana y evidencia (capturas).
- **CSS**: `break-inside: avoid` y `@page` son condiciones de diseño; su efecto debe verificarse
  visualmente, no solo por la presencia de la regla.

## 9. Cobertura

| Requisitos | Tareas principales | Cobertura | Observación |
|---|---|---|---|
| FR-001–FR-015 informe | T012–T034 | Sí | Faltan tareas de prueba para artefactos, rutas, gráficas y síntesis |
| FR-016–FR-021 contactos | T035–T050 | Sí | Verificación separada correcta; falta revalidación por componente |
| FR-022–FR-036 envío/reglas | T040–T075 | Sí | Idempotencia y recuperación cubiertas; DEL-01 en el vínculo versión-evaluación |
| FR-037–FR-041 seguridad | T009, T010, T038, T053, T080 | Sí | Sin hallazgos críticos; pruebas de privacidad presentes |
| FR-042–FR-048 idempotencia/verificación/manifiesto/cortes | T037–T075 | Sí | FR-047 depende de DEL-01; FR-048 no tiene prueba directa |
| SC-001–SC-012 | T027–T080 | Parcial | SC-002 requiere inspección visual; SC-009 requiere tarea de prueba de síntesis |

**Métricas**:

- Requisitos: 48 FR + 12 SC = 60.
- Tareas: 81.
- Cobertura formal (al menos una tarea por requisito): 100 %.
- Cobertura de verificación dedicada: incompleta en síntesis, artefactos, rutas, migraciones y
  transporte.
- Ambigüedades: 4 (dígitos, propiedad de tests, revalidación por componente, PDF visual).
- Duplicaciones: 1 principal (archivos de test con dos dueños) y 1 de estado (top 5/título).
- Críticos: 1 (DEL-01).
- Altos: 10 (DEP-01, DEP-02, DEP-03, DEP-04, TST-01, TST-02, SYN-01, SYN-02, DEL-02, PDF-01).
- Medios: 6.
- Bajos: 4.


### 9.1 Mapa FR/SC → tareas

| Requisito | Tareas | Observación |
|---|---|---|
| FR-001 | T013, T022, T060 | Solo snapshot confirmado |
| FR-002 | T012, T013, T022, T028 | Versión inmutable |
| FR-003 | T019, T020, T029 | Concordancia web/PDF |
| FR-004 | T014, T024, T027 | Tarjetas separadas |
| FR-005 | T014, T027 | Indicadores independientes |
| FR-006 | T014, T016, T027 | Escala 1–5 |
| FR-007 | T016, T024 | Cuatro gráficas |
| FR-008 | T015, T016, T024, T027 | Top 5, recorte y tabla |
| FR-009 | T016 | Título-conclusión |
| FR-010 | T021, T024 | Resumen, focos y recomendaciones |
| FR-011 | T014, T021 | Cifras en SQLite |
| FR-012 | T021 | Falta validación de citas; ver SYN-02 |
| FR-013 | T009, T014, T027 | Desconocidos no son ausencia |
| FR-014 | T019, T020, T030 | PDF 2–3 páginas; ver PDF-01 |
| FR-015 | T022, T028 | Nueva versión al regenerar |
| FR-016 | T036, T044, T046 | Contactos y canales |
| FR-017 | T003, T036, T038, T046 | Token fuera de SQLite/UI |
| FR-018 | T045, T047 | Informes y notificaciones del caso |
| FR-019 | T058, T064, T065 | Modalidad por regla |
| FR-020 | T009, T038, T043, T053 | Falta mención del título; ver STA-02 |
| FR-021 | T036, T042, T043, T062 | Solo informes; código aparte |
| FR-022 | T043, T045, T055 | Flujo manual |
| FR-023 | T043, T060, T067 | Sin envío en selección/vista previa |
| FR-024 | T042, T050 | Invalidación por edición |
| FR-025 | T058, T065 | Campos de la regla |
| FR-026 | T058, T064, T066 | Reactivación |
| FR-027 | T060, T067 | Solo importación confirmada |
| FR-028 | T061, T063, T070 | Evidencia automática |
| FR-029 | T038, T043, T053 | Resumen y PDF |
| FR-030 | T040, T045, T054 | Registro por destinatario |
| FR-031 | T040, T041, T052, T054 | Estados de entrega |
| FR-032 | T041, T052 | Resultado parcial |
| FR-033 | T040, T051, T063, T070 | Idempotencia sin modo |
| FR-034 | T041, T052 | Evento persistido |
| FR-035 | T041, T052, T063 | Timeout sin reintento ciego |
| FR-036 | T042, T058, T065 | Confirmación vs regla |
| FR-037 | T009, T039, T053 | Contenido limitado |
| FR-038 | T032, T053, T073 | Aislamiento por caso |
| FR-039 | T010, T038, T053 | Errores sin secretos |
| FR-040 | T036, T043, T062 | Bloqueo de destinos inválidos |
| FR-041 | T055, T072, T080 | Dobles y autorización posterior |
| FR-042 | T040, T041, T052, T063 | Componentes aceptados no se reenvían |
| FR-043 | T059, T060, T067 | Evaluación idempotente |
| FR-044 | T040, T063, T070 | Reutilización de evento |
| FR-045 | T037, T044, T049 | Desafío y envío de código |
| FR-046 | T039, T042, T051, T062 | Manifiesto aprobado |
| FR-047 | T061, T068 | DEL-01: falta vínculo atómico |
| FR-048 | T035, T057 | Sin prueba directa de independencia |
| SC-001 | T029 | Concordancia 100 % |
| SC-002 | T030 + inspección visual | Falta tarea visual; ver PDF-01 |
| SC-003 | T060, T067 | Cero desde staging/rechazo |
| SC-004 | T036, T043, T062 | Bloqueo de destinatario |
| SC-005 | T040, T051, T063, T070 | Sin duplicados |
| SC-006 | T061, T063, T070 | Evidencia automática |
| SC-007 | T022, T028 | Snapshot histórico |
| SC-008 | T009, T032, T053 | Privacidad |
| SC-009 | T021, T033 | Falta prueba dedicada; ver TST-03 |
| SC-010 | T055 | Recorrido manual |
| SC-011 | T039, T042, T051, T062 | Manifiesto |
| SC-012 | T037, T049 | Verificación sin bloqueo |

## 10. Separación entre defectos y verificaciones no ejecutadas

### Defectos documentales actuales

- DEP-01–DEP-06 (paralelismo y `[P]`).
- TST-01–TST-03 (propiedad de pruebas y pruebas faltantes).
- SYN-01–SYN-03 (validación de síntesis).
- STA-01–STA-02 (top 5/título tratados como pendientes).
- DEL-01–DEL-02 (recuperación y revalidación por componente).
- PDF-01–PDF-02 (pypdf vs inspección visual y comando placeholder).
- COV-01–COV-02 (restricciones y agrupación de tests).

### Verificaciones aún no ejecutadas

- Gate real de Playwright/Chrome.
- Renderizado Node de SVG.
- Inspección visual real del PDF.
- Navegador de escritorio y móvil.
- Envío real de prueba a Telegram.
- Llamadas pagadas y presupuesto.
- Evaluación semántica humana.
- Rendimiento de informe/PDF.

No deben presentarse como defectos ni como aprobaciones. Son comprobaciones posteriores con
autorización concreta.

## 11. Dictamen inicial sobre el inicio del Corte A (histórico)

**NO-GO inmediato (previo a la pasada de correcciones).** El Corte A puede comenzar cuando se corrijan, como mínimo:

1. **DEL-01**: clave de generación/transacción para el vínculo versión-evaluación, porque afecta al
   esquema de T012 y a la idempotencia de C.
2. **DEP-01, DEP-02, DEP-05**: cadenas y `[P]` de A, para no ejecutar T013–T016 en paralelo.
3. **SYN-01–SYN-03**: validación numérica/referencial y contrato de síntesis.
4. **TST-01–TST-03**: propiedad única de tests y tarea de prueba de síntesis.
5. **PDF-01–PDF-02**: separar pypdf de inspección visual y hacer ejecutable el gate A0.

DEP-03/DEP-04 y DEL-02 afectan a B/C y pueden corregirse antes de esos cortes, pero deben quedar
resueltos antes de implementarlos. STA-01/STA-02 son correcciones de seguimiento, no bloquean A.

Una vez corregidos esos puntos, el Corte A es el MVP adecuado y puede validarse de forma independiente.

## 12. Resolución de la pasada de correcciones (2026-11-23)

Se aplicó una única pasada documental. No se implementó código, no se instalaron dependencias, no se
ejecutaron migraciones, no hubo llamadas pagadas ni envíos.

### 12.1 Estado por hallazgo

| ID | Estado | Resolución y ubicaciones |
|---|---|---|
| DEL-01 | **Resuelto** | `report_versions.generation_key` único nullable; `notification_rule_evaluations.generation_key = auto:<evaluation.id>`; creación/recuperación con `INSERT ... ON CONFLICT DO NOTHING`; T012/T035/T057/T061/T068; `data-model.md:23-63`, `research.md`, `plan.md`, `contracts/telegram-delivery.md`. |
| DEL-02 | **Resuelto** | Revalidación de destinatario, consentimiento, vínculo, manifiesto y regla antes de cada componente; T041/T052/T062/T069; `contracts/telegram-delivery.md:99-116`, `data-model.md` invariante 16. |
| DEP-01 | **Resuelto** | T013→T014→T015→T016 secuenciados; `tasks.md` Test Ownership/Dependencies/Parallel Examples. |
| DEP-02 | **Resuelto** | Batches de Setup/Foundational corregidos; `[P]` retirado de T006/T011/T014/T015/T016/T031/T033/T037/T077. |
| DEP-03 | **Resuelto** | T036→T037; T038/T039 paralelos tras T035. |
| DEP-04 | **Resuelto** | T049–T054 con dependencias explícitas; T054 tras T047. |
| DEP-05 | **Resuelto** | `[P]` retirado de T033; ruta de pruebas secuenciada. |
| DEP-06 | **Resuelto** | Ruta crítica reescrita con T015, T037, T047, T054 y T061; notación sin paralelismo falso. |
| TST-01 | **Resuelto** | Matriz «Test Ownership»: un dueño por archivo; implementaciones remiten al dueño. |
| TST-02 | **Resuelto** | Pruebas faltantes asignadas: T007, T010, T012, T015, T016, T018, T021, T023, T035, T038, T040, T057. |
| TST-03 | **Resuelto** | T021 crea `test_report_synthesis.py`; T071 amplía el caso automático; T068 cubre crash de generación. |
| SYN-01 | **Resuelto** | `research.md` R6 y `tasks.md` T021 eliminan la prohibición general de dígitos; `contracts/report-synthesis.md` define `claim_refs`, identificadores y rechazo de números libres. |
| SYN-02 | **Resuelto** | `documentary` exige cita existente/aceptada; se documenta que la validación literal no garantiza respaldo semántico; sin respaldo comprobado se muestra como propuesta. |
| SYN-03 | **Resuelto** | `contracts/report-synthesis.md` es el contrato canónico; referenciado en `plan.md`, `research.md`, `data-model.md` y T021/T071. |
| STA-01 | **Resuelto** | Top 5 es predeterminado en `spec.md`, `plan.md`, `contracts/report-metrics.md` y seguimientos; no es decisión bloqueante. |
| STA-02 | **Resuelto** | Título sensible excluido por defecto (`include_case_title=false`) en `spec.md` FR-020, contrato, modelo y seguimientos. |
| PDF-01 | **Resuelto** | T030 solo pypdf (páginas/texto/objetos); T031 inspección visual del PDF con capturas/notas; `quickstart.md` A3 separado. |
| PDF-02 | **Resuelto** | `quickstart.md` A0 usa `scripts/check_pdf_runtime.py`; sin `...`. |
| PDF-03 | **Aclarado, no bloqueante** | Los tiempos de `plan.md` son objetivos por medir, no resultados; no se añade requisito de aceptación. |
| COV-01 | **Resuelto** | `data-model.md` añade `Check(status IN ('pending','consumed','expired','locked'))` y `consumed_at`; T035 lo prueba. |
| COV-02 | **Resuelto** | La matriz Test Ownership permite agrupar archivos con un solo dueño; no se duplica trabajo. |

### 12.2 Conteo y cobertura

- Tareas vigentes: **81** (T001–T081). No se añadieron tareas; se corrigieron dependencias, propiedad
  de pruebas y alcance.
- Cobertura formal: 48 FR + 12 SC, todos con al menos una tarea.
- Cobertura de verificación: cada archivo de prueba tiene un dueño; síntesis, artefactos, rutas,
  migraciones, transporte, desafío y crash de generación tienen prueba asignada.
- Dependencias: A independiente tras Foundational; B depende de A por `report_versions`; C depende de
  A/B; Polish al final.

### 12.3 Revisión final de solo lectura

Se revisaron los artefactos corregidos sin ejecutar código:

- 81 tareas secuenciales, sin IDs duplicados.
- Sin cadenas `[P]` falsas: T006/T011/T014/T015/T016, T031, T033, T037 y T077 no se declaran paralelas.
- Matriz de propiedad de pruebas completa; no hay archivo sin dueño ni dueño duplicado.
- `generation_key` presente en especificación, modelo, research, plan, contratos y tareas.
- Revalidación por componente presente en T041/T052/T062/T069 y contrato de entrega.
- `report-synthesis-v1` presente en contrato, research, plan y tareas; sin prohibición general de
  dígitos.
- PDF automático y visual separados; pypdf no se usa para recortes/legibilidad.
- Top 5 y título sensible sincronizados como defaults; no hay pendientes bloqueantes.
- `quickstart.md` sin comandos con `...`.
- No se modificaron `AGENTS.md` ni las autorizaciones registradas.

**Resultado de la revisión final**: PASS documental. Quedan verificaciones futuras no ejecutadas:
Playwright/Chrome, renderizado Node, inspección visual real del PDF, navegador real, envío real,
llamadas pagadas, evaluación semántica y rendimiento.

### 12.4 Dictamen vigente

**GO para iniciar el Corte A** una vez revisado este informe. El Corte A es el MVP y puede validarse
de forma independiente. No se declara aceptación funcional, no se ejecutó código y no se envió nada.
Las verificaciones futuras requieren autorización concreta y no bloquean el inicio del Corte A.

## 13. Próximas acciones

- Revisar este informe y confirmar el GO documental.
- Iniciar el Corte A por T001–T034, respetando la secuencia corregida.
- Ejecutar primero el gate A0 (`scripts/check_pdf_runtime.py` y `render_report_charts.mjs --check`).
- Ejecutar pruebas automáticas y la inspección visual del PDF de T031; registrar evidencia.
- No declarar aceptación funcional sin ejecutar las verificaciones pendientes.
- No ejecutar `/speckit.implement`; implementar por tareas cuando se autorice.
