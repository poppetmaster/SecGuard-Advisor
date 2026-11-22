# Quickstart: Generador configurable (005)

**Estado**: referencia de implementación. Ningún comando de este documento se ejecutó en la
preparación. No se instalan dependencias, no se realizan llamadas pagadas y no se modifica `storage/`.

## 1. Selección local

La configuración vive en `.env` (ignorado por Git). `.env.example` solo contiene marcadores vacíos.
Precedencia: variables de entorno > `.env` > predeterminados.

```bash
# Ollama local (predeterminado, sin credencial externa)
SECGUARD_GENERATION_PROVIDER=ollama
SECGUARD_GENERATION_MODEL=qwen3.5:9b
SECGUARD_GENERATION_MAX_OUTPUT_TOKENS=1200
SECGUARD_GENERATION_TIMEOUT_SECONDS=90
SECGUARD_GENERATION_REASONING=off
```

```bash
# DeepSeek Flash (requiere credencial y presupuesto aprobado)
SECGUARD_GENERATION_PROVIDER=deepseek
SECGUARD_GENERATION_MODEL=deepseek-flash
DEEPSEEK_API_KEY=...            # solo en .env local, nunca en Git
SECGUARD_EXTERNAL_BUDGET_USD=0  # 0 bloquea; un valor > 0 debe estar aprobado
SECGUARD_EXTERNAL_RUN_BUDGET_USD=0
```

```bash
# Claude Haiku 5.5 (requiere credencial y presupuesto aprobado)
SECGUARD_GENERATION_PROVIDER=anthropic
SECGUARD_GENERATION_MODEL=claude-haiku-5-5
ANTHROPIC_API_KEY=...
SECGUARD_EXTERNAL_BUDGET_USD=0
SECGUARD_EXTERNAL_RUN_BUDGET_USD=0
```

Si falta la credencial o el proveedor es inválido, la aplicación no arranca y muestra la variable
faltante sin imprimir el valor.

## 2. Arranque local

```bash
make qdrant-up
uv run alembic upgrade head
make dev
```

`/healthz` debe informar `database`, `ollama` y `qdrant`. Un proveedor externo no se presenta como
disponible si falta credencial o presupuesto.

## 3. Flujo de consulta

El flujo no cambia:

1. crear un caso;
2. cargar un documento público o ficticio;
3. preguntar;
4. abrir la cita y la evidencia de ejecución;
5. revisar el proveedor, modelo, tokens, duración y costo.

Con un proveedor externo y un caso sin autorización, la consulta se bloquea antes de la llamada con
`external_processing_blocked`.

## 4. Autorización externa (solo datos públicos o ficticios)

La autorización se registra por caso, con alcance `public_corpus` o `fictional_case`, identidad
declarada, política y fecha. No se infiere de la credencial ni de una variable global. En 005 no se
autoriza `private_case`.

```bash
# Otorgar (revoca la autorización vigente anterior del caso)
uv run python scripts/external_authorization.py --case <case_id> \
  --scope fictional_case --authorized-by "Revisora local" --note "Prueba ficticia"

# Consultar la autorización vigente
uv run python scripts/external_authorization.py --list --case <case_id>

# Revocar
uv run python scripts/external_authorization.py --case <case_id> --revoke
```

El comando no imprime secretos ni contenido del caso. No hay formulario web en 005.

Con proveedor externo, `findings_query` solo se permite en un caso `fictional_case` y con
`origin=synthetic`. Un resultado importado o mixto falla con `external_tool_blocked`; para hallazgos
importados se usa Ollama.

## 5. Presupuesto

- `SECGUARD_EXTERNAL_BUDGET_USD=0` bloquea las llamadas externas.
- Un valor mayor debe corresponder a un presupuesto aprobado; no se inventa.
- La reserva se crea antes de la llamada y se liquida con el uso observado.
- Si falta el uso, el costo se muestra como desconocido.
- El presupuesto es un límite local, no una garantía del proveedor.

## 6. Pruebas

```bash
make check             # unitarias, contrato y aceptación rápida
make test-integration  # Ollama real y Qdrant
```

Pruebas externas (no ejecutar en esta preparación):

```bash
# Solo con credencial y presupuesto explícitos.
# Sin ellos, la prueba se omite con motivo.
uv run pytest -m external -q
```

## 7. Comparación reproducible

Conjunto fijo de diez preguntas públicas o ficticias, mismo prompt y mismo corpus/caso. Métricas:
latencia, citas válidas, estructura válida, seguimiento de instrucciones, recomendaciones y costo.
Los resultados medidos se guardan separados de las expectativas. Sin credencial o presupuesto, el
proveedor se omite y no se simula.

## 8. Verificación de modelos

Antes de implementar y antes de aceptar, revalidar:

- `claude-haiku-5-5` en <https://platform.claude.com/docs/en/models/haiku-5-5/overview>
- `deepseek-flash` en <https://api-docs.deepseek.com/quick_start/pricing>

Registrar fecha, fuente y tarifa aplicada. No usar denominaciones comerciales como identificadores.

## 9. Seguridad

- No versionar `.env`.
- No registrar claves en logs, SQLite, trazas, respuestas ni capturas.
- No enviar Qualys, filas, CVE, activos ni resultados de herramientas a proveedores externos.
- No afirmar retención cero ni garantías de privacidad sin evidencia.
- Mantener `LANGSMITH_TRACING=false` salvo autorización independiente.
