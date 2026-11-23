# Revisión de 005, Entrega 3 — 2026-11-22

Podemos continuar con la especificación de 006. Los defectos R1–R3 están corregidos; 005 tiene aceptación local parcial, con comparación externa real pendiente. No se requiere repetir la planificación de 005.

## Verificación realizada

- Repositorio limpio al iniciar; último commit observado: `feaed5a`.
- Inicio y reintento comparten perfil, autorización, registro y construcción del contexto. El contexto público excluye el contexto privado del caso.
- Ambos adaptadores propagan el timeout al transporte HTTP.
- El registro persiste proveedor, identidad, ventana de contexto, salida máxima, timeout y autorización efectivos.
- Ejecuté las pruebas de reintento externo, comparación, contratos DeepSeek/Anthropic, persistencia de uso y ledger: **32 passed**, 14 advertencias, 1,57 s. Sin llamadas externas ni cambios a datos del usuario.
- Los reportes guardados documentan la comparación Ollama real: diez preguntas, ocho aciertos de cita esperada, dos abstenciones y media de 13.948 ms. Es una prueba pequeña con corpus ficticio, sin evaluación semántica humana.
- La regresión completa reportada por OpenCode es 649 pruebas rápidas y 37 de integración aprobadas. Revisé sus reportes; no repetí la integración de veinte minutos.
- Existen reportes separados de simulación y de omisión de proveedores externos. T039 sigue pendiente y no se presenta como aprobada.

## Pendientes que no bloquean especificar 006

1. T039: presupuesto explícito global y por turno, credenciales locales y posterior comparación externa real. No hay evidencia para afirmar que DeepSeek o Claude mejoren la latencia o calidad.
2. AGENTS.md conserva frases obsoletas: aceptación de 004 pendiente y proveedor API no implementado. Deben alinearse con 004 aceptada localmente y 005 implementada con aceptación parcial. Es una corrección documental acotada.
3. El título de `005-ultimo-resultado.md` todavía dice «Entrega 3 en cierre»; puede aclararse como «aceptación local parcial; T039 pendiente».

## Prompt único para continuar

```text
/speckit.specify

Prepara la funcionalidad 006 de SecGuard Advisor: destinatarios y notificación operativa controlada, con Telegram como primer canal de evaluación. Lee AGENTS.md, la constitución vigente, docs/planificacion/hoja-ruta-mejoras-profesor.md, los contratos de 002 y 005, docs/planificacion/005-ultimo-resultado.md, docs/planificacion/handoff-005.md y docs/planificacion/revision-codex-005-entrega-3.md.

005 tiene aceptación local parcial: R1–R3 corregidos y Ollama real medido; T039 externa real sigue pendiente. Esto permite preparar 006 sin declarar aceptados los proveedores externos. 003 continúa suspendida. No vuelvas a planificar 005 ni solicites de nuevo decisiones ya registradas.

Antes de la especificación, corrige únicamente las frases obsoletas de estado en AGENTS.md: 004 ya está aceptada localmente; los adaptadores API de 005 existen, pero no tienen aceptación externa real. Alinea el título de 005-ultimo-resultado.md con su aceptación parcial. Conserva el historial y no marques T039 completada.

RESULTADO DE 006

El agente podrá preparar una notificación defensiva basada en evidencia del caso. Una persona revisa el contenido y el destinatario y confirma la acción antes de cualquier envío. La aplicación valida y ejecuta; el modelo no puede enviar directamente ni inventar destinatarios.

ALCANCE MÍNIMO

- Registro por formulario de destinatarios vinculados al caso: nombre visible, canal, identificador de destino, consentimiento, verificación, estado activo y datos mínimos de auditoría. No solicites correo, teléfono u otros datos que Telegram no necesite.
- Token del bot en configuración local ignorada por Git o entorno; nunca en SQLite, HTML, respuestas, logs o trazas. No incluyas un formulario que revele el token.
- Flujo de verificación del destino explícito. Distingue comprobación técnica del chat y consentimiento de la persona: una no prueba la otra. Cualquier mensaje de prueba también requiere confirmación humana.
- Preparación de acción con destinatario existente, evidencia, snapshot/filtros cuando apliquen, contenido propuesto y procedencia. La preparación no envía mensajes.
- Interfaz Flowbite gratuito integrada en el caso: destinatarios, acciones preparadas, vista previa, confirmación, cancelación e historial. Conserva los indicadores de carga y prevención de doble envío existentes.
- Una modificación de contenido, destinatario o evidencia invalida la confirmación anterior. El envío usa exactamente la versión confirmada.
- Estados explícitos: preparada, envío solicitado, aceptada por el proveedor, fallida e incierta; cancelación previa al envío. No llames entregado o leído a un mensaje solo porque Telegram lo aceptó.
- Prevención persistente de duplicados ante doble clic, concurrencia y reinicio. Si el resultado del envío es incierto, no reintentes automáticamente ni prometas entrega exactamente una vez.
- Evidencia local de acción, versión confirmada, destinatario, identidad declarada, fecha y resultado del proveedor. No confundas identidad declarada con autenticación.
- La acción funciona con Ollama y el contrato de generador común. No depende de P1–P4 ni del entrenamiento. No amplía la autorización externa de 005.

CONTENIDO Y PRUEBAS

- Primer alcance y aceptación: datos públicos o ficticios y un chat de prueba autorizado. No autorices por esta especificación enviar CSV Qualys privado, sus derivados, activos/IP privados, documentos o contenido privado a Telegram ni a proveedores de IA. Si la hoja de ruta sugiere agregados de Qualys, deja explícito que su salida privada sigue sin autorizarse.
- Planifica pruebas deterministas de preparación sin envío, confirmación de versión, destinatario revocado/inactivo/no verificado, aislamiento por caso, doble envío, fallo conocido, timeout incierto y reinicio durante el envío.
- Incluye navegación, teclado, móvil, carga y mensajes de error comprensibles.
- La prueba real con Telegram requiere bot y destino de prueba configurados, consentimiento y confirmación explícita posterior del mensaje concreto. No envíes nada en este paso.
- Correo, WhatsApp, mesa de ayuda, recordatorios, envíos masivos, autenticación nueva y remediación automática quedan fuera del mínimo.

ENTREGA DOCUMENTAL

Crea la especificación y checklist de 006 con el mecanismo instalado de Spec Kit. Define historias, requisitos comprobables, datos de entrada/salida, estados y aceptación. No generes todavía plan, tareas, código, migraciones ni dependencias. Deja las decisiones técnicas para plan y plantea solo decisiones de producto realmente faltantes; no inventes aprobaciones, cuentas ni consentimientos.

Guarda un resumen completo en docs/planificacion/006-ultimo-resultado.md y un handoff en docs/planificacion/handoff-006.md: archivos creados, alcance, decisiones respaldadas, preguntas pendientes, siguiente comando y condiciones de prueba real. Toda la información necesaria para revisión debe quedar en archivos, sin depender de capturas ni consola.

Conserva los datos existentes y el estado parcial de 005. No llames APIs externas, no envíes mensajes, no hagas push ni crees remotos. Finaliza al completar esta especificación.
```
