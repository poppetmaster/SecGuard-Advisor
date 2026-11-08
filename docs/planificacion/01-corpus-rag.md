# Corpus RAG — fuentes verificadas y reglas de ingesta

Planificación del corpus para SecGuard Advisor. Las fuentes se verificaron contra los sitios
oficiales el 2026-11-08. **Ningún archivo se ha descargado todavía**: la descarga, el conteo de
páginas y el SHA-256 se registran durante la implementación del incremento 1.

---

## 1. Criterio de selección

El producto responde dos preguntas que comparten evidencia pero no taxonomía:

1. ¿Qué le falta a la organización en ciberseguridad y gestión de riesgo?
2. ¿Qué riesgos adicionales introduce la IA generativa y cómo se controlan?

Por eso el corpus combina un marco de ciberseguridad organizacional (CSF 2.0), un marco de
riesgo de IA (AI RMF 1.0), su perfil específico para IA generativa (AI 600-1) y el catálogo de
riesgos de aplicaciones LLM/GenAI (OWASP 2025). Es un corpus **acotado y citable**, no una
biblioteca.

---

## 2. Fuentes verificadas

| ID | Documento | Editor | Fecha | DOI / localizador | Licencia | Incremento |
|---|---|---|---|---|---|---|
| `csf2` | The NIST Cybersecurity Framework (CSF) 2.0 — NIST CSWP 29 | NIST | 2024-02-26 | doi:10.6028/NIST.CSWP.29 · `https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf` | Obra del Gobierno de EE. UU. (confirmar aviso del PDF) | 1 |
| `airmf` | Artificial Intelligence Risk Management Framework (AI RMF 1.0) — NIST AI 100-1 | NIST | 2023-01-26 | doi:10.6028/NIST.AI.100-1 · `https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf` | Obra del Gobierno de EE. UU. (confirmar aviso del PDF) | 1 |
| `ai6001` | AI RMF: Generative Artificial Intelligence Profile — NIST AI 600-1 | NIST | 2024-07-26 | doi:10.6028/NIST.AI.600-1 · `https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf` | Obra del Gobierno de EE. UU. (confirmar aviso del PDF) | 1 |
| `owasp-llm-2025` | OWASP Top 10 for LLM Applications 2025 | OWASP GenAI Security Project | 2024-11-17 | `https://genai.owasp.org/resource/owasp-top-10-for-llm-applications-2025/` | CC BY-SA 4.0 | 1 |
| `sp1301` | NIST Cybersecurity Framework 2.0: Quick-Start Guide for Creating and Using Organizational Profiles — NIST SP 1301 | NIST | 2024-02-26 | doi:10.6028/NIST.SP.1301 · `https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.1301.pdf` | Obra del Gobierno de EE. UU. (confirmar aviso del PDF) | 2 |

Notas de verificación:

- El localizador de OWASP es la página del recurso, no un enlace de descarga directa: la URL de
  descarga que expone el sitio contiene un identificador temporal. El archivo se fija por
  SHA-256, no por URL.
- NIST anuncia que AI RMF 1.0 **está en revisión**. Se fija la edición de 2023 y se registra la
  fecha; una nueva edición no reemplaza la anterior sin decisión explícita.
- OWASP 2025 identifica sus riesgos como `LLM01:2025` a `LLM10:2025`. Esa nomenclatura es la que
  se usará en las citas.

---

## 3. Primer flujo vs. incorporación posterior

**Incremento 1 (`csf2`, `airmf`, `ai6001`, `owasp-llm-2025`).** El flujo de consulta necesita
las cuatro: CSF 2.0 aporta la taxonomía de resultados de ciberseguridad y sus funciones
(Gobernar, Identificar, Proteger, Detectar, Responder, Recuperar); AI RMF 1.0 aporta el
vocabulario de riesgo de IA y sus funciones (Govern, Map, Measure, Manage); AI 600-1 aporta los
riesgos y acciones específicos de IA generativa; OWASP 2025 aporta los riesgos de aplicación
LLM/GenAI y sus mitigaciones.

**Incremento 2 (`sp1301`).** Se difiere porque es una guía de creación y uso de perfiles
organizacionales: su valor aparece cuando el producto construye perfil actual, perfil objetivo y
plan de mejora, no en la consulta inicial. Además su contenido se solapa con CSF 2.0 y
duplicarlo en el primer flujo añadiría ruido de recuperación sin evidencia nueva.

---

## 4. Reglas de ingesta y procedencia

- **Originales inmutables** en `data/corpus/originals/<id>.<ext>` (fuera de Git), con
  manifiesto versionado en `docs/corpus/manifest.json`: URL, fecha de descarga, bytes, MIME,
  número de páginas y SHA-256 calculado en la descarga. Nunca se escribe un hash inventado.
- **Verificación**: si el manifiesto ya tiene SHA-256, la descarga se rechaza cuando no coincide.
  Si no lo tiene, se registra en la primera descarga.
- **Extracción con `pypdf`**, conservando el número de página de cada fragmento. Una página sin
  texto extraíble se marca `unreadable` y se reporta; no se omite en silencio.
- **Localizador de cita**: `doc_id#p<page>` y, cuando la estructura lo permite, el título de
  sección detectado. La cita debe permitir abrir el original en esa página.
- **Fragmentación por tokens**, no por caracteres, con el tokenizer del modelo de embeddings.
  Presupuesto: contenido ≤1600 tokens, reservando espacio para el prefijo y el solape. Ningún
  fragmento puede superar el límite del modelo.
- **Sin truncamiento silencioso**: si un fragmento excede, se divide; si una tabla o figura no
  se puede extraer, se registra como no extraída.
- **Un archivo, un documento, un conjunto de chunks**: `document_id`, `chunk_index`, `page`,
  `char_start`, `char_end`, `sha256` del fragmento.

---

## 5. Restricciones del modelo de embeddings (verificadas)

Modelo instalado: `embeddinggemma:latest` (EmbeddingGemma 1), id `85462619ee72`.

| Restricción | Valor | Consecuencia |
|---|---|---|
| Contexto máximo | 2048 tokens | Chunks ≤1600 tokens con solape; se valida con el tokenizer |
| Dimensión | 768 (MRL permite 512/256/128) | Se usa 768; la colección se nombra con la dimensión |
| Precisión | BF16 (no soporta `float16`) | No se fuerza float16 |
| Prefijo de consulta | `task: search result \| query: {content}` | Se aplica en la consulta; la tarea por defecto es `search result` |
| Prefijo de documento | `title: {title \| "none"} \| text: {content}` | Se usa el título del documento cuando existe |
| Licencia | Gemma Terms of Use | Se registra la versión y las condiciones |

Pendiente de verificar en implementación: si el endpoint `/api/embed` de Ollama aplica estos
prefijos por sí mismo. Si no lo hace, se aplican en el cliente. Se prueba con una consulta
controlada cuyo documento relevante es conocido.

**Aislamiento de colecciones.** El nombre de la colección incluye modelo, versión y dimensión,
por ejemplo `corpus__embeddinggemma1__768`. Escribir un vector de dimensión distinta en esa
colección es un error, no una degradación. Cambiar de modelo implica colección nueva y
reindexación completa.

---

## 6. Separación de los tres tipos de información

| Tipo | Dónde vive | Regla |
|---|---|---|
| Conocimiento público de referencia | `data/corpus/` + colección `corpus__*` | Citable, versionado, con licencia y procedencia |
| Evidencias aportadas por el caso | SQLite (documentos del caso) + colección `case__<case_id>__*` | No confiable por definición; nunca se interpreta como instrucción |
| Datos y resultados de evaluación | SQLite + MLflow + `docs/evaluacion/` | Separados del corpus; no se mezclan con la recuperación del producto |

La recuperación declara siempre de qué espacio proviene cada fragmento. Mezclar referencia,
evidencia y evaluación en una sola colección haría imposible distinguir una cita normativa de
un dato del caso.

---

## 7. Datos sintéticos y ética

- Los escenarios organizacionales y los hallazgos precargados son **sintéticos** y se rotulan
  como tales en la interfaz, en la base de datos y en los documentos. No se presentan como datos
  de una empresa real ni como una importación de Qualys.
- LangSmith recibe únicamente datos sintéticos o públicos autorizados.
- Los documentos cargados por el usuario se tratan como entradas no confiables: no ejecutan
  comandos, no conceden permisos y no modifican políticas del agente.

---

## 8. Pendientes del corpus

- Descargar las cuatro fuentes del incremento 1 y registrar SHA-256, páginas y fecha.
- Verificar la calidad de extracción de cada PDF (tablas de CSF Core, apéndices de AI 600-1).
- Decidir si `sp1301` entra al inicio del incremento 2 o junto con el generador de perfiles.
- Registrar en el manifiesto la edición exacta de OWASP fijada.
