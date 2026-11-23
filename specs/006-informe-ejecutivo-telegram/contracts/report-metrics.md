# Contrato — Métricas del informe (`report-dataset-v1`)

**Alcance**: define qué significa cada tarjeta y gráfica, su universo y su denominador. Es el
contrato que garantiza concordancia SQLite → dataset → tarjetas → gráficas → PDF.

## Base de cálculo

- Población: filas de `qualys_vulnerabilities` con `case_id` y `import_id` de la instantánea
  `confirmed` seleccionada.
- Filtros opcionales del informe: `asset`, `qid`, `cve`, `severity_level`, `exploitability`,
  `malware`, `priority`, `status_group`. Se aplican antes de agregar y se registran en
  `filters_json`.
- Conteos: `COUNT(*)` sobre filas de vulnerabilidad. Prohibido `COUNT(DISTINCT cve)` y `JOIN` a
  `qualys_vulnerability_cves` en agregados.
- Cada tarjeta y gráfica declara `scope` y `denominator`. Si el denominador es distinto del total del
  snapshot, la UI lo muestra junto al título.

## Tarjetas

| Clave | Etiqueta visible | Cálculo | Denominador |
|---|---|---|---|
| `pending` | Registros pendientes | `status_group = 'pending_known'` (Active, New, Re-Opened) | `base.total_rows` |
| `critical_pending` | Críticas pendientes (nivel 5) | `pending_known AND severity_level = 5` | `base.pending_known` |
| `high_pending` | Altas pendientes (nivel 4) | `pending_known AND severity_level = 4` | `base.pending_known` |
| `distinct_assets_pending` | Activos distintos afectados | `COUNT(DISTINCT asset_label)` en `pending_known`, excluyendo `Sin activo` | `base.pending_known` |
| `exploitability_positive_pending` | Explotabilidad positiva (pendientes) | `pending_known AND exploitability_eval = 'positive'` | `base.pending_known` |
| `malware_positive_pending` | Malware positivo (pendientes) | `pending_known AND malware_eval = 'positive'` | `base.pending_known` |
| `both_positive_pending` | Ambos indicadores positivos (pendientes) | `pending_known AND ambos = 'positive'` | `base.pending_known` |
| `fixed` | Registros Fixed | `status_group = 'fixed'` | `base.total_rows` |
| `manual_review` | Requieren revisión de estado o indicadores | Unión contada una vez: `status_group='manual_review' OR exploitability_eval='indeterminate' OR malware_eval='indeterminate'` | `base.total_rows` |

Reglas:

- `manual_review` NO se suma con `pending`, `fixed` ni con las distribuciones.
- `exploitability_positive_pending` y `malware_positive_pending` son independientes; un registro puede
  estar en ambos. `both_positive_pending` es la intersección, no una suma.
- `distinct_assets_pending` informa `unknown_asset_rows` (filas con `asset_label = 'Sin activo'`) y el
  orden de identificación `FQDN > DNS > NetBIOS > IP`.
- La severidad crítica no se presenta como P1. La política P1–P4 está fuera de alcance.

## Gráficas

### G1 — Distribución de severidad

- Título-conclusión determinista: «El N % de los registros pendientes es de severidad 3 o superior».
- Series: `pendientes` y `fixed`, barras agrupadas por nivel 1–5.
- Denominadores: `severity.denominator_pending` y `severity.denominator_fixed`, declarados bajo el
  título. No se mezclan en un mismo porcentaje.
- Etiquetas: 1 Informativa, 2 Baja, 3 Media, 4 Alta, 5 Crítica.
- Tabla alternativa: nivel, pendientes, fixed, total por serie.
- Prohibido: 3D, pastel decorativo, suma de series como si fueran una sola población.

### G2 — Activos con mayor concentración de críticos/altos

- Base: `pending_known` con `severity_level IN (4,5)`.
- Orden: críticos descendente, altos descendente, total descendente, etiqueta ascendente.
- Top `N = 5` por defecto; el resto se agrupa como «Otros (K activos, M registros)». El valor 5 no
  requiere una decisión bloqueante adicional.
- Título-conclusión: «5 activos concentran M de R registros críticos/altos (P %)».
- Declara `total_assets`, `assets_with_critical_or_high`, `recorted` y el criterio de desempate.
- Contenido saliente: alias `Activo 01..N`; nunca FQDN/DNS/NetBIOS/IP. La vista local puede mostrar
  la etiqueta interna junto al alias, sin incluirla en el PDF ni en el mensaje.
- Tabla alternativa con alias, críticos, altos, total.

### G3 — Explotabilidad

- Base: `pending_known`. Categorías excluyentes dentro de esta distribución:
  `positive`, `negative_no_info`, `indeterminate`.
- Título-conclusión: «X de N registros pendientes tienen explotabilidad positiva; Y no la informan».
- `negative_no_info` significa negativo o no informado; no equivale a «sin amenaza».
- Tabla alternativa con valores y denominador.

### G4 — Malware

- Base: `pending_known`. Mismas categorías y reglas que G3, con su propio denominador.
- Título-conclusión propio.
- Prohibido sumar G3 y G4 o presentarlas como una sola categoría.

## Concordancia web ↔ PDF (SC-001)

1. Ambos leen el mismo `dataset_json` y `chart_specs_json` de la misma `report_version`.
2. El HTML de impresión y la vista web renderizan las mismas claves de tarjeta y los mismos títulos.
3. La prueba de contrato compara, para cada tarjeta y gráfica, el valor del dataset con el texto
   extraído del HTML y del PDF (pypdf) y con los datos de la tabla alternativa.
4. El PDF incluye el `report_version.id`, la secuencia de snapshot y la fecha. La vista web muestra
   los mismos identificadores.
5. Un cambio de dataset exige nueva versión; nunca se reescribe una versión publicada.

## Cobertura y limitaciones

`coverage` incluye, como mínimo:

- proporción de registros con explotabilidad conocida (`positive` + `negative_no_info` sobre
  `pending_known`);
- proporción con malware conocido;
- proporción con severidad conocida (siempre 1–5 por validación de 002);
- campos faltantes agregados (por ejemplo, activos sin identificación);
- texto fijo: «Un campo vacío se muestra como no informado; no demuestra ausencia de amenaza» y «Un
  total 0 no demuestra ausencia de vulnerabilidades».

## Contenido aprobado (`report-manifest-v1`)

La confirmación manual y la ejecución comparten un manifiesto canónico con:

- `case_id`, `report_id`, `report_version_id`, `report_version_number`;
- `dataset_sha256`;
- `outbound_text` y `outbound_text_sha256`;
- `pdf_sha256`;
- `content_policy`;
- `recipients` (contact_id, alias, chat_fingerprint) y `recipients_sha256`.

El ejecutor recalcula el manifiesto y compara `manifest_sha256` antes de llamar a Telegram. Si el
texto, el PDF, la política o los destinatarios cambian, la confirmación manual se invalida o la regla
exige reactivación. El manifiesto no se presenta como contenido saliente: es evidencia de lo
aprobado.

## Privacidad del contenido saliente

| Campo | Vista local | PDF | Mensaje Telegram |
|---|---|---|---|
| Cifras agregadas | Sí | Sí | Sí |
| Título del caso | Sí | No por defecto (`include_case_title=false`) | No por defecto |
| Alias de activo | Sí | Sí | Sí |
| Etiqueta interna del activo | Sí | No | No |
| IP/DNS/NetBIOS/FQDN | Sí (si existe) | No | No |
| Results / filas crudas | No | No | No |
| CVEs detallados | Sí (detalle técnico) | No por defecto | No |
| Token del bot | No | No | No |

La vista previa muestra exactamente el texto y el PDF que saldrán. El evento guarda
`content_policy_json` y `content_sha256`.
