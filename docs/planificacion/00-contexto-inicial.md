# Contexto inicial — SecGuard Advisor

Documento de preparación previa a la constitución de Spec Kit. **No es normativo**: la
constitución es el único documento normativo. Aquí solo se registran hechos verificados,
insumos propuestos y decisiones pendientes.

- **Fecha:** 2026-11-08
- **Equipo:** Edwin Perez L., Cristian Quebrada, Ruben Dario Sabogal.
- **Mentor (referencia académica):** Cristian Urcuqui.
- **Estado:** preparación para `/speckit.constitution`.

---

## 1. Hechos verificados del entorno

Ejecutado en esta máquina (macOS, arm64). No se declara nada que no se haya corrido.

| Elemento | Evidencia observada |
|---|---|
| Python | 3.14.6 (`.python-version` y `.venv/bin/python -V`) |
| uv | 0.13.0 (Homebrew) |
| `uv sync` | Resolvió 133 paquetes, comprobó 131, sin error |
| Import de stack base | `fastapi 0.162.2`, `jinja2 3.1.6`, `langchain 1.4.9`, `langchain_ollama 1.1.0`, `langsmith 0.14.17`, `pypdf 7.0.0`, `sqlalchemy 2.1.8`, `uvicorn 0.54.0`, `alembic 1.20.1`, `httpx 0.28.1`, `pytest 9.2.0` — todos OK |
| Chroma | `chromadb 1.5.9` (dependencia transitiva de `langchain-chroma`) |
| Ollama | 0.34.4 |
| Modelo generativo candidato | `qwen3.5:9b` · id `56671c2ab938` · 9.0B · ctx 262144 · Q4_K_M · 6.6 GB en disco · *completion, vision, tools, thinking* (thinking por defecto activo) · Apache 2.0 |
| Modelo de embeddings | `embeddinggemma:latest` · id `85462619ee72` · 307.58M · ctx **2048** · embedding **768** · BF16 · Gemma Terms of Use |
| Modelo de comparación | `gemma4:latest` · id `dc35e8d9c606` · **7.5B** · ctx 131072 · Q4_K_M · *completion, vision, audio, tools, thinking* |
| Otro modelo presente | `nomic-embed-text-v2-moe:latest` (no seleccionado; no se mezclará en la misma colección) |
| LangSmith | Configurado contra `https://api.smith.langchain.com`; proyecto `secguard-advisor-dev` creado; traza real con estado `success` verificada |
| Git | Repositorio sin commits y sin remoto. Identidad local: `Edwin Perez L <edwinandperez@gmail.com>` |
| Stack del incremento 3 (resolución) | `scikit-learn 1.9.1`, `mlflow 3.18.0`, `prefect 3.9.2` resuelven para 3.14.6 (instalación real pendiente) |

Conclusión: **Python 3.14.6 no presenta incompatibilidad** con el stack declarado, ni con el
stack diferido del incremento 3. Se reverifica al instalar y al ejecutar.

### Consecuencias técnicas de los modelos

- `qwen3.5:9b` trae contexto de 262144 tokens. **No se usará el valor por defecto**: el KV
  cache crece con el contexto. Se fijará `num_ctx` explícito (orden de 8k–16k) y se medirá
  memoria real; el tamaño de descarga (6.6 GB) no es la memoria de ejecución.
- `thinking` viene activo por defecto. Hay que decidir por flujo si se desactiva (latencia,
  formato de respuesta) y probarlo con uso de herramientas.
- Un solo modelo generativo grande cargado a la vez. La comparación Qwen3.5 9B vs Gemma 4
  7.5B Q4_K_M es secuencial, no concurrente.
- EmbeddingGemma 1 (la instalada) tiene **2048 tokens de contexto** y **768 dimensiones**.
  Google ya publica EmbeddingGemma 2 (740M, 8192 tokens, Apache 2.0), pero **no está
  instalada**: se fija la v1 y se registra su versión; un cambio de modelo obliga a
  reconstruir el índice.

---

## 2. Referencias académicas leídas

### `01-Challenges_MCD_MIAA_2026_2.xlsx` — hoja «Retos disponibles»

La fila del proyecto (fila 3) solo trae: empresa (Universidad Icesi), título («Agente
Consultor en Ciberseguridad para IA»), mentor y correo (Cristian Urcuqui), semestre
(2026-03-02), programa (MCD/MIAA) y prerrequisitos técnicos y de negocio. Las columnas
**Descripción del alcance, Objetivos esperados, Datos disponibles, Enlace a datos, Criterios
de éxito y Herramientas sugeridas están vacías**, y la columna «Video descripción» contiene
el nombre del mentor.

Consecuencia: esta hoja **no aporta alcance normativo adicional**; el alcance vinculante es
el brief del producto. Cualquier requisito que se agregue debe salir de ahí o de una decisión
explícita del equipo, no de una inferencia sobre la hoja.

### `02-Rubrica_PAIII_2026.xlsx` — hoja «Rubrica»

Resultados y criterios que el proyecto debe evidenciar:

| Criterio | Qué exige | Evidencia que produciremos |
|---|---|---|
| R.6.1 Cr1 | Formulación del problema con contexto empresarial | Especificación + plantilla de caso con contexto organizacional |
| R.6.1 Cr2 | Justificar la elección del modelo comparando alternativas | Evaluación Qwen3.5 9B vs Gemma 4 7.5B (calidad, herramientas, fundamentación, memoria, latencia) |
| R.6.1 Cr3 | Integrar el modelo al caso | Producto funcionando por incrementos |
| R.6.1 Cr4 | Métricas e interpretación crítica | Métricas RAG, evaluación de clasificador, lectura de resultados |
| R.6.2 Cr5 | Seleccionar tareas automatizables con valor real | Ingesta, recuperación, priorización y generación de informe como tareas automatizadas |
| R.6.2 Cr6 | Demostrar eficiencia | Tiempos y latencias medidas antes/después, no estimadas |
| R.6.2 Cr7 | Mitigar riesgos éticos | Datos sintéticos rotulados, defensa ante prompt injection, sin datos de empresa real |
| R.6.2 Cr8 | Documentar de forma replicable | README, constitución, especificación, ADRs, demo reproducible |
| RA1 / RA2 | Comunicación escrita y oral | Informe y sustentación con estructura, canales, conclusiones y referencias |
| R.7.1 Cr1–Cr3 | Pipeline de datos | Validación y limpieza del CSV de Qualys, deduplicación, procedencia |
| R.7.2 Cr4–Cr6 | MLOps | MLflow, Prefect, versionado, reentrenamiento, promoción, rollback, Docker Compose, pruebas de carga |

La rúbrica **no es un checklist de entrega**: exige demostración. Documentar una capacidad no
la implementa.

---

## 3. Decisiones resueltas (técnicas, reversibles, con justificación)

| ID | Decisión | Justificación |
|---|---|---|
| D-01 | Constitución única: contenido real en `.specify/memory/constitution.md`; `CONSTITUTION.md` en la raíz es un **enlace simbólico** a ese archivo | Spec Kit escribe en `.specify/memory/constitution.md` y el estándar del proyecto exige `CONSTITUTION.md`. El enlace elimina la duplicación: un solo archivo editado, dos rutas de lectura. Se verificó que sobrescribir el destino preserva el enlace |
| D-02 | Idioma: documentación e interfaz en **español**; código, identificadores, nombres de tablas y comentarios en **inglés** | El producto y la rúbrica son en español; el código se mantiene legible para cualquier herramienta y estándar de Python |
| D-03 | Corpus del primer flujo: CSWP 29 (CSF 2.0), AI 100-1 (AI RMF 1.0), AI 600-1 (Perfil GenAI) y OWASP Top 10 LLM 2025. SP 1301 se incorpora en el incremento 2 | Ver `01-corpus-rag.md` |
| D-04 | Embeddings: EmbeddingGemma 1, 768 dimensiones, 2048 tokens de contexto. Chunks objetivo ≤1600 tokens con solape, prefijos de tarea de la tarjeta del modelo | Límite físico del modelo instalado; superarlo trunca en silencio |
| D-05 | Chroma es **derivado y reconstruible**. SQLite es la fuente de verdad de documentos, chunks y metadatos | Permite cambiar de modelo de embeddings o reindexar sin perder procedencia |
| D-06 | Assets de UI (Tailwind CSS, Flowbite, HTMX) **servidos localmente y versionados**, sin CDN | Funcionamiento offline y demo reproducible |
| D-07 | Sin autenticación en el incremento 1 (uso local mono-usuario), pero el **alcance por caso se impone en código** antes de tocar SQLite, Chroma o memoria | La seguridad del alcance no depende de que exista login; es una regla de servidor |
| D-08 | Pruebas de integración ejecutan Ollama, embeddings, recuperación y herramientas reales; los mocks solo aparecen en pruebas unitarias identificadas | Un mock no acredita una demo |
| D-09 | Los originales del corpus se conservan fuera de Git (`data/corpus/originals/`), con manifiesto versionado, URL, fecha de descarga y SHA-256 calculado en la descarga | Evita inflar el repositorio sin perder procedencia ni reproducibilidad |

---

## 4. Decisiones abiertas

No se inventa ninguna. Cada una bloquea un incremento concreto, no el trabajo actual.

| ID | Decisión | Por qué importa | Bloquea | Responsable |
|---|---|---|---|---|
| A-01 | Política P1–P4: significado, condiciones, excepciones, datos mínimos y ejemplos | Sin ella no hay etiquetas legítimas ni clasificador defendible | Incremento 3 (entrenamiento) | Equipo + mentor |
| A-02 | Formato CSV de Qualys a soportar (reporte y columnas exactas) | El adaptador no puede prometer «todos los reportes» | Incremento 2 | Equipo |
| A-03 | **Resuelta 2026-11-08:** LangSmith parametrizado con endpoint, proyecto `secguard-advisor-dev` y traza real verificada | Deja de bloquear la evidencia de observabilidad | — | Edwin |
| A-04 | Destino GitHub (owner/repo) y autorización de publicación | Badges de CI verificables y plantillas de gobernanza requieren repo real | Publicación y badges | Equipo |
| A-05 | Generador definitivo tras la comparación | Cambia configuración por defecto, no la arquitectura | Cierre del incremento 1 | Equipo |
| A-06 | Presupuesto aprobado para DeepSeek (proveedor educativo opcional) | Sin presupuesto no se activan llamadas pagadas | Proveedor opcional | Equipo |
| A-07 | Identidad Git de Cristian y Ruben para sus commits | No se modifica configuración global ni se inventan correos | Commits de cada autor | Cada integrante |

---

## 5. Insumos para la constitución

Propuesta de principios. Cada uno es verificable y tiene consecuencia práctica.

**I. Alcance por caso impuesto en código.** Toda consulta a SQLite, Chroma o memoria aplica
el `case_id` resuelto por el servidor. Ningún argumento del modelo concede permisos.

**II. Evidencia antes que afirmación.** Toda respuesta normativa cita documento, página o
sección. Se distingue referencia existente de afirmación respaldada. La información faltante
se declara como faltante y nunca se convierte en riesgo bajo ni en cumplimiento.

**III. Supervisión humana no delegable.** El agente no aprueba informes, no adjudica
prioridades y no ejecuta remediaciones. Aprobar el texto de un informe no confirma las
prioridades de sus hallazgos.

**IV. Procedencia y reproducibilidad del conocimiento.** Originales conservados, referencias
localizables, sin truncamiento silencioso, sin mezclar vectores de modelos distintos, modelos
y versiones registrados, índice reconstruible.

**V. Integración real por encima de mocks.** Las pruebas de integración ejecutan Ollama,
embeddings, recuperación y herramientas. Los mocks se limitan a pruebas unitarias
identificadas.

**VI. Local primero y costo controlado.** Inferencia local por defecto. Un proveedor externo
se selecciona explícitamente, sin fallback automático, con saldo reservado antes de cada
llamada y sin claves en logs ni trazas.

**VII. Simplicidad operativa.** Monolito modular con responsabilidades separadas. Sin
microservicios ni infraestructura distribuida en el alcance inicial. SQLite + Chroma
persistente y eventos operativos mínimos.

**VIII. Calidad y trazabilidad verificables.** `uv`, Ruff, pre-commit, pytest y CI. Nada se
declara exitoso sin haberse ejecutado. Datos sintéticos rotulados como sintéticos.

Secciones complementarias: stack técnico fijado; flujo de trabajo y puertas de calidad
(Conventional Commits, PR con verificación de constitución); seguridad y tratamiento de datos
(documentos no confiables, aprobación humana, LangSmith solo con datos sintéticos o públicos
autorizados); gobernanza (constitución única, versionado semántico, procedimiento de enmienda).

---

## 6. Incrementos y evidencia de aceptación

**Incremento 1 — consulta funcional.** Evidencia: caso creado con contexto; PDF/Markdown
cargado; recuperación con procedencia; respuesta con citas verificables y evidencia visible;
conversación con memoria persistente; hallazgos sintéticos consultados por herramienta
controlada; abstención ante información faltante; ejecución registrada en SQLite y traza real
en LangSmith cuando exista configuración.

**Incremento 2 — importación y revisión humana.** Evidencia: CSV de Qualys validado (tipos,
obligatorios, rangos, fechas, duplicados, procedencia); severidad, CVSS, QID y CVE separados;
tabla con filtros y detalle con prioridad sugerida, política y versión, evidencias y datos
faltantes; formulario de revisión con decisión, P1–P4 y justificación; autor, fecha, contexto y
versión registrados.

**Incremento 3 — clasificación, aprendizaje y operación.** Evidencia: política P1–P4 pactada;
clasificador scikit-learn comparado con regla de severidad y con la política; separación
entrenamiento/validación/regresión/prueba final; pantalla administrativa de etiquetas,
entrenamiento, versiones, métricas, activación y rollback; MLflow con backend SQLite y
artefactos locales; flujos Prefect demostrados; exportación, cola, cancelación, expiración,
recuperación tras reinicio, Docker Compose y pruebas de carga.

---

## 7. Riesgos conocidos

- **AI RMF 1.0 está en revisión** según NIST. Se fija la edición 2023 y se registra; no se
  sustituye en silencio.
- **OWASP 2025** se publicó el 2024-11-17 y su contenido está bajo CC BY-SA 4.0: se cita y no
  se relicencia.
- **EmbeddingGemma 1 vs 2**: la instalada es la 1 (2K tokens). La 2 existe upstream y no está
  instalada; migrar implica reindexar.
- **`thinking` activo por defecto** en Qwen3.5 y Gemma 4: afecta latencia y formato de
  herramientas; se prueba explícitamente.
- **Memoria de ejecución**: dos modelos grandes no se cargan a la vez.
- **Prompt injection** en documentos de caso: se tratan como datos, nunca como instrucciones.
- **Ecosistema Python 3.14**: el stack resuelve hoy; se reverifica en cada instalación real.

---

## 8. Siguiente paso

`/speckit.constitution` con estos insumos. La constitución se escribe en
`.specify/memory/constitution.md` y queda visible en `CONSTITUTION.md`.
