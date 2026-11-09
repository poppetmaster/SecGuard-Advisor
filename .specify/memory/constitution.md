<!--
Sync Impact Report
==================
Versión: 1.0.4 → 1.0.5
Tipo de cambio: PATCH — registro de una decisión de parámetros, sin cambios de principios
Principios modificados: ninguno
Secciones modificadas:
  - Registro de decisiones: Node unificado en 26.11.1 para local y CI
Secciones añadidas: ninguna
Secciones eliminadas: ninguna
Plantillas dependientes: sin cambios; leen esta constitución en tiempo de ejecución
TODOs diferidos: política P1–P4, formato CSV de Qualys, generador definitivo, destino
  GitHub y presupuesto de DeepSeek. Se registran como pendientes, no como decisiones
  tomadas.
Este informe es material temporal de revisión y DEBE eliminarse antes del commit de la
enmienda.
-->

# SecGuard Advisor Constitution

## Core Principles

### I. Propósito y alcance

SecGuard Advisor es un agente consultor **defensivo** para responsables de TI y seguridad.
Analiza documentación, contexto organizacional y hallazgos técnicos; identifica brechas; y
prepara recomendaciones y planes de mejora respaldados por evidencia. Es configurable por
contexto organizacional.

- El producto DEBE producir recomendaciones sujetas a revisión humana, con evidencia
  rastreable y límites declarados.
- El producto NO DEBE ejecutar remediaciones, modificar sistemas, aprobar informes ni
  adjudicar prioridades por cuenta propia.
- El producto NO DEBE certificar cumplimiento ni presentarse como auditor o certificador.
- El producto NO DEBE incluir capacidades ofensivas ni explotación.
- Los escenarios organizacionales y hallazgos educativos sintéticos DEBEN identificarse como
  sintéticos en interfaz, base de datos y documentación. Nunca se presentan como datos de una
  empresa real.

*Razón*: el valor del producto está en fundamentar decisiones, no en sustituir al responsable
que las toma.

### II. Construcción reproducible

- Python DEBE estar fijado en `.python-version` y en `requires-python`. La versión vigente es
  un parámetro revisable (ver «Stack técnico y parámetros revisables»).
- La gestión de entornos y dependencias DEBE hacerse solo con `uv`. Se prohíben `pip` y
  `requirements.txt`. `uv.lock` DEBE versionarse.
- El código DEBE usar src-layout (`src/secguard_advisor/`) con backend de build `uv_build`.
- La calidad DEBE automatizarse con Ruff (lint y formato), pre-commit y pytest, expuestos en
  targets de `Makefile`. El CI DEBE ejecutar los mismos targets que el entorno local.
- Los commits DEBEN seguir Conventional Commits, en un solo idioma y en imperativo. No se
  agrega atribución de IA.
- La documentación y la interfaz DEBEN estar en español. El código, los identificadores, los
  nombres de tablas y los comentarios DEBEN estar en inglés.
- Un cambio de versión de Python o de una dependencia crítica DEBE identificar primero la
  causa de la incompatibilidad y registrarse en el registro de decisiones.

*Razón*: un entorno reproducible es condición para que la evidencia académica y la demo sean
verificables por terceros.

### III. Arquitectura modular

- La aplicación DEBE ser un monolito modular con responsabilidades separadas: interfaz,
  configuración, casos, ingesta, recuperación, agente, herramientas, persistencia y evaluación.
- La interfaz DEBE usar FastAPI para rutas y servicios, Jinja2 para plantillas y HTMX para
  solicitudes y actualizaciones parciales.
- Tailwind CSS y Flowbite (versión gratuita) DEBEN servirse localmente y estar versionados. No
  se permite CDN en la interfaz.
- LangChain DEBE cubrir procesamiento documental, embeddings y recuperación. LangGraph DEBE
  cubrir conversación, memoria, herramientas y flujo controlado.
- SQLite DEBE conservar el estado y la procedencia: casos, activos, hallazgos, mensajes,
  revisiones, trabajos y ejecuciones.
- Chroma DEBE ser un índice derivado y reconstruible. Eliminar el índice NO DEBE perder datos
  de negocio ni procedencia.
- NO se añaden microservicios ni infraestructura distribuida al alcance inicial.
- Los módulos DEBEN comunicarse por interfaces definidas, no leyendo directamente las tablas de
  otro módulo.

*Razón*: la separación permite cambiar interfaz, modelo o índice sin reescribir el dominio, y
mantiene el sistema operable en una sola máquina.

### IV. Ejecución local por defecto

- La inferencia DEBE ejecutarse con Ollama nativo de forma predeterminada.
- Los modelos DEBEN ser configurables y versionados. Se registra identificador, digest,
  cuantización, contexto y, para embeddings, dimensión.
- Qwen3.5 9B es el candidato generativo inicial. Gemma 4 de 7,5B Q4_K_M es el candidato de
  comparación; no se confunde con Gemma 4 12B.
- La selección definitiva DEBE basarse en calidad, uso de herramientas, fundamentación, memoria
  y latencia medidas. El tamaño de descarga NO es criterio de selección ni memoria de ejecución.
- DEBE fijarse un contexto explícito (`num_ctx`) y medirse la memoria real; no se usa el contexto
  máximo del modelo por defecto.
- Inicialmente DEBE cargarse un solo modelo generativo grande a la vez. La comparación entre
  candidatos es secuencial.
- Un proveedor externo es opcional, se selecciona explícitamente y no tiene fallback automático
  desde local.

*Razón*: la ejecución local protege los datos del caso y hace la demo reproducible sin depender
de servicios pagados.

### V. Recuperación verificable

- El corpus DEBE provenir de documentación oficial real, con título, versión, procedencia,
  condiciones de uso y fecha de obtención registrados.
- Los originales DEBEN conservarse y ser localizables por página o sección.
- La extracción DEBE ser comprobable. Una página o tabla no extraída se reporta; NO se omite ni
  se trunca en silencio.
- Toda respuesta normativa DEBE citar documento, página o sección verificable contra el original.
- DEBEN respetarse el tokenizer, los límites de contexto y los prefijos de tarea del modelo de
  embeddings.
- Cada colección vectorial DEBE corresponder a un modelo, versión y dimensión. Mezclar vectores
  incompatibles es un error. Un cambio de modelo de embeddings exige colección nueva y
  reindexación completa.
- La fragmentación DEBE medirse en tokens del modelo de embeddings, no en caracteres.

*Razón*: sin procedencia y sin límites respetados, la recuperación produce citas que no se
pueden verificar y respuestas que parecen fundamentadas sin serlo.

### VI. Separación de datos

- DEBEN mantenerse separados cuatro espacios: guías públicas de referencia, evidencias
  aportadas por el caso, datos sintéticos y conjuntos de evaluación.
- Las referencias académicas (`docs/referencias`) y las instrucciones para agentes NO forman
  parte del RAG consultivo. No se indexan, no se citan como normativa y no se recuperan.
- Los conjuntos de evaluación NO se usan para responder consultas del producto ni para
  seleccionar o promover modelos.
- Todo resultado de recuperación DEBE declarar de qué espacio proviene.
- Los datos de un caso NO se mezclan con los de otro caso en la misma colección.

*Razón*: mezclar espacios convierte una cita normativa en un dato del caso, o un resultado de
evaluación en una recomendación, sin que nadie lo note.

### VII. Seguridad

- El alcance del caso DEBE imponerse en el código antes de consultar SQLite, Chroma o memoria.
  Los argumentos del modelo NO conceden permisos.
- Los documentos DEBEN tratarse como entradas no confiables. NO se ejecutan instrucciones
  incrustadas, comandos arbitrarios ni remediaciones.
- Las herramientas DEBEN tener permisos explícitos y argumentos validados. El modelo no concede
  acceso ni puede aprobarse a sí mismo.
- La aprobación humana NO puede ser ejecutada por el agente.
- Los secretos NO se registran en logs, trazas ni respuestas.

*Razón*: un agente que puede ampliar su propio alcance deja de ser un consultor y pasa a ser un
riesgo operativo.

### VIII. Evidencia e incertidumbre

- Toda salida DEBE distinguir hecho verificado, hipótesis y recomendación.
- La ausencia de evidencia NO equivale a incumplimiento ni a riesgo bajo. La información
  faltante DEBE registrarse como faltante.
- Los conteos, indicadores y cálculos DEBEN realizarse mediante código y herramientas
  controladas. El modelo explica resultados y limitaciones; no los calcula.
- NO se fabrican resultados, fuentes, clientes, métricas ni estados de pruebas.
- Una capacidad NO se considera implementada por estar documentada.

*Razón*: el producto se evalúa por la calidad de sus recomendaciones, y una recomendación sin
evidencia es una opinión disfrazada.

### IX. Revisión humana

- La aprobación del informe DEBE estar separada de la adjudicación de prioridades. Aprobar el
  texto no confirma las prioridades de sus hallazgos.
- Solo las prioridades revisadas explícitamente y marcadas como elegibles pueden alimentar
  entrenamiento.
- Información insuficiente, rechazos sin prioridad alternativa y desacuerdos pendientes NO
  producen etiquetas elegibles.
- La política P1–P4 —significado, condiciones, excepciones, datos mínimos y ejemplos— DEBE
  acordarse con el equipo antes de entrenar. El agente NO la inventa ni la presume aprobada.
- Guardar una revisión NO dispara automáticamente entrenamiento ni activación.

*Razón*: sin separación entre aprobar y adjudicar, el sistema aprende de etiquetas que nadie
validó.

### X. Evaluación independiente

- DEBEN separarse entrenamiento, validación, regresión y prueba final.
- La prueba final NO se usa para seleccionar, ajustar ni promover modelos.
- DEBE evitarse el solapamiento indebido entre escenarios o activos. Las transformaciones se
  ajustan únicamente con entrenamiento.
- Toda comparación DEBE incluir líneas base: al menos una regla de severidad y la política
  completa que genera etiquetas sintéticas.
- Las limitaciones de los datos sintéticos DEBEN declararse. Una buena métrica sobre datos
  sintéticos no demuestra superioridad en una organización real.
- Las promociones DEBEN basarse en validación.

*Razón*: si la prueba final participa en la selección, deja de medir generalización.

### XI. Observabilidad y costos

- LangSmith DEBE recibir únicamente datos sintéticos o públicos autorizados. NO se registran
  claves ni secretos.
- La indisponibilidad de LangSmith NO bloquea la ejecución local. En ese caso queda evidencia
  operativa mínima en el log estándar y en SQLite.
- NO se construye otra plataforma de observabilidad.
- Un proveedor externo de inferencia es opcional, se selecciona explícitamente y no tiene
  fallback automático desde local.
- NO se activan llamadas pagadas sin presupuesto aprobado. El control de gasto DEBE reservar
  saldo antes de cada llamada e incluir reintentos.
- Una traza no configurada se declara pendiente; nunca se presenta como ejecutada.

*Razón*: la observabilidad debe servir para depurar y evaluar, no para acumular datos ni costos.

### XII. Desarrollo incremental

El producto se construye por funcionalidades verificables, en este orden:

1. **Consulta funcional**: caso con contexto; carga de PDF textual y Markdown; recuperación con
   procedencia; respuesta con citas verificables y evidencia visible; conversación con memoria
   persistente; consulta de hallazgos sintéticos precargados mediante herramienta controlada;
   abstención cuando falta información; registro de ejecución y traza real cuando exista
   configuración válida.
2. **Importación y revisión humana**: adaptador para un formato CSV de Qualys seleccionado y
   documentado, con validación de tipos, campos, rangos, fechas, duplicados y procedencia;
   separación de severidad de Qualys, CVSS, QID y CVE; pantalla de hallazgos con filtros y
   detalle; formulario de revisión con decisión, prioridad P1–P4 y justificación.
3. **Clasificación, aprendizaje y operación**: política P1–P4 acordada; clasificador ligero con
   scikit-learn; comparación con líneas base; pantalla administrativa de etiquetas,
   entrenamiento, versiones, métricas, activación y rollback; MLflow con backend SQLite y
   artefactos locales; flujos Prefect; exportación, cola acotada, cancelación, expiración,
   recuperación tras reinicio, Docker Compose y pruebas de carga.

- El especialista adicional, el clustering, Isolation Forest, el reranker con Transformers y el
  streaming son opcionales. NO son dependencias del núcleo.
- Las pruebas y el CI se incorporan desde el primer incremento; no se difieren al final.
- Cada funcionalidad DEBE tener criterios de aceptación y evidencia observada.

*Razón*: un incremento que no se puede demostrar no está terminado, sin importar cuánto código
contenga.

## Stack técnico y parámetros revisables

Los principios I–XII son **permanentes**. Los elementos de esta sección son **parámetros
técnicos revisables**: pueden cambiar sin enmienda constitucional, pero todo cambio DEBE
registrarse en el registro de decisiones con fecha, motivo y evidencia.

Un cambio que altere un principio permanente —por ejemplo, permitir remediaciones automáticas o
convertir Chroma en fuente de verdad— NO es un cambio de parámetro: exige enmienda.

### Stack fijado

| Capa | Tecnología | Carácter |
|---|---|---|
| Rutas y servicios | FastAPI | Fijado |
| Plantillas | Jinja2 | Fijado |
| Interacción parcial | HTMX | Fijado |
| Estilo e interfaz | Tailwind CSS + Flowbite gratuito, local | Fijado |
| Documentos, embeddings, recuperación | LangChain | Fijado |
| Conversación, memoria, herramientas | LangGraph | Fijado |
| Inferencia | Ollama nativo | Fijado |
| Estado y procedencia | SQLite | Permanente |
| Índice vectorial | Chroma persistente, derivado | Permanente (derivado) |
| Trazas y evaluación | LangSmith | Fijado |
| Clasificación (incremento 3) | scikit-learn | Fijado |
| Registro de modelos (incremento 3) | MLflow con backend SQLite y artefactos locales | Fijado |
| Orquestación por lotes (incremento 3) | Prefect | Fijado |
| Empaquetado operativo (incremento 3) | Docker Compose | Fijado |

### Parámetros vigentes

| Parámetro | Valor vigente | Evidencia o nota |
|---|---|---|
| Versión de Python | 3.14.6 | `uv sync` resuelve 133 paquetes sin error |
| Empaquetado | uv + `uv_build`, src-layout | Estándar del proyecto |
| Modelo generativo inicial | `qwen3.5:9b` (digest `56671c2ab938`, ctx 262144, Q4_K_M) | Instalado; *thinking* activo por defecto |
| Modelo de comparación | `gemma4:latest`, 7.5B Q4_K_M | Instalado; no es 12B |
| Modelo de embeddings | `embeddinggemma:latest`, EmbeddingGemma 1, 768 dims, 2048 tokens | Instalado; v2 no está instalada |
| Presupuesto de chunk | ≤1600 tokens de contenido | Reserva para prefijo y solape |
| Prefijos de embeddings | `task: search result \| query:` y `title: … \| text:` | Tarjeta oficial del modelo |
| Corpus del primer flujo | NIST CSWP 29, NIST AI 100-1, NIST AI 600-1, OWASP Top 10 LLM 2025 | `docs/planificacion/01-corpus-rag.md` |
| Corpus diferido | NIST SP 1301 (incremento 2) | Se solapa con CSF 2.0 |
| Directorio de almacenamiento | `./storage` | Configurable por entorno |
| Proveedor externo opcional | DeepSeek, deshabilitado | Sin presupuesto aprobado no se activa; sin fallback automático |

### Prohibiciones de arquitectura

- No microservicios ni infraestructura distribuida en el alcance inicial.
- No CDN para recursos de interfaz.
- No `pip` ni `requirements.txt`.
- No fallback automático de un proveedor externo hacia local ni en sentido inverso.
- No segunda plataforma de observabilidad.

## Flujo de trabajo y puertas de calidad

### Secuencia de trabajo

El proyecto sigue el orden de Spec Kit: constitución, especificación, aclaraciones, plan,
tareas, análisis de consistencia e implementación por incrementos. La implementación avanza por
funcionalidades verificables, no por capas completas.

### Política de pruebas

- Por defecto se aplica test-first: cuando existe una prueba determinista ejecutable y un
  resultado esperado claro, se observa RED antes de implementar, luego GREEN y después
  refactorización con las pruebas en verde.
- Cada regla solicitada DEBE tener al menos una prueba que la cubra.
- Toda funcionalidad existente que comparta código con el cambio DEBE conservar una prueba que
  demuestre que su comportamiento anterior sigue vigente.
- Las pruebas de integración DEBEN ejecutar Ollama, embeddings, recuperación y herramientas
  reales. Los mocks se permiten solo en pruebas automatizadas identificadas como unitarias.
- Cuando no exista una prueba RED significativa —documentación pasiva o runner no disponible—
  se declara la excepción y se ejecutan comprobaciones funcionales o estructurales
  proporcionales.
- El estado temporal de las pruebas (directorios temporales, cachés, `HOME`, `TMPDIR`) DEBE
  quedar fuera del árbol de trabajo.

### Puertas de calidad

- `make check` DEBE ejecutar lint, formato y pruebas. Ningún cambio se integra con la puerta en
  rojo.
- `pre-commit` DEBE estar instalado y ejecutarse. `--no-verify` está prohibido salvo causa
  documentada.
- El CI DEBE replicar los mismos targets que el entorno local.
- Ningún estado —verde, completado, aprobado— se declara antes de ejecutar la comprobación
  correspondiente.
- Un cambio arquitectónico, tecnológico o de proceso DEBE actualizar la constitución en el mismo
  commit.

### Obligaciones académicas y conocimiento deseable

Las obligaciones evaluables provienen de la rúbrica disponible y exigen **evidencia
demostrable**, no solo documentación:

- R.6.1: formulación del problema con contexto, justificación del modelo frente a alternativas,
  integración al caso y evaluación crítica del desempeño.
- R.6.2: selección de tareas automatizables con valor real, demostración de eficiencia con
  indicadores, mitigación de riesgos éticos y documentación replicable.
- R.7.1: pipeline de datos con limpieza, transformación y validación.
- R.7.2: prácticas MLOps con versionado, registro, actualización y reentrenamiento.
- RA1 y RA2: comunicación escrita y oral ajustada a contexto y audiencia.

Los **prerrequisitos deseables** de la hoja de retos —Python y SQL, ML básico, experiencia con
LLM, frameworks de agentes, flujos multi-agente, control de costos, traducción de necesidades de
negocio— describen capacidades del equipo. NO son funcionalidades obligatorias del producto y
NO se convierten en requisitos del sistema.

Las columnas vacías de la hoja de retos —alcance, objetivos, datos disponibles, criterios de
éxito y herramientas sugeridas— no aportan alcance. El alcance vinculante es el brief del
producto y esta constitución.

### Publicación

No se publica repositorio ni servicio hasta definir destino y autorización. Los badges del
README DEBEN ser verificables o no incluirse; no se inventan estados de CI.

## Governance

### Jerarquía normativa y constitución única

Esta constitución es la fuente única de verdad y prevalece sobre especificaciones, planes,
tareas, ADRs y código.

El contenido normativo vive en `.specify/memory/constitution.md`. `CONSTITUTION.md`, en la raíz,
es un enlace simbólico a ese archivo. NO se mantienen dos documentos editados por separado:

- Se edita únicamente `.specify/memory/constitution.md`.
- Sobrescribir ese archivo DEBE preservar el enlace. Se verifica después de cada enmienda.
- Si el enlace se rompe o se duplica el contenido, la enmienda se considera inválida hasta
  restaurarlo.
- Una comprobación automatizada DEBE fallar si `CONSTITUTION.md` deja de ser un enlace al
  archivo normativo.

### Reglas de modificación

1. **Propuesta.** Cualquier integrante puede proponer una enmienda, indicando el principio o
   sección afectada.
2. **Justificación.** La propuesta DEBE incluir motivo, impacto en especificaciones, plan,
   tareas y código, y evidencia que la respalde.
3. **Revisión.** La enmienda requiere acuerdo del equipo: Edwin Perez L., Cristian Quebrada y
   Ruben Dario Sabogal.
4. **Versión.** Se incrementa según versionado semántico: MAJOR por eliminación o redefinición
   incompatible de un principio; MINOR por principio o sección nueva, o ampliación material;
   PATCH por aclaraciones y correcciones que no cambian el significado.
5. **Registro.** Toda enmienda se anota en el registro de decisiones con fecha, versión y
   motivo.
6. **Propagación.** Los artefactos afectados se actualizan en el mismo commit que la enmienda.
   Una especificación que necesite una excepción DEBE registrarla con alcance, motivo y fecha de
   revisión; no se admiten excepciones silenciosas.
7. **Informe.** El Sync Impact Report se elimina antes del commit de la enmienda.

### Cumplimiento

- Toda revisión de cambios DEBE verificar el cumplimiento de esta constitución.
- La plantilla de Pull Request incluye la verificación explícita.
- Un incumplimiento bloquea la integración.
- Una complejidad añadida DEBE justificarse frente a la alternativa más simple.

### Registro de decisiones

| Fecha | Decisión | Tipo | Principio | Motivo o evidencia |
|---|---|---|---|---|
| 2026-11-08 | Constitución única en `.specify/memory/constitution.md` con `CONSTITUTION.md` como enlace simbólico | Permanente | Gobernanza | Spec Kit escribe en `.specify`; el estándar exige `CONSTITUTION.md`; enlace verificado |
| 2026-11-08 | Documentación e interfaz en español; código e identificadores en inglés | Permanente | II | Producto y rúbrica en español; código legible por herramientas |
| 2026-11-08 | Chroma derivado y reconstruible; SQLite como fuente de verdad | Permanente | III | Permite reindexar sin perder procedencia |
| 2026-11-08 | Assets de interfaz locales y versionados, sin CDN | Permanente | III | Operación offline y demo reproducible |
| 2026-11-08 | Sin autenticación en el incremento 1; alcance por caso impuesto en código | Permanente | VII | Uso local mono-usuario; la seguridad no depende de un login |
| 2026-11-08 | Pruebas de integración con Ollama, embeddings, recuperación y herramientas reales | Permanente | II, X | Un mock no acredita una demo |
| 2026-11-08 | Corpus del primer flujo: NIST CSWP 29, NIST AI 100-1, NIST AI 600-1 y OWASP Top 10 LLM 2025 | Parámetro | V | Cobertura de ciberseguridad, riesgo de IA y aplicaciones LLM |
| 2026-11-08 | NIST SP 1301 diferido al incremento 2 | Parámetro | V, XII | Se solapa con CSF 2.0; su valor aparece al construir perfiles organizacionales |
| 2026-11-08 | Originales del corpus fuera de Git, con manifiesto, URL, fecha y SHA-256 calculado al descargar | Parámetro | V | Evita inflar el repositorio sin perder procedencia |
| 2026-11-08 | Python 3.14.6 verificado con `uv sync` | Parámetro | II | 133 paquetes resueltos sin error; stack del incremento 3 también resuelve |
| 2026-11-08 | EmbeddingGemma 1: 768 dimensiones, 2048 tokens, prefijos de tarea oficiales | Parámetro | V | Modelo instalado; la versión 2 no está instalada |
| 2026-11-08 | Qwen3.5 9B como generador inicial; Gemma 4 de 7,5B Q4_K_M como comparación | Parámetro | IV | Candidatos definidos en el brief; selección final pendiente de medición |
| 2026-11-08 | Razonamiento desactivado en el generador configurado (`reasoning=False`) | Parámetro | IV | Con razonamiento activo la salida estructurada no se producía dentro del presupuesto (400 tokens, 29 s, contenido vacío); desactivado respondió en 2,7 s |
| 2026-11-08 | Umbral de recuperación por similitud coseno en 0,35 | Parámetro | V, X | Datos de humo con corpus real: preguntas pertinentes ≥ 0,58; fuera de dominio ≤ 0,05. Filtra candidatos débiles, no prueba ausencia de evidencia |
| 2026-11-08 | Historial de conversación acotado a 8 mensajes y 6000 caracteres; evidencia limitada a 3500 tokens | Parámetro | IV | `num_ctx=8192` y `num_predict=1200` dejan margen para instrucciones e historial; los tokens de evidencia se miden con Ollama al ingerir |
| 2026-11-08 | La recuperación de una pregunta de seguimiento se amplía con la última pregunta confirmada | Parámetro | IV, V | Interpreta referencias sin un segundo modelo; la evidencia se recupera y valida igual contra los fragmentos del turno |
| 2026-11-08 | Admisión de contexto con el tokenizador del generador (vocabulario y BPE del GGUF instalado), reserva de salida 1200 y margen 320 para la plantilla | Parámetro | IV | Verificado contra `prompt_eval_count` de qwen3.5:9b (24 = 24 en el mínimo; +1 en español; +17-21 en técnico/Base64). El margen cubre variaciones de plantilla, no incertidumbre del tokenizador |
| 2026-11-08 | Dependencias `gguf` y `tokenizers` para leer el tokenizador del modelo instalado | Parámetro | IV, III | No hay descargas en tiempo de ejecución ni llamadas pagadas; `tokenizers` ya era transitiva y `gguf` solo lee el GGUF local |
| Pendiente | Política P1–P4: significado, condiciones, excepciones, datos mínimos y ejemplos | Pendiente | IX, X | Bloquea el entrenamiento del incremento 3 |
| Pendiente | Formato CSV de Qualys a soportar | Pendiente | XII | Bloquea el adaptador del incremento 2 |
| Pendiente | Generador definitivo tras la comparación | Pendiente | IV | Requiere evidencia de calidad, herramientas, fundamentación, memoria y latencia |
| 2026-11-08 | LangSmith parametrizado: `LANGSMITH_ENDPOINT=https://api.smith.langchain.com`, proyecto `secguard-advisor-dev`, traza real verificada con estado `success` | Parámetro | XI | Prueba sintética sin datos de caso; la clave vive solo en `.env`, ignorado por Git |
| 2026-11-08 | Una sola consulta activa por caso y una generación local a la vez; liberación en éxito, error, timeout y reinicio | Parámetro | IV, XI | Evita concurrencia de escritura sobre SQLite y carga simultánea de modelos |
| 2026-11-08 | Revisión humana mínima del respaldo semántico de citas: pendiente, respaldada o no respaldada, con autor, fecha y observación | Permanente | VIII, IX | SC-003 no es automatizable; una cita válida no acredita fundamentación |
| 2026-11-08 | Dos controles distintos: exclusión por caso con índice único y semáforo global de una generación; un proceso y un worker | Permanente | IV, XI | Evita generaciones simultáneas entre casos y bloqueos de escritura |
| 2026-11-08 | `SECGUARD_REVIEWER_NAME` como identidad local declarada del revisor; sin valor no se guarda revisión; no es autenticación | Permanente | VIII, IX | El autor no puede inventarse; el incremento no incluye autenticación |
| 2026-11-08 | Respuesta, citas, telemetría y cierre de ejecución en una sola transacción; reintento solo sin respuesta persistida | Permanente | VIII | Evita respuestas visibles con ejecución abierta y respuestas duplicadas |
| 2026-11-08 | Recursos de interfaz fijados: Tailwind 3.4.17, Flowbite 2.5.2, HTMX 2.0.4; Node 22 en CI; CSS y JS vendorizados con hashes | Parámetro | III | Build reproducible desde `package-lock.json`; hashes en `MANIFEST.md` |
| 2026-11-08 | Node unificado en 26.11.1 mediante `.nvmrc` y `engines`; CI usa el mismo archivo | Parámetro | III | Elimina la divergencia local/CI; el build de recursos se verificó desde el lockfile |
| Pendiente | Destino GitHub y autorización de publicación | Pendiente | Flujo de trabajo | Sin repo no hay badges de CI verificables |
| Pendiente | Presupuesto aprobado para DeepSeek (proveedor externo opcional) | Pendiente | XI | No se activan llamadas pagadas sin aprobación |

**Version**: 1.0.5 | **Ratified**: 2026-11-08 | **Last Amended**: 2026-11-08
