# Research: Migración del índice documental a Qdrant

**Fecha**: 2026-11-11  
**Alcance**: decisiones de investigación para 004. No implementa ni instala nada.

## Decisiones

### D-01 — Versiones fijadas de Qdrant

**Decisión:** servidor `qdrant/qdrant:v1.20.0` y cliente `qdrant-client==1.20.0`.

**Evidencia:** Qdrant publicó `v1.20.0` como última versión el 2026-10-22; el cliente Python
`1.20.0` se publicó el mismo día y declara soporte para Python 3.10–3.15
([release del servidor](https://github.com/qdrant/qdrant/releases/tag/v1.20.0),
[release del cliente](https://github.com/qdrant/qdrant-client/releases/tag/v1.20.0),
[metadatos PyPI](https://pypi.org/project/qdrant-client/1.20.0/)).

**Compatibilidad:** el cliente considera compatibles versiones con la misma major y diferencia de
minor ≤ 1. Se fijan ambas en 1.20.0 para evitar ambigüedad. La comprobación real se hará contra
`/readyz` y la versión reportada por el servidor.

**Alternativas descartadas:** `latest` o rangos flotantes; no son reproducibles.

### D-02 — Servidor local persistente con Docker Compose

**Decisión:** Qdrant server local, imagen fijada, puertos solo en `127.0.0.1`, volumen persistente
`./storage/qdrant`.

**Evidencia:** la guía oficial de Qdrant local usa `qdrant/qdrant`, publica 6333/6334 y monta
`/qdrant/storage`
([Local Quickstart](https://qdrant.tech/documentation/quickstart/)). El almacenamiento usa WAL y
persistencia en disco
([Storage](https://qdrant.tech/documentation/manage-data/storage/)).

**Alternativas descartadas:** Qdrant Cloud (fuera del alcance local); modo embebido como backend
de producto (se reserva para pruebas; no sustituye la aceptación contra servidor).

### D-03 — Colecciones por alcance, alias y generaciones

**Decisión:** una colección física por alcance y generación; un alias activo por alcance. La
consulta usa el alias; la reconstrucción crea una generación nueva, valida y cambia el alias.

**Razón:** evita que una reconstrucción parcial se presente como índice listo sin introducir una
tabla de estado ni un segundo backend. Qdrant soporta aliases de colección y `update_collection_aliases`;
es una capacidad del propio motor. La generación anterior se conserva para recuperación.

**Alternativas descartadas:** escribir directamente sobre la colección activa (deja un índice
parcial visible); tabla SQLite de estado (persistencia adicional innecesaria); dos backends
(prohibido por la simplificación confirmada).

### D-04 — Correspondencia de identificadores

**Decisión:** ID de punto Qdrant = UUIDv5 determinista de `chunk_id` con namespace fijo de
SecGuard; payload `chunk_id` como identificador autoritativo. El texto y la procedencia se
resuelven desde SQLite.

**Razón:** Qdrant acepta IDs UUID o enteros; los `chunk_id` actuales son cadenas hex de 32
caracteres, no UUID canónicos. UUIDv5 preserva idempotencia y evita depender del formato del ID
interno. No se duplica el texto en Qdrant.

**Alternativas descartadas:** usar `chunk_id` crudo como ID (depende del parser UUID de Qdrant);
ID entero autoincremental (no idempotente entre reconstrucciones); texto completo en payload
(duplicación y riesgo de desactualización).

### D-05 — Payload e índices

**Decisión:** payload de metadatos con `chunk_id`, `document_id`, `version_id`, `origin`,
`source_id`, `page_start`, `page_end`, `section`, `locator`, `document_title`, `declared_version`,
`chunk_index`, `embedding_model`, `embedding_dim`. Índices de payload en `document_id`,
`version_id` y `origin`.

**Razón:** la aplicación ya resuelve el fragmento y la cita desde SQLite; el payload solo necesita
localizar y filtrar. Los índices de payload mejoran filtros por documento/versión/origen.

**Alternativas descartadas:** payload con texto completo; índices por cada campo sin uso medido.

### D-06 — Métrica y embeddings

**Decisión:** vector de 768 dimensiones, métrica `COSINE`, modelo local `embeddinggemma` actual.
No se cambia el modelo en 004.

**Razón:** coincide con la dimensionalidad y la similitud coseno actuales. Qdrant devuelve
similitud (mayor es mejor); no se reutiliza el `1 - distance` de Chroma sin recalibrar.

**Alternativas descartadas:** cambiar de modelo de embeddings en 004; mezclar dimensiones; copiar
el umbral 0.35 de Chroma.

### D-07 — Reconstrucción limpia

**Decisión:** comando explícito que lee SQLite, regenera embeddings locales, crea una generación
Qdrant nueva, valida y cambia el alias. No exporta vectores de Chroma.

**Razón:** los vectores no están persistidos en SQLite; no hay exportación autorizada. La
reconstrucción limpia es la ruta confirmada. La generación + alias evita un índice parcial activo.

**Alternativas descartadas:** migrar/exportar vectores Chroma; escritura dual; selección
permanente de backend; retorno a Chroma.

### D-08 — Umbral de recuperación

**Decisión:** calibrar con Qdrant sobre un conjunto reproducible de preguntas relevantes,
marginales y fuera de dominio; registrar score y elegir umbral. El valor 0.35 de Chroma es solo
referencia histórica, no una equivalencia.

**Razón:** la escala de similitud y la configuración de Qdrant deben comprobarse. No se inventan
métricas ni se declara equivalencia sin evidencia.

### D-09 — Evidencia sin tablas nuevas

**Decisión:** registrar `vector_backend=qdrant`, versión, alias y generación en
`RunStep.detail_json` del paso `retrieve`. La reconstrucción escribe un reporte JSON local.

**Razón:** no se crean tablas por costumbre. La evidencia de ejecución ya persiste detalles de
pasos; el reporte de reconstrucción es un artefacto operativo, no estado de negocio.

**Alternativas descartadas:** nueva tabla de índices (no necesaria); columnas nuevas sin migración
aditiva justificada.

### D-10 — Retirada de Chroma

**Decisión:** retirar `ChromaIndex`, `chroma_dir`, la fábrica y las dependencias
`langchain-chroma`/`chromadb` del código de producto. No borrar `storage/chroma` ni datos.

**Razón:** la simplificación confirmada elimina la migración, la comparación y el retorno. La
limpieza física de Chroma queda fuera de 004.

**Alternativas descartadas:** mantener una capa dual permanente; conservar Chroma como fallback;
borrar archivos Chroma en la aceptación.

## Versiones y compatibilidad verificadas

| Componente | Versión fijada | Verificación |
|---|---|---|
| Python | 3.14.6 | Proyecto y `qdrant-client 1.20.0` declaran soporte |
| Servidor Qdrant | `qdrant/qdrant:v1.20.0` | Release oficial 2026-10-22 |
| Cliente Qdrant | `qdrant-client==1.20.0` | PyPI 2026-10-22; `requires_python >=3.10`; clasificadores 3.14/3.15 |
| Embeddings | `embeddinggemma`, 768 dims, 2048 tokens | Configuración local actual; sin cambio en 004 |
| Docker Compose | Servicio local con volumen | Guía oficial de Qdrant local |

**No verificado aún:** disponibilidad del manifiesto Docker para la arquitectura arm64 del equipo,
latencia de reconstrucción, calidad de recuperación y umbral. Se verifican en implementación y
aceptación; no se inventan resultados.

## Riesgos de investigación

- Qdrant 1.20.0 es reciente; se fijan versiones exactas y se ejecutan pruebas de contrato.
- El re-embedding puede ser costoso; se medirá y se hará por lotes.
- El alias/generación agrega lógica; se prueba la atomicidad del cambio y la recuperación.
- La imagen Docker debe estar disponible para arm64; se verifica antes de la aceptación.
- La escala de score no es idéntica a Chroma; se calibra con Qdrant.
- Los acuerdos de Cristian/Ruben no constan; se registra la ratificación del responsable sin
  inventar aprobación del equipo.

## Fuentes

- Qdrant, *Local Quickstart*: <https://qdrant.tech/documentation/quickstart/>
- Qdrant, *Storage*: <https://qdrant.tech/documentation/manage-data/storage/>
- Qdrant, release v1.20.0: <https://github.com/qdrant/qdrant/releases/tag/v1.20.0>
- Qdrant Client, release v1.20.0: <https://github.com/qdrant/qdrant-client/releases/tag/v1.20.0>
- PyPI, `qdrant-client 1.20.0`: <https://pypi.org/project/qdrant-client/1.20.0/>
- Qdrant Client, local mode y snapshots:
  <https://github.com/qdrant/qdrant-client>
- Qdrant, aliases/collections: <https://qdrant.tech/documentation/manage-data/collections/>
- Qdrant, payload indexes: <https://qdrant.tech/documentation/manage-data/indexing/>

Consultadas el 2026-11-11. Las versiones y condiciones pueden cambiar; se reverifican en la
implementación y la aceptación.
