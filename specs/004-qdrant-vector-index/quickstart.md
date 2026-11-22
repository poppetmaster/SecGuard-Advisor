# Quickstart: Qdrant local para 004

**Estado:** Qdrant es el backend documental implementado y aceptado localmente en el Corte 6. Estos
comandos son los vigentes para arranque, reconstrucción, consulta de estado y evaluación. No migran
Chroma, no borran datos y no instalan nada por sí solos.

## Versiones fijadas

- Servidor: `qdrant/qdrant:v1.20.0`
- Cliente: `qdrant-client==1.20.0`
- Python: 3.14.6
- Embeddings: `embeddinggemma` local, 768 dimensiones
- Métrica: `COSINE`

## 1. Servicio local

```bash
cd /ruta/a/secguard-advisor
docker compose -f compose.qdrant.yml up -d
curl -fsS http://127.0.0.1:6333/readyz
```

El compose de referencia expone solo loopback y monta `./storage/qdrant`:

```yaml
services:
  qdrant:
    image: qdrant/qdrant:v1.20.0
    ports:
      - "127.0.0.1:6333:6333"
      - "127.0.0.1:6334:6334"
    volumes:
      - ./storage/qdrant:/qdrant/storage
    restart: unless-stopped
```

No se expone a la red. No se usa Qdrant Cloud.

## 2. Configuración

```bash
export SECGUARD_INSTANCE_ID="local-dev"          # estable, opaco, distinto por instancia
export SECGUARD_QDRANT_URL="http://127.0.0.1:6333"
export SECGUARD_QDRANT_TIMEOUT_SECONDS="5"
# Embeddings locales actuales
export OLLAMA_EMBEDDING_MODEL="embeddinggemma"
```

`SECGUARD_INSTANCE_ID`:

- se conserva entre reinicios; no se genera al arrancar;
- se aplica a colecciones, alias, generaciones, reportes y locks;
- no contiene rutas privadas;
- debe ser distinto para almacenamiento habitual, presentación y pruebas.

El marcador `<SECGUARD_STORAGE_DIR>/qdrant-control/instances/<instance_id>.json` guarda el ID y un
fingerprint de la ruta canónica del almacenamiento combinada con el ID (no el contenido ni el hash de
SQLite). Si no coincide, la aplicación falla con `instance_namespace_mismatch` y no escribe ni cambia
alias. Un servidor que ya contiene otras instancias no impide registrar una instancia nueva; si falta
el marcador pero ya existen colecciones o alias de ese ID, la aplicación falla cerrada en lugar de
adoptar el namespace. No se reutiliza el ID de presentación en pruebas.

El volumen `./storage/qdrant` pertenece solo al servidor Qdrant. Los marcadores, locks y reportes viven
en `qdrant-control/`, fuera de ese volumen.

No existe selección `chroma|qdrant`: Qdrant es el único backend documental. No hay fallback a
Chroma.

## 3. Reconstrucción en almacenamiento separado

Primero validar con datos públicos/ficticios y una instancia separada:

```bash
export SECGUARD_STORAGE_DIR="$PWD/storage/qdrant-acceptance"
mkdir -p "$SECGUARD_STORAGE_DIR"
uv run alembic upgrade head
uv run python scripts/rebuild_qdrant.py --storage "$SECGUARD_STORAGE_DIR"
```

El comando debe:

1. comprobar `/readyz` y versión 1.20.0;
2. leer SQLite y seleccionar versiones vigentes disponibles;
3. regenerar embeddings locales;
4. crear una generación Qdrant nueva;
5. validar `chunk_id`, conteos y payloads;
6. cambiar el alias activo solo si todo coincide;
7. reportar uno de los cinco estados observables, los faltantes y los errores.

No se usa `storage/chroma` ni se borran sus archivos.

## 4. Comandos de mantenimiento previstos

```bash
make qdrant-up        # docker compose up -d
make qdrant-down      # docker compose down (conserva volumen)
make qdrant-health    # /readyz + versión
make qdrant-rebuild   # reconstrucción limpia
```

Todos los targets llevan comentario `##` para aparecer en `make help`. No se crea `make qdrant-clean`
en 004: la limpieza de generaciones antiguas requiere una decisión separada y no debe borrar
colecciones ajenas.

## 4.1 Estado de la reconstrucción

El comando de reconstrucción y su reporte son la interfaz operativa de estado y avance. No hay pantalla
web de administración en 004.

| Estado | Cómo se observa |
|---|---|
| `not_started` | No existe `qdrant-control/reports/<instance_id>/latest.json` y el lock no está tomado por una reconstrucción. |
| `in_progress` | El lock está tomado por un proceso vivo y su registro de propietario declara `operation=rebuild`. El `latest.json` previo describe el intento anterior. |
| `completed` | `latest.json` con `status: completed`. |
| `partial` | `latest.json` con `status: partial`; el reporte indica alcances y faltantes. |
| `failed` | `latest.json` con `status: failed`; el alias anterior sigue vigente. |

Si el lock lo posee una ingesta (`operation=ingestion`), hay ingesta activa y no reconstrucción en
curso: se muestra el último resultado terminal. Un lock activo no es éxito, la ausencia de reporte no
es fallo y un registro residual con el lock libre se ignora.

## 4.2 Consulta del estado sin reconstruir

```bash
uv run python scripts/rebuild_qdrant.py --status
```

Devuelve un objeto con `state`, el propietario del lock si está activo y el último resultado terminal:

| Situación | `state` |
|---|---|
| Sin estado registrado | `not_started`, con salida 0 y sin crear archivos |
| Ingesta en curso (lock con `operation=ingestion`) | `ingestion_in_progress` |
| Reconstrucción en curso (lock con `operation=rebuild`) | `rebuild_in_progress` |
| Último reporte terminal completado | `completed` |
| Último reporte terminal parcial | `partial` |
| Último reporte terminal fallido | `failed` |

La consulta no inicia reconstrucciones, no genera embeddings, no crea colecciones, no registra
instancias, no escribe archivos y no cambia aliases. Metadatos de propietario con el lock libre se
ignoran. No se añade un target de Makefile para esta consulta: el comando es el contrato. El resolvedor
único vive en `retrieval/status.py`.

Casos de error: salida 2, motivo en `stderr` y
`{"state": null, "last_terminal": null, "error": {"code": "...", "message": "..."}}`.

| Situación | `error.code` |
|---|---|
| Reporte terminal ilegible | `status_report_unreadable` |
| Configuración de instancia ausente o inválida | `instance_configuration_invalid` |
| Archivo de lock existente pero ilegible, o lock tomado con registro de propietario ausente o corrupto | `lock_unreadable` |

En los tres casos no se devuelve `not_started`, no se afirma que no existe una operación activa y no se
crea ni modifica ningún archivo. El código 2 por argumentos inválidos se distingue porque imprime el uso
y no emite ese JSON.

## 5. Primer documento de un caso nuevo

No se exige una reconstrucción completa por cada caso nuevo:

1. cargar el documento por la interfaz normal;
2. la ingesta persiste documento/versión/fragmentos y genera embeddings;
3. si el caso no tiene alias, crea la generación inicial;
4. valida los `chunk_id` en Qdrant;
5. publica el alias del caso y marca la versión disponible.

Si falla extracción, embedding o escritura en Qdrant, la versión queda no disponible y no se publica
alias nuevo. El reintento limpia por `version_id` y repite el flujo. Un documento posterior usa el
alias existente.

## 6. Alcance vacío e índice ausente

- Caso sin documentos privados: se consulta solo el corpus público; no es error.
- Caso con documentos esperados pero sin alias: `case_index_unavailable`; no se responde solo con
  público.
- Público con documentos esperados pero sin alias: `public_index_unavailable`; no se declara falta
  de evidencia.
- Público no configurado o vacío: se omite; el caso puede continuar.
- Qdrant caído: `qdrant_unavailable`; sin Chroma.

## 7. Lock entre procesos

La aplicación, la ingesta del corpus y el comando de reconstrucción comparten
`<SECGUARD_STORAGE_DIR>/qdrant-control/locks/<instance_id>.lock` mediante un lock de archivo
exclusivo. No es un lock en memoria. La primitiva vive en `retrieval/instance.py`.

Mientras posee el lock, el proceso registra `{operation, attempt_id, pid, started_at}` con
`operation` en `ingestion` o `rebuild`. La autoridad de actividad es el bloqueo real: si el lock puede
adquirirse, el registro es obsoleto y se ignora, también tras una terminación abrupta.

```bash
# Si hay ingesta, la reconstrucción falla con ingestion_in_progress.
make qdrant-rebuild
```

- La reconstrucción rechaza ingestas nuevas con `reconstruction_in_progress`.
- La ingesta rechaza una reconstrucción con `ingestion_in_progress`.
- Las consultas siguen usando el alias anterior.
- Si el proceso muere, el sistema operativo libera el lock; el alias no cambia.
- Dos instancias distintas no se bloquean entre sí.

## 8. Pruebas

Cada suite usa un `SECGUARD_INSTANCE_ID` propio y un storage separado:

```bash
export SECGUARD_INSTANCE_ID="test-local"   # distinto por suite e instancia
```

Unitarias con Qdrant local en modo embebido:

```bash
uv run pytest tests/unit -q
```

El modo embebido se limita a pruebas unitarias y de aceptación con dobles: no reproduce volumen
persistente, aliases entre procesos ni el lock de archivo compartido, y no sustituye la aceptación
contra el servidor. La calibración y la evaluación funcional se ejecutan con `--backend server`.

Contrato e integración con servidor Qdrant y embeddings locales:

```bash
uv run pytest -m integration -q
```

Aceptación funcional:

```bash
uv run pytest tests/acceptance -q
```

La aceptación real requiere Qdrant 1.20.0 y Ollama con `embeddinggemma`. No se declara éxito si el
servidor no está disponible.

## 9. Verificación funcional mínima

Con un caso ficticio y corpus público:

1. reconstruir Qdrant;
2. preguntar por un documento del corpus público y comprobar cita/procedencia;
3. preguntar por un documento del caso y comprobar cita/localizador;
4. comprobar que un documento privado de otro caso no aparece;
5. comprobar que una versión superada no aparece en búsquedas nuevas;
6. abrir una cita histórica y comprobar que resuelve desde SQLite;
7. repetir la reconstrucción y comprobar que no hay duplicados;
8. interrumpir una reconstrucción y comprobar que el alias no apunta a un índice parcial;
9. detener Qdrant y comprobar un error explícito, sin Chroma;
10. reiniciar Qdrant y comprobar persistencia;
11. comprobar que ningún registro Qualys aparece en el índice documental;
12. ejecutar la regresión de 001 y 002;
13. repetir con dos instancias (`test-a`, `test-b`) en el mismo servidor Qdrant, el mismo
    `case_id` y documentos distintos; comprobar que no comparten alias, documentos ni resultados
    públicos;
14. consultar con un alias de caso ausente y comprobar que devuelve `case_index_unavailable`, no una
    respuesta de «sin evidencia», y que no se ejecuta la generación documental;
15. insertar un punto de prueba sin fragmento en SQLite y comprobar que se reporta como discrepancia
    y nunca se resuelve como cita;
16. revisar `qdrant-control/reports/<instance_id>/latest.json` y comprobar que el estado observado
    coincide con uno de los cinco estados y que un lock activo no se interpreta como éxito;
17. con el lock tomado por una ingesta, comprobar que el reporte no anuncia reconstrucción en curso y
    que una reconstrucción falla con `ingestion_in_progress`;
18. matar abruptamente el proceso que posee el lock y comprobar que el bloqueo se libera, que el
    registro de propietario queda obsoleto y que el alias no cambia;
19. ejecutar la evaluación final con el umbral calibrado ya aplicado en `config.py`, sin recalibrar y
    con un conjunto distinto del de calibración.

## 10. Reconstrucción de una instancia existente

No ejecutar directamente sobre la instancia del usuario. Primero:

```bash
cp -R storage storage-backup-$(date +%Y%m%d)
export SECGUARD_STORAGE_DIR="$PWD/storage-copy"
cp -R storage-backup-YYYYMMDD/ "$SECGUARD_STORAGE_DIR"
# El marcador copiado pertenece a la ruta original: en la copia se usa una instancia nueva.
export SECGUARD_INSTANCE_ID="aceptacion-$(date +%Y%m%d)"
rm -f "$SECGUARD_STORAGE_DIR/qdrant-control/instances/"*.json
uv run python scripts/rebuild_qdrant.py --storage "$SECGUARD_STORAGE_DIR"
```

La copia se hace fuera de Git y se conserva hasta validar. La limpieza de Chroma no forma parte de
004.

**Por qué se elimina solo el marcador de la copia:** el fingerprint incluye la ruta canónica, así que
una copia en otra ruta no coincide y la aplicación falla cerrada con `instance_namespace_mismatch`.
El marcador es estado operativo de la aplicación, no dato de negocio: se retira únicamente de la copia
y nunca del original. La copia usa un `SECGUARD_INSTANCE_ID` propio y no adopta el namespace original.

## 11. Fallos esperados

| Situación | Resultado |
|---|---|
| Qdrant no responde | Error explícito; no fallback a Chroma |
| Versión incompatible | Error antes de escribir; no se cambia el alias |
| Dimensión/modelo incompatible | Error; no se mezcla |
| Reconstrucción interrumpida | Generación no activa; reintento seguro |
| Alias ausente | Error de índice no disponible |
| Reinicio de Qdrant | El volumen persiste; el alias sigue disponible |

## 12. Detener

```bash
docker compose -f compose.qdrant.yml down
```

Conserva el volumen. No borres `storage/qdrant` ni `storage/chroma` sin autorización y copia.

## 13. Calibración y evaluación del umbral

El umbral vigente es **0.5033**, calibrado con servidor Qdrant y `embeddinggemma`, y congelado antes
de la evaluación final. Los conjuntos de calibración y evaluación son distintos y están fijados en
`tests/fixtures/qdrant_eval.py`.

```bash
make qdrant-up
uv run python scripts/qdrant_threshold.py --mode calibrate --dataset cal2 --backend server \
  --output docs/evidencia/004-corte-6/calibration-iter2.json
uv run python scripts/qdrant_threshold.py --mode evaluate --dataset final --backend server \
  --threshold 0.5033 --output docs/evidencia/004-corte-6/evaluation-final.json
make qdrant-down
```

- `--backend server` usa el servidor configurado en `SECGUARD_QDRANT_URL`; `--backend embedded` usa un
  directorio temporal y se conserva solo para pruebas.
- `--dataset` selecciona `cal2` (calibración) o `final` (evaluación congelada).
- El reporte registra modalidad, versión de Qdrant, modelo, dimensión, métrica, `top_k`, umbral, fecha
  y hash SHA-256 del conjunto.
- En evaluación, el comando termina con código 1 si `outcome.passed` es falso, conservando el reporte.
- La prueba `tests/integration/test_qdrant_functional_eval.py` ejecuta la evaluación con el umbral de
  `config.py` y falla si algún criterio no se cumple.
