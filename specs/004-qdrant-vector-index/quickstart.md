# Quickstart: Qdrant local para 004

**Estado:** comandos de referencia para implementación y aceptación. No se ejecutaron en esta fase
documental. No migran Chroma, no borran datos y no instalan nada por sí solos.

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

El marcador `storage/qdrant/instances/<instance_id>.json` guarda el ID y un hash del storage. Si no
coincide, la aplicación falla con `instance_namespace_mismatch` y no escribe ni cambia alias. No se
reutiliza el ID de presentación en pruebas.

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
7. reportar estado, faltantes y errores.

No se usa `storage/chroma` ni se borran sus archivos.

## 4. Comandos de mantenimiento previstos

```bash
make qdrant-up        # docker compose up -d
make qdrant-down      # docker compose down (conserva volumen)
make qdrant-health    # /readyz + versión
make qdrant-rebuild   # reconstrucción limpia
```

No se crea `make qdrant-clean` en 004: la limpieza de generaciones antiguas requiere una decisión
separada y no debe borrar colecciones ajenas.

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

La aplicación y el comando de reconstrucción comparten
`storage/qdrant/locks/<instance_id>.lock` mediante un lock de archivo exclusivo. No es un lock en
memoria.

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
    públicos.

## 10. Reconstrucción de una instancia existente

No ejecutar directamente sobre la instancia del usuario. Primero:

```bash
cp -R storage storage-backup-$(date +%Y%m%d)
export SECGUARD_STORAGE_DIR="$PWD/storage-copy"
cp -R storage-backup-YYYYMMDD/ "$SECGUARD_STORAGE_DIR"
uv run python scripts/rebuild_qdrant.py --storage "$SECGUARD_STORAGE_DIR"
```

La copia se hace fuera de Git y se conserva hasta validar. La limpieza de Chroma no forma parte de
004.

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
