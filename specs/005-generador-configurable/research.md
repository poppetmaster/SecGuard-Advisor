# Research: Generador configurable (Ollama, DeepSeek y Claude Haiku)

**Fecha**: 2026-11-22
**Alcance**: decisiones de investigación para 005. No implementa, no instala dependencias y no ejecuta
llamadas pagadas.

## Decisiones

### D-01 — Identificadores y capacidades verificados

**Decisión:** fijar como candidatos `claude-haiku-5-5` (Anthropic) y `deepseek-flash` (DeepSeek).
No usar denominaciones comerciales como identificadores de API.

**Evidencia verificada el 2026-11-22:**

| Proveedor | Identificador de API | Versión / contexto | Salida máxima | Precio base |
|---|---|---|---|---|
| Anthropic | `claude-haiku-5-5` | Claude Haiku 5.5; 1M tokens | 128K | Entrada $0.10/MTok (prompt ≤100k); salida $0.50/MTok |
| DeepSeek | `deepseek-flash` | DeepSeek-V4.1-Flash-1017; 1M tokens | 384K | Entrada cache miss $0.15/MTok off-peak, $0.30 peak; salida $0.60/$1.20; cache hit $0.003/$0.006 |

**Fuentes:**

- Anthropic, *Models overview*: <https://platform.claude.com/docs/en/models/overview> (consultado
  2026-11-22). Lista `claude-haiku-5-5` como Claude API ID, contexto 1M, salida 128K.
- Anthropic, *Claude Haiku 5.5*: <https://platform.claude.com/docs/en/models/haiku-5-5/overview>
  (consultado 2026-11-22). Precios por tramo: entrada $0.10/MTok hasta 100k tokens y $0.50/MTok por
  encima; salida $0.50/MTok hasta 100k y $2.50/MTok por encima. Thinking adaptativo; omitir
  `temperature`, `top_p` y `top_k`.
- DeepSeek, *Models & Pricing*: <https://api-docs.deepseek.com/quick_start/pricing> (consultado
  2026-11-22). Modelo `deepseek-flash`, versión DeepSeek-V4.1-Flash-1017, contexto 1M, salida máxima
  384K; precios peak/off-peak y cache hit/miss; JSON Output y Tool Calls disponibles.

**Advertencia:** los precios y modelos cambian. La implementación MUST revalidar los identificadores y
la tarifa antes de aceptar, y MUST registrar la fecha y la fuente de la tarifa usada. No se asume que
«Haiku 5.5» o «DeepSeek V4.1 Flash» sean identificadores válidos por sí mismos.

**Alternativas descartadas:** `claude-haiku-4-5` y `deepseek-chat` como valores por defecto; no son
los candidatos autorizados. Un alias flotante tampoco es reproducible.

### D-02 — Frontera de adaptador y un solo grafo

**Decisión:** definir un protocolo `Generator` con `provider`, `model`, `digest`/`identity`,
`decide(...)`, `generate(...)`, `last_usage` y `close()`. El grafo existente recibe el generador por
inyección; no se crea un grafo por proveedor. La selección se resuelve una vez al arrancar.

**Evidencia:** el código actual ya inyecta `llm_factory` en `create_app` y `start_question_turn`
registra `getattr(generator, "model")` y `digest`. El grafo llama a `generator.decide` y
`generator.generate` sin conocer el proveedor.

**Consecuencia:** los adaptadores solo traducen transporte, esquema, uso y errores. La recuperación,
memoria, herramientas, citas, reparación y abstención permanecen en el grafo.

**Alternativas descartadas:** un grafo distinto por proveedor (duplica comportamiento y divergencia);
selección por turno (viola la decisión autorizada); fallback automático (prohibido).

### D-03 — Salida estructurada y argumentos de herramienta

**Decisión:** conservar los modelos Pydantic `AnswerPayload` y `ToolDecision`, pero sustituir
`ToolDecision.arguments: dict` por un esquema tipado y acotado compatible con `findings_query`
(`origin`, `snapshot_id`, `asset`, `severity`, `severity_level`, `status_group`, `priority`,
`exploitability`, `malware`, `qid`, `cve`, `group_by`, `detail`, `limit`). El adaptador traduce el
esquema al formato de cada proveedor.

**Evidencia:**

- Anthropic Structured Outputs usa `output_config.format` con `type: json_schema`; los objetos deben
  declarar propiedades y `additionalProperties: false`. Un `dict` libre no produce un esquema útil
  (<https://platform.claude.com/docs/en/build-with-claude/structured-outputs>, consultado
  2026-11-22>).
- DeepSeek JSON Output usa `response_format={"type":"json_object"}` y exige la palabra «json» y un
  ejemplo en el prompt; si la salida no es JSON, el contenido se reemplaza por espacios y puede
  quedar vacío (<https://api-docs.deepseek.com/guides/json_mode>, consultado 2026-11-22>).
- Ollama ya usa `with_structured_output(..., method="json_schema")`.

**Consecuencia:** el adaptador de DeepSeek MUST tratar contenido vacío o no JSON como salida inválida
y aplicar la reparación acotada existente. El adaptador de Anthropic MUST transformar el esquema
Pydantic al subconjunto admitido y validar la respuesta localmente.

**Alternativas descartadas:** tool calls nativos como único mecanismo (el flujo actual usa una
decisión estructurada previa y el contrato debe conservarse); un `dict` libre (incompatible con
Anthropic y con validación estricta).

### D-04 — Admisión de contexto por proveedor

**Decisión:** interfaz `PromptCounter` por proveedor:

| Proveedor | Medición previa | Fuente |
|---|---|---|
| Ollama | Tokenizador GGUF y plantilla instalada | Implementación actual |
| Anthropic | `POST /v1/messages/count_tokens` (gratuito) | Documentación oficial |
| DeepSeek | Estimador conservador local con margen configurable, validado contra el uso observado | DeepSeek publica tokenizador fuera de línea; no se incorpora en la primera entrega |

**Evidencia:** Anthropic documenta el endpoint de conteo, que acepta system, tools e imágenes y
devuelve `input_tokens`; es una estimación y es gratuito
(<https://platform.claude.com/docs/en/build-with-claude/token-counting>, consultado 2026-11-22>).
DeepSeek publica un tokenizador fuera de línea y declara que el uso real es el que devuelve la API
(<https://api-docs.deepseek.com/quick_start/token_usage>, consultado 2026-11-22>).

**Regla de privacidad:** el conteo de Anthropic es una llamada externa y solo se permite después de
la compuerta de datos. Si el contenido no está autorizado, no se llama al contador; se usa el
estimador local conservador y, si no cabe, se falla cerrado.

**Consecuencia:** el presupuesto de contexto deja de depender del GGUF para proveedores externos. Se
reduce historial y fuentes con el mismo orden actual; la pregunta y el contexto declarado no se
recortan.

**Alternativas descartadas:** reutilizar el tokenizador GGUF (subestima el tokenizador nuevo de
Anthropic y no aplica a DeepSeek); contar por bytes sin margen (arriesga 400 del proveedor).

### D-05 — Uso, costo y presupuesto

**Decisión:** registrar por llamada los tokens de entrada, salida y caché que reporta el proveedor;
calcular el costo con una tarifa versionada y fechada; si falta el uso, `cost_status=unknown` y
`cost_usd=NULL`. Reservar antes de la llamada el costo máximo (entrada estimada + salida máxima) en
un libro de presupuesto local; liquidar con el uso observado; reconciliar reservas abiertas al
arrancar.

**Fórmulas:**

```text
costo_entrada = tokens_entrada_cache_miss * tarifa_entrada_miss
              + tokens_entrada_cache_hit  * tarifa_entrada_hit
costo_salida  = tokens_salida * tarifa_salida
costo_total   = costo_entrada + costo_salida
```

DeepSeek distingue peak/off-peak y cache hit/miss; Anthropic distingue tramos de prompt ≤100k y
>100k. La tarifa se selecciona con la marca de tiempo UTC de la llamada y la versión de tarifa
registrada.

**Evidencia:** DeepSeek publica precios peak/off-peak y cache hit/miss; Anthropic publica tramos por
longitud de prompt y precios de caché. Ver D-01.

**Consecuencia:** el presupuesto es un límite local, no una garantía del proveedor. Si el proveedor
cobra más por una condición no modelada, el sistema lo registra como diferencia y no promete un tope
exacto. Un presupuesto no aprobado impide las llamadas externas.

**Alternativas descartadas:** estimar costo cero cuando falta uso; reservar solo después de la
llamada (permite sobregiro); confiar en un límite del proveedor sin control local.

### D-06 — Configuración y secretos

**Decisión:** extender `Settings` de pydantic-settings con `generation_provider`, modelo por
proveedor, `SecretStr` para credenciales, límites y presupuesto. Precedencia: variables de entorno >
`.env` > predeterminados. `.env` está ignorado por Git; `.env.example` contiene solo marcadores
vacíos. La validación de arranque falla cerrada y enumera la variable faltante sin imprimir valores.

**Evidencia:** la configuración actual ya usa `SettingsConfigDict(env_file=".env")` y `SecretStr`
para LangSmith; `.env.example` ya declara `LANGSMITH_API_KEY=` vacía.

**Consecuencia:** no se añade un formulario de administración. No se aceptan claves por argumentos de
línea de comandos ni por URL. Los errores de autenticación no incluyen la clave.

**Alternativas descartadas:** leer secretos de SQLite (los mezcla con datos de negocio); un archivo
versionado con claves; variables de entorno únicas para todos los proveedores sin validación.

### D-07 — Frontera de datos y autorización externa

**Decisión:** añadir una autorización explícita por caso (`ExternalProcessingAuthorization`) con
alcance, política, identidad declarada, fecha y revocación. Sin autorización vigente, el proveedor
externo falla con `external_processing_blocked` antes de cualquier llamada. Qualys y sus derivados
nunca se envían. `findings_query` solo se permite con proveedor externo en un caso `fictional_case`
y con `origin=synthetic`; un resultado importado o mixto bloquea el turno con
`external_tool_blocked` y sugiere Ollama.

**Evidencia:** la constitución XIII exige una frontera explícita para CSV, derivados, activos,
preguntas, historial, fragmentos, argumentos y resultados de herramientas; las pruebas iniciales
deben usar datos públicos o ficticios.

**Consecuencia:** la primera entrega externa funciona con corpus público y casos ficticios
autorizados. Los casos privados siguen en Ollama. No se afirma retención cero ni ausencia de
entrenamiento.

**Alternativas descartadas:** autorización implícita por tener credencial; filtrar solo el archivo y
enviar derivados; enviar resultados de `findings_query` «anonimizados» sin política aprobada.

### D-08 — Errores, reintentos y reparación

**Decisión:** normalizar los errores del proveedor a la taxonomía existente y añadir
`provider_auth_error`, `provider_rate_limited`, `external_processing_blocked`,
`external_tool_blocked` y `budget_exceeded`. Sin fallback. Un reintento solo si el proveedor o la
red lo justifican y dentro del presupuesto; la reparación de salida sigue limitada a una.

**Evidencia:** la taxonomía actual en `web/errors.py` y el turno clasifican
`model_unavailable`, `model_timeout`, `invalid_model_output`, `context_budget_exceeded`, etc. El
grafo ya limita reparación y pasos.

**Consecuencia:** el usuario ve un mensaje comprensible y la ejecución conserva el código. Un 401 no
se reintenta. Un 429 respeta `Retry-After` si existe y no excede el presupuesto.

### D-09 — Dependencias

**Decisión:** implementar los adaptadores externos con `httpx` (ya instalado) contra las APIs
documentadas; no añadir SDKs en la primera entrega. Si una capacidad (por ejemplo, transformación de
esquema o conteo) resulta insegura con HTTP directo, se evalúa el SDK oficial en una tarea separada
con justificación y `uv`.

**Evidencia:** `httpx` ya se usa en Ollama, LangSmith y sondas; el proyecto exige `uv` para
dependencias.

**Alternativas descartadas:** añadir `anthropic` y `openai` sin necesidad demostrada; usar SDKs sin
fijar versión.

### D-10 — Modo de razonamiento y latencia

**Decisión:** DeepSeek se configura con razonamiento desactivado por defecto
(`thinking: {type: disabled}`) para conservar la latencia y la salida estructurada; se expone una
opción explícita para activarlo. Anthropic Haiku 5.5 usa thinking adaptativo con `effort` bajo por
defecto; no se envían `temperature`, `top_p` ni `top_k`. Los valores efectivos se registran por
ejecución.

**Evidencia:** DeepSeek documenta thinking activado por defecto y su desactivación; Anthropic
documenta thinking adaptativo y la omisión de parámetros de muestreo.

**Consecuencia:** la comparación debe registrar el modo de razonamiento; no se compara un proveedor
con razonamiento alto contra otro sin razonamiento y se presenta como equivalente.

### D-11 — Comparación reproducible

**Decisión:** un conjunto de diez preguntas públicas o ficticias, fijado antes de medir, ejecutado
con el mismo prompt y el mismo corpus/caso ficticio. Métricas: latencia total, tiempo por llamada,
citas válidas, estructura válida, seguimiento de instrucciones, recomendaciones y costo. Resultados
medidos y expectativas en secciones separadas.

**Evidencia:** la constitución IX y XIII exigen datos públicos/ficticios y evidencia observada; 004
dejó un patrón de calibración/evaluación con criterios fijados antes de medir.

**Consecuencia:** sin credencial o presupuesto, el proveedor se omite con motivo; no se simula. No se
declara un ganador absoluto con diez preguntas.

## Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| El esquema estructurado de Anthropic rechaza un campo | Esquema tipado y validación local; prueba de contrato por proveedor |
| El estimador de DeepSeek subestima tokens | Margen conservador, validación contra uso observado y reducción antes de enviar |
| Una clave aparece en un error | Redacción centralizada y pruebas de escaneo |
| El proveedor cobra más de lo reservado | Registrar diferencia; no prometer tope exacto; presupuesto local conservador |
| El contenido privado se filtra por el historial | Compuerta por caso y minimización antes de construir el prompt |
| El modelo externo no respeta el JSON | Reparación acotada y abstención; no se inventan citas |
| Cambio de precios o retiro de modelo | Tarifa fechada y revalidación obligatoria antes de aceptar |
