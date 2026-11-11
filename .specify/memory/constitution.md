# SecGuard Advisor Constitution

## Core Principles

### I. Propósito y alcance

SecGuard Advisor es un agente consultor **defensivo** para ciberseguridad empresarial. Ayuda a
consultar documentación, analizar reportes de vulnerabilidades mediante herramientas y apoyar
decisiones con evidencia verificable. Es configurable por contexto organizacional.

- El alcance DEBE cubrir consulta documental con evidencia, análisis de vulnerabilidades mediante
  herramientas, apoyo a decisiones y acciones operativas controladas. La seguridad de sistemas de
  IA es un caso posible cuando corresponda, no un requisito para usar el producto.
- El producto DEBE producir recomendaciones sujetas a revisión humana, con evidencia rastreable y
  límites declarados.
- El producto NO DEBE ejecutar remediaciones, modificar sistemas, aprobar informes ni adjudicar
  prioridades por cuenta propia.
- Las acciones operativas externas, si existen, DEBEN seguir el principio XIV: preparar,
  previsualizar, confirmar, ejecutar y registrar evidencia. No son remediaciones automáticas.
- El producto NO DEBE certificar cumplimiento ni presentarse como auditor o certificador.
- El producto NO DEBE incluir capacidades ofensivas ni explotación.
- Los escenarios organizacionales y hallazgos educativos sintéticos DEBEN identificarse como
  sintéticos en interfaz, base de datos y documentación. Nunca se presentan como datos de una
  empresa real.

*Razón*: el valor del producto está en fundamentar decisiones y ejecutar acciones acotadas con
control humano, no en sustituir al responsable que las toma ni en certificar su organización.

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
  revisiones, trabajos y ejecuciones. SQLite es la fuente de verdad.
- El índice vectorial DEBE ser derivado y reconstruible. Eliminar el índice NO DEBE perder datos de
  negocio ni procedencia. Qdrant es la tecnología objetivo para 004; Chroma permanece como
  implementación actual durante la transición.
- El diseño objetivo de 004 es **Qdrant en servidor local persistente, preferiblemente mediante
  Docker Compose**, con acceso limitado al equipo local. El modo embebido se reserva para pruebas o
  como alternativa expresamente documentada; no se presentan ambas modalidades como implementadas.
  La versión de servidor, cliente y configuración se concretará en la planificación técnica.
- Qdrant es una dependencia de infraestructura local, no un microservicio de dominio. NO se añaden
  microservicios ni infraestructura distribuida al alcance inicial.
- El índice DEBE conservar procedencia, versiones, resolución de citas, aislamiento entre casos y
  corpus público compartido. La recuperación ante fallos y la verificación deben completarse antes
  de retirar el índice anterior.
- El cambio de índice de 004 NO DEBE cambiar simultáneamente el modelo de embeddings. La dependencia
  actual de Ollama para embeddings es independiente del futuro cambio de generador.
- Los módulos DEBEN comunicarse por interfaces definidas, no leyendo directamente las tablas de
  otro módulo.

*Razón*: la separación permite cambiar interfaz, modelo o índice sin reescribir el dominio, y
mantiene el sistema operable en una sola máquina.

### IV. Persistencia local e inferencia autorizada

- La persistencia y los embeddings DEBEN ejecutarse localmente por defecto.
- El generador PUEDE ser local (Ollama) o un proveedor API explícitamente configurado. NO existe
  fallback automático entre proveedores ni desde/hacia local.
- Para 005 se evaluarán Claude Haiku y DeepSeek. Sus identificadores, versiones y precios DEBEN
  verificarse en documentación oficial al planificar y evaluar; no son reglas constitucionales
  permanentes.
- No se declara un proveedor seleccionado ni un presupuesto aprobado. NO se activan llamadas
  pagadas sin aprobación.
- Cualquier generador DEBE conservar citas verificables, herramientas con argumentos controlados,
  memoria acotada, abstención, límites de contexto y salida, tiempo y número de llamadas acotados,
  reintentos acotados y registro de proveedor, modelo, uso y costo.
- Ollama PUEDE conservarse durante la transición y para embeddings locales. No se presenta como
  generador objetivo definitivo.
- El tokenizador y las reglas específicas de Qwen/Ollama son decisiones de la implementación
  actual. NO deben imponerse a todos los proveedores futuros.
- Los modelos DEBEN ser configurables y versionados. Se registra proveedor, identificador, versión
  y, para embeddings, dimensión.
- Cuando la inferencia sea local, DEBE cargarse un solo modelo generativo grande a la vez y la
  comparación entre candidatos DEBE ser secuencial.

*Razón*: la persistencia y los embeddings locales protegen los datos del caso; la inferencia
externa solo se permite con configuración explícita, presupuesto y una frontera de datos declarada.

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
- Toda migración de índice DEBE comparar recuperación, citas, aislamiento y fallos antes de retirar
  el índice anterior. El índice anterior DEBE conservarse hasta completar la verificación.
- La migración a Qdrant de 004 NO DEBE cambiar el modelo de embeddings. Un cambio de embeddings es
  una decisión separada, con reindexación y comparación propias.

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
- Los datos que salen del equipo hacia un proveedor de inferencia, una acción externa o una traza
  DEBEN regirse por el principio XIII. Habilitar un proveedor API NO autoriza enviarle a LangSmith
  los mismos datos.
- LangSmith mantiene una política independiente y limitada de contenido.

*Razón*: mezclar espacios convierte una cita normativa en un dato del caso, o un resultado de
evaluación en una recomendación, sin que nadie lo note; y la salida de datos exige una frontera
explícita.

### VII. Seguridad

- El alcance del caso DEBE imponerse en el código antes de consultar SQLite, Qdrant, Chroma en
  transición o memoria. Los argumentos del modelo NO conceden permisos.
- Los documentos DEBEN tratarse como entradas no confiables. NO se ejecutan instrucciones
  incrustadas, comandos arbitrarios ni remediaciones.
- Las herramientas DEBEN tener permisos explícitos y argumentos validados. El modelo no concede
  acceso ni puede aprobarse a sí mismo.
- La aprobación humana NO puede ser ejecutada por el agente. Las acciones externas siguen el
  principio XIV y nunca se envían por iniciativa del modelo.
- Las credenciales de canales externos DEBEN mantenerse separadas de los datos de destinatarios y
  NO se registran en logs, trazas, respuestas ni SQLite.
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
  claves ni secretos. Habilitar un proveedor API NO amplía la autorización de LangSmith.
- La indisponibilidad de LangSmith NO bloquea la ejecución local. En ese caso queda evidencia
  operativa mínima en el log estándar y en SQLite.
- NO se construye otra plataforma de observabilidad.
- Un proveedor externo de inferencia o de acción es opcional, se selecciona explícitamente y no
  tiene fallback automático desde local ni hacia local.
- NO se activan llamadas pagadas sin presupuesto aprobado. El control de gasto DEBE reservar
  saldo antes de cada llamada e incluir reintentos.
- Se DEBE registrar proveedor, modelo, versión, uso y costo de todas las llamadas del turno,
  incluidas decisión, herramientas y reparación.
- NO se afirma retención cero, ausencia de entrenamiento ni garantía de privacidad sin evidencia
  de las condiciones aplicables.
- Una traza no configurada se declara pendiente; nunca se presenta como ejecutada.

*Razón*: la observabilidad debe servir para depurar y evaluar, no para acumular datos ni costos.

### XII. Desarrollo incremental

El producto se construye por funcionalidades verificables, en este orden:

1. **Consulta funcional**: caso con contexto; carga de PDF textual y Markdown; recuperación con
   procedencia; respuesta con citas verificables y evidencia visible; conversación con memoria
   persistente; consulta de hallazgos sintéticos precargados mediante herramienta controlada;
   abstención cuando falta información; registro de ejecución y traza real cuando exista
   configuración válida.
2. **Importación y consulta de hallazgos**: adaptador para un formato CSV de Qualys seleccionado y
   documentado, con validación de tipos, campos, rangos, fechas, duplicados y procedencia;
   separación de severidad de Qualys, CVSS, QID y CVE; pantalla de hallazgos con filtros y
   detalle. La importación no incluye el formulario de revisión P1–P4.
3. **004 — Qdrant**: migración del índice derivado a Qdrant local persistente, preferiblemente en
   servidor con Docker Compose; reconstrucción desde SQLite; comparación con Chroma; mismas
   citas, aislamiento y corpus público. No cambia el modelo de embeddings.
4. **005 — Generador API**: interfaz de proveedor y evaluación de Claude Haiku y DeepSeek con
   datos públicos o ficticios; presupuesto, conteo de tokens, herramientas, memoria, abstención,
   latencia y costo. No selecciona proveedor ni habilita llamadas pagadas por sí sola.
5. **006 — Acción operativa**: destinatarios verificados, preparación, vista previa, confirmación,
   ejecución y evidencia; Telegram para evaluación; correo y mesa de ayuda posteriores.
6. **007 — Aceptación integrada**: recorrido completo con Qdrant, proveedor elegido y acción
   externa; comparación, reversión, guía y PDF; datos públicos o ficticios.
7. **003 — Retomar priorización y clasificación**: política P1–P4 aprobada o revisada; contexto y
   etiquetas; formulario de revisión; clasificador ligero con scikit-learn; comparación con
   líneas base; pantalla administrativa de etiquetas, entrenamiento, versiones, métricas,
   activación y rollback; MLflow con backend SQLite y artefactos locales; flujos Prefect;
   exportación, cola acotada, cancelación, expiración, recuperación tras reinicio, Docker Compose
   y pruebas de carga. 003 sigue suspendida hasta completar 004–007; su número no altera el orden
   de ejecución.

- El especialista adicional, el clustering, Isolation Forest, el reranker con Transformers y el
  streaming son opcionales. NO son dependencias del núcleo.
- Las pruebas y el CI se incorporan desde el primer incremento; no se difieren al final.
- Cada funcionalidad DEBE tener criterios de aceptación y evidencia observada.

*Razón*: un incremento que no se puede demostrar no está terminado, sin importar cuánto código
contenga.

### XIII. Frontera de datos y proveedores externos

- La operación DEBE distinguir: persistencia local, embeddings locales, inferencia externa
  autorizada, trazabilidad y acciones externas.
- La protección DEBE aplicarse al archivo CSV original, filas y resultados derivados, activos e
  IP, preguntas e historial, fragmentos documentales, argumentos y resultados de herramientas y
  mensajes preparados para envío.
- Que el archivo original no se envíe NO demuestra que sus datos derivados estén protegidos. La
  minimización y la redacción DEBEN aplicarse antes de cualquier salida.
- Las pruebas iniciales de proveedor externo y de acciones DEBEN usar datos públicos o ficticios.
- El envío de información privada DEBE depender de una política explícita de contenido permitido y
  de autorización aplicable al caso. Esta constitución NO autoriza la salida del CSV privado ni de
  sus datos derivados.
- LangSmith mantiene una política independiente y limitada. Habilitar un proveedor API NO autoriza
  enviarle a LangSmith los mismos datos.
- NO se afirma retención cero, ausencia de entrenamiento ni garantía de privacidad sin evidencia de
  las condiciones aplicables.
- Las credenciales NO son datos de destinatario ni contenido; se mantienen separadas y fuera de
  logs, trazas y almacenamiento de negocio.

*Razón*: la inferencia externa y las acciones externas amplían la superficie de exposición; una
frontera explícita evita confundir “no enviar el archivo” con “proteger sus datos”.

### XIV. Acciones operativas controladas

- La capacidad objetivo es: preparar → previsualizar → confirmar → ejecutar → registrar evidencia.
- El modelo PUEDE proponer una acción. La aplicación DEBE validar contenido, caso, destinatario y
  permisos aplicables.
- El destinatario DEBE estar configurado y verificado. El agente NO inventa destinatarios ni envía
  mensajes por iniciativa propia.
- La confirmación DEBE corresponder al contenido y destino concretos. Una edición del contenido o
  del destino invalida la confirmación anterior.
- Las credenciales DEBEN mantenerse separadas de los datos de destinatarios.
- Se DEBE registrar el resultado real del proveedor. Un envío aceptado NO equivale a recibido o
  leído; esas afirmaciones solo se hacen con evidencia.
- Un timeout PUEDE producir un resultado incierto. NO habilita reintento ciego.
- Se DEBEN prevenir dobles envíos sin prometer entrega exactamente una vez cuando el proveedor no
  la garantiza.
- Telegram es el primer canal propuesto para evaluación. Correo y mesa de ayuda son alternativas
  posteriores, no integraciones disponibles.
- La acción PUEDE usar resultados de 002; NO requiere P1–P4 ni una política de prioridad aprobada.
- La identidad declarada actual NO es autenticación. El entorno educativo mantiene restricciones
  explícitas y el control de acceso multiusuario queda como necesidad futura.

*Razón*: una acción externa sin confirmación, destinatario verificado y evidencia de resultado
convierte una recomendación en una escritura irreversible fuera del sistema.

## Stack técnico y parámetros revisables

Los principios I–XIV son **permanentes**. Los elementos de esta sección son **parámetros
técnicos revisables**: pueden cambiar sin enmienda constitucional, pero todo cambio DEBE
registrarse en el registro de decisiones con fecha, motivo y evidencia.

Un cambio que altere un principio permanente —por ejemplo, permitir remediaciones automáticas o
convertir el índice vectorial en fuente de verdad— NO es un cambio de parámetro: exige enmienda.

### Stack técnico: actual y objetivo

| Capa | Tecnología | Carácter |
|---|---|---|
| Rutas y servicios | FastAPI | Fijado |
| Plantillas | Jinja2 | Fijado |
| Interacción parcial | HTMX | Fijado |
| Estilo e interfaz | Tailwind CSS + Flowbite gratuito, local | Fijado |
| Documentos, embeddings, recuperación | LangChain | Fijado |
| Conversación, memoria, herramientas | LangGraph | Fijado |
| Inferencia | Generador local Ollama o proveedor API explícito | Objetivo 005; Ollama en transición; sin selección |
| Proveedor API | Claude Haiku / DeepSeek como candidatos | En evaluación 005; no seleccionado |
| Estado y procedencia | SQLite | Permanente |
| Índice vectorial | Qdrant local persistente, derivado | Objetivo 004; Chroma en transición |
| Infraestructura vectorial | Qdrant en servidor local con Docker Compose; embebido para pruebas o alternativa documentada | Objetivo 004; no implementado |
| Trazas y evaluación | LangSmith | Fijado |
| Acción externa | Telegram para evaluación; correo y mesa de ayuda posteriores | Objetivo 006; no implementado |
| Clasificación (003) | scikit-learn | Fijado |
| Registro de modelos (003) | MLflow con backend SQLite y artefactos locales | Fijado |
| Orquestación por lotes (003) | Prefect | Fijado |
| Empaquetado operativo (003) | Docker Compose | Fijado |

### Parámetros actuales y objetivos

| Parámetro | Valor vigente | Evidencia o nota |
|---|---|---|
| Versión de Python | 3.14.6 | `uv sync` resuelve 133 paquetes sin error |
| Empaquetado | uv + `uv_build`, src-layout | Estándar del proyecto |
| Modelo generativo inicial | `qwen3.5:9b` (digest `56671c2ab938`, ctx 262144, Q4_K_M) | Instalado; *thinking* activo por defecto |
| Modelo de comparación | `gemma4:latest`, 7.5B Q4_K_M | Instalado; no es 12B |
| Modelo de embeddings | `embeddinggemma:latest`, EmbeddingGemma 1, 768 dims, 2048 tokens | Instalado; v2 no está instalada; sin cambio en 004 |
| Generador objetivo | API por evaluar en 005 | Claude Haiku / DeepSeek; no seleccionado; Ollama en transición |
| Índice objetivo | Qdrant local persistente (004) | Chroma actual en transición; servidor local con Docker Compose |
| Acción externa | Telegram para evaluación (006) | No implementada; correo y mesa de ayuda posteriores |
| Presupuesto API | No aprobado | Sin llamadas pagadas ni cuentas creadas |
| Presupuesto de chunk | ≤1600 tokens de contenido | Reserva para prefijo y solape |
| Prefijos de embeddings | `task: search result \| query:` y `title: … \| text:` | Tarjeta oficial del modelo |
| Corpus del primer flujo | NIST CSWP 29, NIST AI 100-1, NIST AI 600-1, OWASP Top 10 LLM 2025 | `docs/planificacion/01-corpus-rag.md` |
| Corpus diferido | NIST SP 1301 (incremento 2) | Se solapa con CSF 2.0 |
| Directorio de almacenamiento | `./storage` | Configurable por entorno |
| Proveedores externos opcionales | Claude Haiku / DeepSeek en evaluación; ninguno seleccionado | Sin presupuesto aprobado no se activan; sin fallback automático |

### Prohibiciones de arquitectura

- No microservicios ni infraestructura distribuida en el alcance inicial. Qdrant local es una
  dependencia de infraestructura, no un microservicio de dominio.
- No CDN para recursos de interfaz.
- No `pip` ni `requirements.txt`.
- No fallback automático de un proveedor externo hacia local ni en sentido inverso.
- No segunda plataforma de observabilidad.
- No presentar Qdrant, el proveedor API ni Telegram como implementados antes de su aceptación.
- No enviar el CSV privado ni sus datos derivados a proveedores o acciones sin política explícita
  de contenido y autorización aplicable al caso.
- No afirmar retención cero, ausencia de entrenamiento ni garantía de privacidad sin evidencia.
- No ejecutar acciones externas sin preparación, vista previa y confirmación humana del contenido y
  destino concretos.
- No presentar la identidad declarada como autenticación ni la aplicación como multiusuario segura.

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
- Las pruebas de integración locales DEBEN ejecutar Ollama, embeddings, recuperación y
  herramientas reales. Las pruebas de proveedor API usan datos públicos o ficticios y presupuesto
  autorizado; los dobles se identifican como unitarios. Las pruebas de acción usan bot y chat de
  prueba, no destinatarios reales.
- Los mocks se permiten solo en pruebas automatizadas identificadas como unitarias.
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

### Estado de ratificación de la enmienda 1.2.0

- **Solicitud y autorización registrada:** Edwin Perez L., responsable del producto, solicitó y
  autorizó esta evolución documental en la conversación del 2026-11-11. La autorización cubre la
  propuesta y su propagación documental; no crea cuentas, no autoriza gasto ni envía mensajes.
- **Ratificación pendiente:** conforme a la regla 3, falta el acuerdo de Cristian Quebrada y Ruben
  Dario Sabogal. No consta acta, firma, reunión ni aprobación académica adicional.
- **Efecto mientras falte la ratificación:** la versión 1.2.0 es una **propuesta revisable**. No se
  presenta como acuerdo del equipo ni habilita por sí sola la implementación de 004–006. La
  propuesta documental puede revisarse y completarse; las decisiones técnicas rutinarias no se
  amplían a decisiones de política que requieran ratificación.
- **Alcance de la suspensión:** 003 sigue suspendida y su política P1–P4 no está aprobada.

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
| 2026-11-09 | Selección de herramienta en una llamada estructurada previa (`ToolDecision`) y presupuesto también para la decisión y los resultados | Permanente | IV, VIII | Ollama no emite `tool_calls` nativos junto con `format`; la decisión separada evita el sesgo de las reglas de respuesta y conserva argumentos estrictos, máximo de dos llamadas y medición con el tokenizador |
| 2026-11-09 | `findings_query` acotada por clausura, con conteos en SQLite y resultado sintético con procedencia | Permanente | V, VII, VIII | Sin `case_id` en esquema ni resultado; CVE por subconsulta; el límite afecta solo al detalle; un total 0 no demuestra ausencia de vulnerabilidades |
| 2026-11-09 | Evidencia de ejecución con intentos, pasos, fuentes, herramientas, presupuesto y citas separadas; la página lee registros persistidos | Permanente | VIII, IX | El detalle de herramienta no se persiste y se rotula como consulta actual; el control automático y la revisión humana no se confunden |
| 2026-11-09 | Traza externa manual y acotada con estados `disabled`, `submitted` y `failed`; la aplicación nunca escribe `confirmed` | Permanente | VIII, XI | El SDK puede ocultar errores de envío; se usa envío síncrono y `flush` acotado. La confirmación por API de lectura corresponde a T091 |
| 2026-11-09 | Límites del turno: 8 operaciones de modelo o herramienta, 2 herramientas, 1 reparación, 120 s de turno y 90 s por llamada | Parámetro | IV, XI | La decisión de herramienta consume paso y tiempo; cada llamada usa el tiempo restante y no recibe un presupuesto nuevo |
| 2026-11-09 | Confirmación de traza únicamente por `scripts/confirm_trace.py` con lectura externa, identidad declarada, fecha y evidencia | Permanente | VIII, XI | La aplicación nunca escribe `confirmed`; se rechaza una traza inexistente, de otro proyecto o no correlacionada con `run_id`, `case_id` e intento |
| 2026-11-09 | Aceptación en almacenamiento separado y `make demo-prepare`/`make demo` sobre `storage/demo` | Permanente | II, VIII | No se tocan los casos del usuario; preparación y arranque usan la misma instancia y el recorrido queda reproducible desde el Makefile |
| 2026-11-09 | SC-001 (recorrido humano cronometrado) y SC-003 (diez revisiones semánticas) son validaciones recomendadas y no bloqueantes; resultados reales no ejecutados | Recomendada | IX, X | Decisión del responsable; no implican aprobación académica ni cumplimiento adicional; se conservan plantillas, umbral de 15 minutos y revisión humana por cita |
| 2026-11-09 | 002 importa y consulta hallazgos Qualys; el formulario de revisión con prioridad P1–P4 se difiere al incremento 3, condicionado a la política P1–P4 | Decisión de alcance | IX, XII | Acuerdo de Edwin Perez L., Cristian Quebrada y Ruben Dario Sabogal, confirmado por Edwin Perez L. en esta conversación e incorporado al registro el 2026-11-09. El alcance aprobado de 002 excluye P1–P4; la política sigue pendiente y bloquea el entrenamiento del incremento 3. No se registran fecha de reunión, firmas, actas ni aprobación académica |
| 2026-11-09 | Formato CSV de Qualys definido: archivo filtrado, encabezado inicial de 41 columnas, sin preámbulo ni pie del reporte original; manifiesto opcional para la aceptación local, no campo del formulario | Parámetro | XII | Insumo verificado en `specs/002-qualys-findings-import/spec.md`; el adaptador se implementará en 002. Registrada por instrucción del responsable del producto; no implica aprobación académica |
| Pendiente | Política P1–P4: significado, condiciones, excepciones, datos mínimos y ejemplos | Pendiente | IX, X | Bloquea el entrenamiento del incremento 3 |
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
| 2026-11-11 | Enmienda 1.2.0: alcance general, Qdrant, proveedor API, frontera de datos y acciones controladas | Permanente (propuesta) | I, III, IV, V, VI, VII, XI, XII, XIII, XIV | Solicitud y autorización de Edwin Perez L. registrada en la conversación del 2026-11-11; ratificación de Cristian Quebrada y Ruben Dario Sabogal pendiente; no se inventan acta, firma ni aprobación académica |
| 2026-11-11 | Qdrant local en servidor persistente, preferiblemente Docker Compose, como objetivo de 004; embebido solo para pruebas o alternativa documentada; Chroma en transición | Permanente | III, V | Sustituye la decisión de 2026-11-08 que fijaba Chroma como objetivo permanente; SQLite sigue siendo fuente de verdad; no cambia embeddings en 004 |
| 2026-11-11 | Evaluación de Claude Haiku y DeepSeek como proveedores API; Ollama puede permanecer en transición y para embeddings locales | Parámetro / Pendiente | IV, XI | Identificadores, versiones y precios se verifican al planificar/evaluar 005; no hay proveedor seleccionado ni presupuesto aprobado; sin fallback automático |
| 2026-11-11 | Acción operativa controlada: preparar, previsualizar, confirmar, ejecutar y registrar evidencia; Telegram para evaluación | Permanente | XIV | El modelo propone; la aplicación valida; el destinatario se verifica; una edición invalida la confirmación; aceptado no equivale a recibido/leído; correo y mesa de ayuda posteriores |
| 2026-11-11 | Frontera de datos para proveedores externos y acciones; pruebas iniciales con datos públicos o ficticios | Permanente | XIII | La protección cubre CSV, derivados, activos/IP, preguntas, historial, fragmentos, argumentos/resultados y mensajes; no se autoriza aquí la salida del CSV privado; LangSmith mantiene política independiente |
| 2026-11-11 | 003 suspendida temporalmente; 004–007 se ejecutan antes de retomarla | Decisión de alcance | XII | 0/662 clasificables; política P1–P4 no aprobada; se conservan especificación y checklist; no se cambia la definición de indeterminado |
| Pendiente | Ratificación de la enmienda 1.2.0 por Cristian Quebrada y Ruben Dario Sabogal | Pendiente | Gobernanza | Sin ratificación, 1.2.0 es propuesta revisable y no habilita implementación |
| Pendiente | Presupuesto API para Claude Haiku / DeepSeek | Pendiente | IV, XI | No se activan llamadas pagadas ni se crean cuentas |
| Pendiente | Selección del proveedor API y del canal definitivo de acción | Pendiente | IV, XIV | Requiere evidencia de 005/006; no se declara ganador |

**Version**: 1.2.0 | **Ratified**: 2026-11-08 | **Last Amended**: 2026-11-11

**Estado de ratificación**: propuesta 1.2.0; falta el acuerdo de Cristian Quebrada y Ruben Dario
Sabogal. No se presenta como acuerdo del equipo.
