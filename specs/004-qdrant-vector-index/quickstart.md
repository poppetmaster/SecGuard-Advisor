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
export SECGUARD_QDRANT_URL="http://127.0.0.1:6333"
export SECGUARD_QDRANT_TIMEOUT_SECONDS="5"
# Embeddings locales actuales
export OLLAMA_EMBEDDING_MODEL="embeddinggemma"
```

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

## 5. Pruebas

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

## 6. Verificación funcional mínima

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
12. ejecutar la regresión de 001 y 002.

## 7. Reconstrucción de una instancia existente

No ejecutar directamente sobre la instancia del usuario. Primero:

```bash
cp -R storage storage-backup-$(date +%Y%m%d)
export SECGUARD_STORAGE_DIR="$PWD/storage-copy"
cp -R storage-backup-YYYYMMDD/ "$SECGUARD_STORAGE_DIR"
uv run python scripts/rebuild_qdrant.py --storage "$SECGUARD_STORAGE_DIR"
```

La copia se hace fuera de Git y se conserva hasta validar. La limpieza de Chroma no forma parte de
004.

## 8. Fallos esperados

| Situación | Resultado |
|---|---|
| Qdrant no responde | Error explícito; no fallback a Chroma |
| Versión incompatible | Error antes de escribir; no se cambia el alias |
| Dimensión/modelo incompatible | Error; no se mezcla |
| Reconstrucción interrumpida | Generación no activa; reintento seguro |
| Alias ausente | Error de índice no disponible |
| Reinicio de Qdrant | El volumen persiste; el alias sigue disponible |

## 9. Detener

```bash
docker compose -f compose.qdrant.yml down
```

Conserva el volumen. No borres `storage/qdrant` ni `storage/chroma` sin autorización y copia.
