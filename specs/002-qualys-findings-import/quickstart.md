# Quickstart — Vulnerabilidades Qualys

Guía de validación de la funcionalidad 002. No incluye código de implementación ni datos reales.

## 1. Prerrequisitos

- Python 3.14.6, `uv`, Node.js 26.11.1 para recursos.
- Ollama con `qwen3.5:9b` y `embeddinggemma` para la consulta conversacional.
- Base migrada y recursos locales.
- Para la aceptación real opcional: los archivos autorizados fuera del repositorio:
  - `../14-Qualys_Hallazgos_Active_New_ReOpened.csv`
  - `../14-Qualys_Hallazgos_Active_New_ReOpened_manifest.json`

No se versionan el CSV real, sus filas, IP, activos, resultados ni el manifiesto con datos derivados.

## 2. Preparación

```bash
make install
make assets
uv run alembic upgrade head
make dev
```

Abrir `http://127.0.0.1:8000/cases` y entrar a un caso. La barra del caso debe mostrar:

```text
Resumen · Documentos · Vulnerabilidades · Consulta documental
```

## 3. Fixtures sintéticos

La implementación creará estos archivos, todos sintéticos:

| Fixture | Propósito |
|---|---|
| `tests/fixtures/files/qualys_synthetic_valid.csv` | 5 filas, 41 columnas, BOM, comillas, multilínea y estados admitidos |
| `tests/fixtures/files/qualys_synthetic_second.csv` | Snapshot posterior con un registro nuevo y uno ya presente |
| `tests/fixtures/files/qualys_synthetic_mixed.csv` | `Fixed`, estado desconocido, ambos/solo uno positivos, vacíos e indeterminados |
| `tests/fixtures/files/qualys_synthetic_invalid_header.csv` | Encabezado/columnas inválidas |
| `tests/fixtures/files/qualys_synthetic_invalid_rows.csv` | Severidad, fecha, QID o CVE inválidos; incluye CVE de 4–7 dígitos válidos y formatos inválidos |
| `tests/fixtures/files/qualys_synthetic_empty.csv` | Archivo vacío o sin filas para rechazo `empty_file` |
| `tests/fixtures/files/qualys_synthetic_manifest.json` | Manifiesto sintético para `matched`, `mismatch` e `invalid` |

No se usan filas del archivo real para crear estos fixtures. Los CVE sintéticos cubren longitudes de
4 a 7 dígitos.

## 4. Recorrido principal con fixture sintético

1. Abrir el caso → **Vulnerabilidades**.
2. Pulsar **Cargar reporte de Qualys**.
3. Seleccionar `qualys_synthetic_valid.csv` desde el equipo. No escribir una ruta.
4. Pulsar **Validar archivo**. Comprobar el indicador de carga y que un doble clic no duplique el
   envío.
5. En **Vista previa**, comprobar que el archivo queda `staged` y que muestra:
   - archivo y hash;
   - 5 filas detectadas, 5 válidas, 0 inválidas;
   - estados: `Active` 1, `New` 1, `Re-Opened` 1, `Fixed` 1, desconocido 1;
   - severidades 1–5 con etiquetas Informativa/Baja/Media/Alta/Crítica;
   - explotabilidad: 3 positivas, 0 negativas/no informadas, 2 indeterminadas;
   - malware: 2 positivos, 1 negativo/no informado, 2 indeterminados;
   - ambos positivos: 2;
   - un posible grupo de repetición por combinación parcial;
   - advertencias de estado desconocido y de indicadores indeterminados.
6. Pulsar **Confirmar importación**. Solo un archivo `staged` puede confirmarse.
7. Comprobar el resumen, el snapshot confirmado y la tabla. Las filas `Fixed` y «Revisión manual» no
   deben aparecer como pendientes activos.
8. Abrir **Consulta documental** y preguntar:
   «¿Cuántos registros de vulnerabilidades pendientes hay por activo?».
   La respuesta debe mencionar el snapshot, el origen importado y los conteos recalculables.
9. Verificar que las filas no son documentos: no aparecen en fragmentos, citas ni Chroma.

## 5. Idempotencia y snapshots

1. Volver a cargar el mismo `qualys_synthetic_valid.csv` y confirmar.
   Esperado: cero filas nuevas, cero cambios de conteos, enlace al snapshot existente.
2. Cargar `qualys_synthetic_second.csv` y confirmar.
   Esperado: nuevo snapshot, una fila nueva y una ya presente; el total no suma ambos snapshots.
3. En la sección, dejar el selector en el último snapshot y comprobar sus conteos.
4. Seleccionar el snapshot anterior y comprobar que los conteos vuelven a los de ese snapshot.
5. Verificar que la ausencia de un registro en el segundo snapshot no se etiqueta como corregido ni
   remediado.
6. En un turno nuevo, seleccionar el snapshot anterior. En el mismo turno, solicitar otro snapshot
   después de la primera consulta debe devolver `snapshot_locked`; no puede cambiar en silencio.

## 6. Estados, severidad y prioridad

Con `qualys_synthetic_mixed.csv`:

- `Active`, `New` y `Re-Opened` son `pending_known`.
- `Fixed` es `fixed` y no se suma a pendientes.
- Un estado desconocido es `manual_review`, conserva el valor original y no bloquea.
- La severidad conserva el valor original, el nivel 1–5 y la etiqueta del proyecto.
- Ambos indicadores positivos: bandera «Prioritaria: explotabilidad y malware» con motivo.
- Solo un indicador positivo: se muestra el indicador, sin la bandera conjunta.
- Vacío o estructura no reconocida: indeterminado; no se presenta como positivo.
- Un `Fixed` con ambos indicadores positivos se muestra como antecedente prioritario reportado, no
  como remediación pendiente.

## 7. Filtros y conteos

En la tabla y mediante el agente:

- Filtrar por estado `pending_known`, `fixed`, `manual_review` y `all`; cada resultado debe indicar el
  grupo aplicado.
- Filtrar por nivel 1–5 y etiqueta del proyecto.
- Filtrar por prioridad, explotabilidad y malware.
- Filtrar por activo, QID y CVE.
- Un registro con varios CVE debe contar una vez; el filtro por uno de sus CVE lo devuelve.
- Un caso con datos sintéticos e importados debe mostrar desglose por origen. Un filtro de severidad
  sin origen debe rechazarse como ambiguo.
- `origin=imported` sin `status_group` usa `pending_known`; `origin=all` usa `all` y devuelve bloques
  separados. `origin=all` con `status_group` distinto de `all` debe rechazarse con
  `origin_required_for_status_filter`.
- `snapshot_id`, `priority`, `exploitability` y `malware` solo se aceptan con `origin=imported`; con
  `origin=all` o `origin=synthetic` devuelven `filter_not_applicable`.
- `status_group` con `origin=synthetic` devuelve `filter_not_applicable`; con `origin=all` solo se
  admite `all`.
- Un `snapshot_id` distinto después de fijar la instantánea del turno devuelve `snapshot_locked`.

## 8. Aislamiento y errores

1. Crear un segundo caso sin importaciones.
2. Abrir `Vulnerabilidades`: debe mostrar «sin importaciones confirmadas» con CTA; no debe mostrar
   «sin registros para estos filtros».
3. En el primer caso, con una importación confirmada, aplicar un filtro sin coincidencias: debe
   mostrar «sin registros para estos filtros». Ninguno de los dos estados afirma ausencia de
   vulnerabilidades ni riesgo bajo.
4. Abrir una URL de snapshot del primer caso bajo el segundo: debe responder 404.
5. Validar `qualys_synthetic_invalid_header.csv`: debe rechazar con columnas esperadas/detectadas y
   sin incorporar filas.
6. Validar `qualys_synthetic_invalid_rows.csv`: debe quedar `rejected`, mostrar filas inválidas con
   número y motivo y no ofrecer confirmación. No existe un control para «aceptar solo filas válidas»
   ni se crea un snapshot parcial.
7. Validar `qualys_synthetic_empty.csv`: debe quedar `rejected` con `empty_file`, `csv_bytes=0` y sin
   filas consultables.
8. Cancelar una vista previa `staged` o `rejected`: la instantánea vigente no cambia. Volver a la URL
   debe informar cancelación/expiración y ofrecer cargar de nuevo.

## 9. Aceptación local con el archivo real

Esta prueba es una comprobación separada; no se ejecuta en CI ni se versiona el archivo. Puede quedar
no ejecutada si faltan los archivos, pero no se reporta como aprobada. La aceptación real solo se
ejecuta después de las pruebas de privacidad y manifiesto.

```bash
export SECGUARD_STORAGE_DIR=/ruta/temporal/fuera/del/repositorio
export LANGSMITH_TRACING=false
uv run alembic upgrade head
```

1. Verificar que el CSV autorizado tiene SHA-256
   `f55ab562f2fe5a41654f5c256a0ba9a281b446ebbe608514e06d0100af934e34` y 1.355.926 bytes.
2. Pasar la ruta del manifiesto al servicio de validación de la aceptación local, no al formulario ni
   a una ruta HTTP. Si no se aporta, la validación continúa con `manifest_status=absent`.
3. Si el manifiesto es válido y coincide, `manifest_status=matched`; si no coincide,
   `manifest_mismatch` y `rejected`; si está malformado, `manifest_invalid` y `rejected`.
4. Verificar contra el manifiesto: 662 filas, 41 columnas, `Active` 631, `New` 10, `Re-Opened` 21,
   `Fixed` 0. Si el hash o las cantidades no coinciden, el archivo queda `rejected` y no se confirma.
5. Comprobar que la vista previa web no promete una comparación con el manifiesto que no recibió.
6. Importar en el almacenamiento temporal y confirmar.
7. Contrastar en SQLite los totales por estado y por severidad.
8. Consultar las distribuciones de indicadores: 129 con explotabilidad positiva y 533 con
   explotabilidad indeterminada; 8 con malware positivo y 654 con malware indeterminado; 8 con ambos
   positivos. Son distribuciones independientes y referencias de inspección; si la regla produce otro
   valor, reportar la diferencia y no forzar el número.
9. Comprobar que no se copió el CSV al repositorio, logs, fixtures ni LangSmith.
10. Comprobar que un error de integridad o un manifiesto inválido/discrepante no se puede eludir con
    una aceptación parcial: no existe tal control.
11. Registrar el resultado como **ejecutada y aprobada**, **ejecutada y fallida** o **no ejecutada con
    motivo**. Un `skip` no acredita la aceptación ni permite declarar terminado el incremento.

## 10. Privacidad y trazas

- La importación no produce llamadas externas.
- Las pruebas usan señuelos sintéticos y payloads capturados: preguntas con activos, memoria/historial,
  argumentos y resultados de herramienta, prompts/respuestas, callbacks, nombres de archivo, logs y
  errores. No se usan datos reales para probar una posible filtración.
- Los payloads externos no contienen filas, IP, activos, títulos, resultados, indicadores ni nombres
  de archivo reales.
- Los logs solo pueden contener IDs, códigos, conteos y versiones de política.
- El prompt del modelo local puede contener activos/títulos; la inferencia es local y la traza externa
  solo recibe metadatos acotados.
- La UI escapa el contenido del CSV; `Results` no se renderiza completo ni se envía al modelo.

## 11. Comprobaciones automatizadas

```bash
make check
make test-integration
```

La suite de integración incluye SQLite temporal. La aceptación local real es una comprobación
separada: si los archivos autorizados no existen, se registra como no ejecutada, no como aprobada.
No debe versionar ni imprimir filas reales.

Además:

- la evidencia de ejecución conserva snapshot, filtros y totales históricos; el detalle recalculado
  se etiqueta «Consulta actual» y no sustituye el histórico;
- los registros importados no crean `Document`/`DocumentChunk`, no se indexan en Chroma y no se
  convierten en citas;
- las posibles repeticiones conservan grupos, filas adicionales y todas las filas válidas;
- el manifiesto sintético se compara por hash, bytes, filas, columnas y conteos, con estados
  `absent`, `matched`, `mismatch` e `invalid`;
- los estados vacíos distinguen «sin registros» de «sin importaciones confirmadas»;
- el archivo vacío queda `rejected` con `empty_file` y no produce snapshot;
- los CVE aceptados cubren longitudes de 4–7 dígitos;
- explotabilidad y malware se reportan como distribuciones independientes, no como grupos
  excluyentes.

Playwright:

- escritorio 1440, móvil 390 y 320;
- formulario, preview, confirmación, historial, selector, tabla y estados vacíos;
- indicador de carga y un solo POST ante doble clic;
- menú móvil, foco inicial/restauración, Escape, navegación por teclado, etiquetas accesibles y
  recursos locales;
- consola sin errores y sin recursos faltantes.
