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
| `tests/fixtures/files/qualys_synthetic_invalid_rows.csv` | Severidad, fecha, QID o CVE inválidos |

No se usan filas del archivo real para crear estos fixtures.

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
   - prioridad conjunta: 2 filas; solo explotabilidad: 1; indeterminadas: 2;
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

## 8. Aislamiento y errores

1. Crear un segundo caso sin importaciones.
2. Abrir `Vulnerabilidades`: debe mostrar estado vacío y CTA, no datos del primer caso.
3. Abrir una URL de snapshot del primer caso bajo el segundo: debe responder 404.
4. Validar `qualys_synthetic_invalid_header.csv`: debe rechazar con columnas esperadas/detectadas y
   sin incorporar filas.
5. Validar `qualys_synthetic_invalid_rows.csv`: debe quedar `rejected`, mostrar filas inválidas con
   número y motivo y no ofrecer confirmación. No existe un control para «aceptar solo filas válidas»
   ni se crea un snapshot parcial.
6. Cancelar una vista previa `staged` o `rejected`: la instantánea vigente no cambia. Volver a la URL
   debe informar cancelación/expiración y ofrecer cargar de nuevo.

## 9. Aceptación local con el archivo real

Esta prueba es opcional y local; no se ejecuta en CI ni se versiona el archivo.

```bash
export SECGUARD_STORAGE_DIR=/ruta/temporal/fuera/del/repositorio
uv run alembic upgrade head
```

1. Verificar que el CSV autorizado tiene SHA-256
   `f55ab562f2fe5a41654f5c256a0ba9a281b446ebbe608514e06d0100af934e34` y 1.355.926 bytes.
2. Verificar contra el manifiesto: 662 filas, 41 columnas, `Active` 631, `New` 10, `Re-Opened` 21,
   `Fixed` 0. Si el hash o las cantidades no coinciden, el archivo queda `rejected` y no se confirma.
3. Importar en el almacenamiento temporal y confirmar.
4. Contrastar en SQLite los totales por estado y por severidad.
5. Consultar la regla de indicadores: 129 con explotabilidad positiva, 8 con malware positivo, 8 con
   ambos (7 `Active`, 1 `New`), 121 con solo explotabilidad, 0 con solo malware. Son referencias de
   inspección; si la regla produce otro valor, reportar la diferencia y no forzar el número.
6. Comprobar que no se copió el CSV al repositorio, logs, fixtures ni LangSmith.
7. Comprobar que un error de integridad no se puede eludir con una aceptación parcial: no existe tal
   control.

## 10. Privacidad y trazas

- La importación no produce llamadas externas.
- Las pruebas de traza deben confirmar que los payloads enviados a LangSmith no contienen filas, IP,
  activos, títulos, resultados ni indicadores.
- Los logs solo pueden contener IDs, códigos, conteos y versiones de política.
- El prompt del modelo local puede contener activos/títulos; la inferencia es local y la traza
  externa solo recibe metadatos acotados.

## 11. Comprobaciones automatizadas

```bash
make check
make test-integration
```

La suite de integración incluye SQLite temporal y, si los archivos autorizados existen, la aceptación
local real. No debe versionar ni imprimir filas reales.

Playwright:

- escritorio 1440, móvil 390 y 320;
- formulario, preview, confirmación, historial, selector, tabla y estados vacíos;
- indicador de carga y un solo POST ante doble clic;
- menú móvil, foco y recursos locales;
- consola sin errores y sin recursos faltantes.
