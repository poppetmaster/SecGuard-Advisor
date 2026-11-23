# 005 — Configuración de IA desde la interfaz

**Fecha**: 2026-11-22
**Rama**: `005-generador-configurable`
**Estado**: formulario implementado y validado; 005 con aceptación local parcial; proveedores externos
no aceptados; T039 real pendiente.

## Ruta

`/settings/ai` — «Configuración de IA» en el grupo **Administración** del menú principal, fuera del
contexto de un caso y disponible en escritorio y móvil. «Administración» solo agrupa opciones; no
implica autenticación ni roles.

## Funcionalidad

- Selección explícita: Local — Ollama, DeepSeek, Claude — Anthropic.
- Modelo asociado, máximo de tokens de salida (solo externos) y tiempo máximo por llamada.
- Perfiles externos: **4096 tokens por defecto**, editables en el formulario; Ollama conserva su
  reserva automática. La migración `c1d2e3f4a5b6` eleva perfiles externos guardados por debajo de
  4096.
- **Ollama**: sin claves, sin presupuesto monetario y sin cuota comercial. La reserva de salida se
  administra automáticamente dentro del contexto técnico; no se solicita cuota de tokens. Se muestra
  «Ejecución local; sin cobro por tokens de API» sin afirmar costo operativo total cero.
- Guardado en SQLite; sin editar código ni reiniciar el servidor.
- Perfiles independientes por proveedor; cambiar de proveedor no arrastra modelos ni sobrescribe
  parámetros de otro.
- Resumen de configuración activa, presupuestos externos global y por turno (USD) y disponibilidad
  de credenciales.
- Claves: solo «Clave configurada» / «Clave pendiente» / «No requiere». No se envían valores,
  fragmentos ni máscaras; presencia no equivale a credencial válida ni conexión verificada.
- Conexión: «No verificada». Guardar no verifica conexión ni autoriza gasto.
- Proveedor externo con presupuesto cero:
  «Configurado; consultas externas bloqueadas hasta autorizar presupuesto.»

## Precedencia

1. Selección guardada en `ai_configuration`/`ai_provider_profiles`.
2. Si no existe, valores iniciales de `Settings`/`.env`.
3. `.env` conserva claves, endpoints y presupuestos; la interfaz no lo modifica.
4. Los límites externos se validan contra el proveedor/modelo seleccionado, no contra el proveedor
   inicial de la aplicación.
5. `SECGUARD_GENERATION_MODEL` vacío usa el modelo predeterminado del proveedor cuando no hay
   selección guardada.
6. Cada turno toma una instantánea; una consulta en curso conserva proveedor, modelo, límites,
   timeout y autorización.

## Variables de `.env` (sin secretos)

```text
SECGUARD_GENERATION_PROVIDER=ollama|deepseek|anthropic
SECGUARD_GENERATION_MODEL=              # vacío = predeterminado del proveedor
SECGUARD_GENERATION_MAX_OUTPUT_TOKENS=1200
# Perfiles externos: 4096 tokens de salida por defecto, editable en el formulario.
SECGUARD_GENERATION_TIMEOUT_SECONDS=90
DEEPSEEK_API_KEY=                       # solo en .env local
ANTHROPIC_API_KEY=                      # solo en .env local
SECGUARD_EXTERNAL_BUDGET_USD=0
SECGUARD_EXTERNAL_RUN_BUDGET_USD=0
```

## Identificadores

| Proveedor | Modelo confirmado | Fuente | Fecha |
|---|---|---|---|
| Ollama | `qwen3.5:9b` | Modelo local configurado | 2026-11-22 |
| DeepSeek | `deepseek-flash` | <https://api-docs.deepseek.com/quick_start/pricing> | 2026-11-22 |
| Anthropic | `claude-haiku-5-5` | <https://platform.claude.com/docs/en/models/haiku-5-5/overview> | 2026-11-22 |

Un identificador no confirmado se acepta como elección explícita, se marca «Identificador no
confirmado» y no declara conexión aprobada. Un modelo confirmado de otro proveedor se rechaza.

## Resultados observados

```text
make check
  → 677 passed, 37 deselected, 17 warnings
```

| Prueba | Resultado |
|---|---|
| `tests/unit/test_ai_config_service.py` | 9 passed |
| `tests/contract/test_ai_settings_routes.py` | 12 passed |
| `tests/unit/test_ai_config_turn.py` | 4 passed |
| `tests/contract/test_chat_resource_cleanup.py` | 3 passed |
| Regresión R1–R3 | verde dentro de `make check` |

Playwright (servidor local con almacenamiento temporal, `.env` real solo leído):

- `/settings/ai` carga sin configuración guardada y muestra valores de `.env`.
- Selección DeepSeek actualiza modelo/credencial y guarda 64 tokens / 12.5 s.
- Mensaje de presupuesto cero visible; no hay llamadas externas.
- Cambio a Ollama y regreso a DeepSeek conserva 64/12.5 del perfil DeepSeek.
- Móvil 390×844: menú general, foco en cerrar, Escape, sin overflow (`scrollWidth == clientWidth`).
- Consola: 0 errores.
- Capturas: `settings-desktop-local.png`, `settings-desktop-external.png`,
  `settings-saved-deepseek.png`, `settings-mobile.png`, `settings-mobile-menu.png`. No contienen
  claves.

## Garantías conservadas

- Autorización externa por caso y bloqueo sin autorización.
- Restricción a `public_corpus`/`fictional_case`; Qualys y derivados bloqueados.
- Presupuesto con reserva y resultados inciertos conservadores.
- LangSmith independiente; `LANGSMITH_TRACING=false`.
- Embeddings locales y Qdrant sin cambios.
- Sin fallback automático.

## Limitaciones

- No se ejecutaron llamadas externas reales; las claves están configuradas pero no hay presupuesto
  autorizado en esta instrucción.
- Ollama funciona con presupuesto externo cero o agotado y no crea reservas económicas externas.
- El cierre de recursos propios se probó en éxito, error de modelo y fallo de preparación.
- Guardar no prueba la conexión ni el modelo; no hay botones de prueba automática.
- No se hace conteo remoto durante el guardado.
- T039 real sigue pendiente.

## Archivos principales

```text
src/secguard_advisor/ai_config/service.py
src/secguard_advisor/web/routes/ai_settings.py
src/secguard_advisor/web/templates/ai_settings/{index,_panel,_fields}.html
src/secguard_advisor/web/templates/components/{navigation,icon}.html
src/secguard_advisor/web/routes/chat.py
src/secguard_advisor/web/app.py
src/secguard_advisor/db/models.py
alembic/versions/f7a8b9c0d1e2_add_ai_configuration.py
tests/unit/test_ai_config_service.py
tests/contract/test_ai_settings_routes.py
tests/unit/test_ai_config_turn.py
```
