# Feature Specification: Informe ejecutivo visual y notificaciones mediante Telegram

**Feature Branch**: `006-informe-ejecutivo-telegram` (no creada en este paso)

**Created**: 2026-11-23

**Status**: Especificación corregida (FR-023, idempotencia entre modos, verificación de contactos,
manifiesto de contenido aprobado, generación recuperable, revalidación por componente, contrato de
síntesis y defaults de presentación) y reconciliada con la constitución 1.4.0.
El plan técnico vive en `plan.md` y las tareas en `tasks.md`; no hay implementación, envíos reales,
llamadas pagadas ni aceptación declarada.

**Input**: «Crea la especificación de 006 para SecGuard Advisor: “Informe ejecutivo visual y
notificaciones mediante Telegram”. Transformar una importación confirmada de Qualys en un informe
ejecutivo comprensible, visual y verificable, consultable en la aplicación, descargable como PDF y
enviable por Telegram, con envío manual y envío automático mediante una regla previamente activada
por la persona responsable.»

## Contexto y límites de esta especificación

- 006 se apoya en la importación Qualys confirmada de 002 y en la evidencia de ejecución y la
  interfaz de 004/005. No reabre 003, no implementa P1–P4 y no usa la prioridad conjunta como P1.
- La autorización de esta instrucción cubre **especificar, planificar y reconciliar documentación**,
  no enviar mensajes, llamar a servicios pagados, instalar dependencias ni implementar código.
- El informe se genera desde una **instantánea confirmada** de un caso. Una importación en staging,
  rechazada o cancelada nunca produce informe ni notificación.
- Se mantienen las limitaciones de 005 documentadas; no se exige otra evaluación pagada para
  especificar 006.
- Quedan fuera de alcance: correo, WhatsApp, mesa de ayuda, envío periódico, remediación automática,
  entrenamiento y autenticación multiusuario. Telegram es el único canal de esta especificación.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Generar y revisar un informe ejecutivo verificable (Priority: P1)

Una persona responsable abre un caso con una importación Qualys confirmada, genera un informe
ejecutivo y revisa en la web las cifras, la instantánea, los focos de atención, las limitaciones y la
procedencia de las recomendaciones. Descarga un PDF con una composición propia para impresión. La
vista web y el PDF representan el mismo informe y la misma instantánea.

**Why this priority**: sin un informe comprensible y verificable no hay nada que notificar; además, la
concordancia entre cifras, gráficas y PDF es la base de confianza de todo 006.

**Independent Test**: con una instantánea ficticia confirmada, generar un informe, comparar sus
tarjetas y gráficas con los datos persistidos, descargar el PDF y comprobar que conserva la misma
instantánea, filtros, cifras y contenido sin depender de la pantalla.

**Acceptance Scenarios**:

1. **Given** una importación confirmada con registros pendientes, Fixed, severidades 1–5 e
   indicadores conocidos/desconocidos, **When** se genera el informe, **Then** las tarjetas muestran
   cada categoría con su definición, los Fixed y la revisión manual se muestran por separado y ningún
   indicador solapado se suma como categoría excluyente.
2. **Given** un informe generado, **When** se abre su versión web y se descarga su PDF, **Then**
   ambos muestran el mismo identificador, instantánea, filtros, cifras, títulos de gráficas,
   recomendaciones y limitaciones.
3. **Given** una instantánea anterior, **When** se genera un informe histórico, **Then** las cifras
   se calculan solo sobre esa instantánea y no cambian al importar un CSV posterior.
4. **Given** que la síntesis de IA falla o no está disponible, **When** se genera el informe,
   **Then** se conserva un informe factual identificado como «Sin síntesis de IA», con cifras,
   gráficas y limitaciones, sin inventar explicaciones ni recomendaciones.

---

### User Story 2 - Configurar destinos y enviar manualmente (Priority: P2)

Una persona responsable configura un contacto o grupo de Telegram con alias, identificador de chat,
estado de verificación y consentimiento, y lo vincula a casos autorizados. Desde el caso revisa el
informe, los destinatarios y el contenido exacto que saldrá; confirma y envía el resumen y el PDF. El
sistema registra el resultado por destinatario.

**Why this priority**: el envío manual es el primer uso seguro de Telegram y permite validar destino,
contenido y evidencia sin automatizar decisiones.

**Independent Test**: con un contacto ficticio no verificado, comprobar que no se puede enviar; con
un contacto verificado y un informe de prueba, confirmar y comprobar que solo se envía el contenido
mostrado y que cada destinatario tiene un estado registrado.

**Acceptance Scenarios**:

1. **Given** un contacto sin verificación o sin consentimiento activo, **When** se intenta enviar
   un informe, **Then** el envío se bloquea con un motivo explícito y no se realizan solicitudes.
2. **Given** un informe y un contacto verificado vinculado al caso, **When** la persona revisa y
   confirma el contenido y el destino, **Then** se envía el resumen y el PDF y se registra el estado
   por destinatario.
3. **Given** una confirmación preparada, **When** se edita el informe, el destinatario o el contenido
   permitido antes de enviar, **Then** la confirmación anterior deja de ser válida y se exige una
   nueva.
4. **Given** un doble clic, una recarga o una repetición del mismo evento, **When** se procesa el
   envío, **Then** no se crea un segundo envío para el mismo informe y destinatario.
5. **Given** una versión ya enviada por una regla automática, **When** la persona intenta enviarla
   manualmente al mismo destinatario, **Then** el sistema reutiliza el envío registrado y no
   duplica el contenido ya aceptado.
6. **Given** un contacto no verificado y un informe bloqueado para envío, **When** la persona
   solicita el código de verificación desde la interfaz, **Then** el código se envía al contacto y
   el bloqueo del informe no impide la verificación.

---

### User Story 3 - Activar una regla de envío automático (Priority: P3)

Una persona responsable activa previamente una regla para un caso: destinatarios verificados,
disparador de importación confirmada, filtros, contenido permitido, nivel de detalle, autor declarado
y versión. Cuando una importación confirmada coincide con la regla, el sistema genera el informe y
envía el resumen y el PDF, registrando que fue automático y sin revisión humana individual.

**Why this priority**: automatizar sin una autorización previa explícita convertiría una acción
externa en una excepción silenciosa.

**Independent Test**: con una regla activa para un caso y contacto ficticios, confirmar una
importación que coincide y comprobar el envío registrado; con la regla desactivada o una
importación no confirmada, comprobar cero envíos.

**Acceptance Scenarios**:

1. **Given** una regla activa con destinatarios verificados y autor declarado, **When** se confirma
   una importación que cumple sus condiciones, **Then** se genera un informe y se envía por el canal
   configurado, identificado como automático.
2. **Given** una regla desactivada, modificada sin reactivación o con destinatario no verificado,
   **When** se confirma una importación, **Then** no se envía nada y el motivo queda registrado.
3. **Given** una importación en staging, rechazada, cancelada o solo previsualizada, **When** coincide
   con una regla, **Then** no se genera ni se envía ninguna notificación.
4. **Given** un envío automático con resultado incierto, **When** la aplicación se reinicia, **Then**
   el evento queda persistido y no se reintenta ciegamente ni se presenta como entregado.
5. **Given** una versión ya enviada manualmente al mismo destinatario, **When** una regla
   coincidente se evalúa, **Then** no se crea un segundo envío.

---

### User Story 4 - Auditar versiones y resultados de notificación (Priority: P3)

Una persona revisa el historial de informes y envíos de un caso: versión inmutable, instantánea,
autor, fecha, regla, destinatarios, contenido confirmado y estado por destinatario. Puede distinguir
un informe preparado, una solicitud enviada, una aceptación del proveedor, un fallo y un resultado
incierto.

**Why this priority**: la trazabilidad permite explicar qué se envió, cuándo y con qué evidencia sin
confundir aceptación con entrega o lectura.

**Independent Test**: generar dos versiones del mismo informe y dos envíos con resultados distintos;
comprobar que el historial conserva cada versión y cada estado sin reescribir la anterior.

**Acceptance Scenarios**:

1. **Given** un informe generado, **When** se regenera después de cambiar filtros o texto, **Then**
   se crea otra versión y la anterior conserva sus datos, PDF y contenido.
2. **Given** un envío aceptado por Telegram, **When** se consulta la evidencia, **Then** se muestra
   «aceptado» y no se afirma entrega ni lectura.
3. **Given** un fallo del PDF después de aceptar el resumen, **When** se registra el resultado,
   **Then** se marca resultado parcial y no se reenvía automáticamente el resumen ya aceptado.

### Edge Cases

- Síntesis de IA ausente, fallida o que no cumple el esquema: informe factual, sin texto inventado.
- PDF no generado o corrupto: el informe web y los datos se conservan; el envío se bloquea o queda
  parcial según lo ya aceptado.
- Importación nueva: no modifica informes históricos ni sus PDF; una regeneración crea otra versión.
- Snapshot sin activos identificables: se informa la limitación; no se inventan activos.
- Registros con varios CVE: los conteos no se multiplican por CVE.
- Indicadores vacíos: se muestran como desconocidos/no informados; no se interpretan como negativos
  ni como ausencia de amenaza.
- Destinatario eliminado, revocado, no verificado o desvinculado del caso: bloqueo previo al envío.
- Regla modificada, desactivada o con destinatarios distintos: requiere nueva activación.
- Confirmación invalidada por edición del texto, filtros, PDF o destinatarios.
- Doble clic, recarga, reimportación idéntica o repetición del evento: no duplicar.
- Cruce entre modo manual y automático para la misma versión y destinatario: reutilizar el evento
  existente, no duplicar y registrar el cruce en la evidencia.
- Código de verificación expirado, consumido o con demasiados intentos: rechazar sin enviar informe.
- Manifiesto de contenido desactualizado tras editar el PDF, el texto, la política o los
  destinatarios: bloquear la ejecución y exigir nueva confirmación o reactivación.
- Reinicio durante una evaluación automática: reutilizar la versión y los eventos ya creados.
- Reinicio tras solicitud enviada y antes de conocer el resultado: estado incierto persistido.
- Timeout del proveedor: no reintento ciego; se conserva el evento y se solicita intervención.
- Telegram acepta el resumen pero rechaza el PDF: resultado parcial sin reenviar el resumen.
- Filtros o gráficas sin datos: mensaje específico; no se presenta un cero parcial como completo.
- Caso con datos sintéticos o ficticios: el informe y el mensaje lo identifican como tales.
- Acceso desde móvil o escritorio: lectura y acciones disponibles sin depender de un tamaño de
  pantalla.

## Requirements *(mandatory)*

### Informe ejecutivo

- **FR-001**: El sistema MUST permitir generar un informe ejecutivo solo desde una importación
  Qualys **confirmada** de un caso; staging, rechazo, cancelación o vista previa MUST NOT generar
  informe ni notificación.
- **FR-002**: Cada informe MUST fijar caso, alcance, identificador, fecha, instantánea, filtros y
  versión de informe. La instantánea y los datos de una versión MUST ser inmutables.
- **FR-003**: La vista web y el PDF de una misma versión MUST representar la misma instantánea,
  filtros, cifras, agrupaciones, títulos y contenido gerencial.
- **FR-004**: El informe MUST mostrar tarjetas separadas para: registros pendientes (Active, New y
  Re-Opened), severidad crítica nivel 5, severidad alta nivel 4, activos distintos afectados,
  explotabilidad positiva, malware positivo y ambos indicadores positivos. Fixed y los datos que
  requieren revisión MUST mostrarse por separado.
- **FR-005**: Los indicadores solapados MUST conservarse como distribuciones independientes; el
  sistema MUST NOT sumarlos como categorías excluyentes ni presentar la bandera conjunta como P1.
- **FR-006**: La severidad MUST conservar la escala del proyecto 1–5 y declarar que no es CVSS, QDS,
  TruRisk ni P1–P4.
- **FR-007**: El informe MUST incluir una gráfica de distribución de severidad 1–5, una de activos
  con mayor concentración de registros críticos/altos y dos distribuciones independientes de
  explotabilidad y malware (positivo, negativo/no informado, indeterminado).
- **FR-008**: Las gráficas de activos MUST distinguir los activos principales del total, declarar
  cualquier recorte y usar alias cuando corresponda. La web MUST ofrecer etiquetas, unidades,
  tooltips y tabla alternativa; el PDF MUST usar imágenes estáticas nítidas generadas desde los
  mismos datos y opciones.
- **FR-009**: Cada gráfica MUST tener un título explicativo y comunicar una conclusión concreta; no
  se admiten gráficos 3D, decorativos o redundantes.
- **FR-010**: El informe MUST incluir resumen ejecutivo breve, focos de atención justificados,
  recomendaciones propuestas con procedencia y limitaciones/cobertura/faltantes.
- **FR-011**: Las cifras y agrupaciones MUST calcularse de forma determinista sobre los datos
  persistidos de la instantánea, no por el modelo. Toda afirmación cuantitativa del texto MUST
  construirse desde campos estructurados del dataset con valor, unidad y denominador; que un número
  exista en el dataset no basta para validar la afirmación. El modelo solo puede redactar
  explicaciones y propuestas usando datos y fuentes autorizados.
- **FR-012**: El informe MUST distinguir hechos del CSV, respaldo documental y propuestas del agente.
  La síntesis MUST cumplir el contrato `report-synthesis-v1`: las cifras se renderizan desde el
  dataset y las referencias documentales se validan por existencia e identidad. La validación
  literal de una cita NO garantiza respaldo semántico; una recomendación sin respaldo semántico
  comprobado MUST mostrarse como propuesta. Si la síntesis falla, MUST conservar un informe factual
  rotulado «Sin síntesis de IA» con cifras, gráficas y limitaciones.
- **FR-013**: Un campo vacío MUST mostrarse como desconocido/no informado y no como ausencia de
  amenaza. No se inferirá remediación por ausencia en otro reporte ni novedad sin identidad estable.
- **FR-014**: El PDF MUST ser una composición propia de aproximadamente 2–3 páginas, legible, sin
  cortes, páginas vacías, texto diminuto ni dependencia de enlaces a localhost; el detalle técnico
  puede separarse.
- **FR-015**: Regenerar un informe MUST crear una nueva versión inmutable; el historial anterior MUST
  conservarse aunque se importe otro CSV.

### Contactos y configuración

- **FR-016**: Administración MUST incluir «Contactos y canales» con alias, identificador de chat,
  estado y procedimiento de verificación, consentimiento/fecha/estado y casos autorizados.
- **FR-017**: El sistema MUST NOT solicitar teléfonos ni correos innecesarios. El token del bot MUST
  permanecer en configuración local excluida de Git, fuera del almacenamiento persistente de datos
  de la aplicación y fuera de la interfaz.
- **FR-018**: El caso MUST incluir «Informes y notificaciones» con destinatarios, modalidad manual o
  automática, condiciones, contenido permitido e historial de informes y envíos.
- **FR-019**: La modalidad MUST configurarse por caso/regla, no solo por contacto. Un contacto
  vinculado a varios casos MUST respetar la autorización de cada caso.
- **FR-020**: Por defecto, el PDF y el mensaje MUST excluir IP, nombres internos, Results completos y
  el título del caso cuando se marque como sensible (`include_case_title=false`); MUST usar alias
  cuando corresponda y mostrar de forma visible qué datos saldrán del equipo.
- **FR-021**: Un destinatario MUST estar verificado, con consentimiento vigente y vinculado al caso
  antes de cualquier envío de **informe**. La verificación del contacto MUST registrarse con fecha,
  estado y evidencia del procedimiento, sin inferirse por tener un identificador de chat. El envío
  del código de verificación es un envío técnico distinto y MUST NOT quedar bloqueado por los
  requisitos que aplican al envío de informes.

### Envío manual, reglas y eventos

- **FR-022**: El flujo manual MUST ser generar → revisar informe/destinatarios/contenido → confirmar →
  enviar → registrar resultado por destinatario.
- **FR-023**: El sistema MUST NOT enviar al seleccionar un archivo, validarlo, previsualizarlo ni
  mostrar el informe. Confirmar una importación MUST NOT enviar en modo manual: ese modo exige una
  confirmación individual posterior. La confirmación de una importación PUEDE disparar el envío
  automático únicamente si existe una regla activa, vigente y coincidente; sin regla válida no se
  envía nada.
- **FR-024**: La confirmación MUST corresponder al informe, versión, destinatarios, filtros y
  contenido concretos. Cualquier edición posterior MUST invalidarla y exigir nueva confirmación.
- **FR-025**: Una regla automática MUST declarar caso, destinatarios verificados, disparador,
  filtros/condiciones, contenido y detalle permitido, versión, autor declarado, fecha de activación y
  posibilidad de desactivación.
- **FR-026**: La activación de la regla MUST ser autorización previa solo para envíos que coincidan
  exactamente con sus condiciones. Cambiar destinatarios, condiciones o contenido permitido MUST
  exigir reactivación.
- **FR-027**: La regla solo MUST evaluarse después de una importación confirmada que cumpla sus
  condiciones; MUST NOT enviar desde staging, rechazo, cancelación, vista previa o una importación
  idéntica repetida.
- **FR-028**: Cada envío automático MUST registrarse como generado automáticamente, con la versión y
  regla usadas, sin presentarlo como revisión humana individual.
- **FR-029**: El mensaje MUST incluir un resumen breve y el PDF de la misma versión, comprensible por
  sí mismo sin enlaces a localhost.
- **FR-030**: Por destinatario se MUST registrar informe/versión, modo, regla, contenido confirmado,
  estado, fecha e identificador de mensaje cuando exista.
- **FR-031**: Los estados MUST distinguir preparado, envío solicitado, aceptado por Telegram, fallido
  y resultado incierto. Aceptado MUST NOT presentarse como entregado o leído.
- **FR-032**: Si el resumen se acepta y el PDF falla, MUST registrarse un resultado parcial y MUST NOT
  reenviarse el resumen ya aceptado.
- **FR-033**: El envío MUST identificarse por informe/versión y destinatario, con independencia
  del modo. Una misma versión MUST NOT generar dos envíos al mismo destinatario por la vía manual y
  la automática, ni por doble clic, recarga, reimportación idéntica o repetición del evento. El modo
  es metadato de la evidencia y MUST NOT formar parte de la identidad del envío.
- **FR-034**: El evento de envío MUST persistirse para recuperación tras reinicio. Un fallo MUST NOT
  revertir la importación confirmada.
- **FR-035**: Un timeout incierto MUST NOT provocar reintento ciego; el sistema MUST conservar el
  estado y solicitar intervención. No se promete entrega exactamente una vez.
- **FR-036**: La confirmación individual y la autorización previa por regla MUST quedar diferenciadas
  en la documentación y en la evidencia del envío. La activación de una regla no se presentará como
  excepción silenciosa ni como confirmación individual.

### Seguridad, privacidad y trazabilidad

- **FR-037**: El contenido de los informes enviados MUST limitarse a los datos autorizados del caso y
  a la política de contenido de la regla; MUST excluir Qualys completo, Results, IP, nombres internos
  y secretos.
- **FR-038**: La vista, el PDF y los mensajes MUST aislarse por caso y no mezclar activos, registros o
  contactos de otro caso.
- **FR-039**: Los errores y resultados de envío MUST registrarse con códigos seguros y sin secretos,
  cabeceras, tokens, contenido del PDF ni datos privados adicionales.
- **FR-040**: El sistema MUST impedir envíos de **informe** a destinos no verificados, no autorizados,
  desactivados o desvinculados del caso. La comprobación MUST repetirse inmediatamente antes de cada
  componente (resumen y PDF), tanto en modo manual como automático. El código de verificación se rige
  por FR-045.
- **FR-041**: Las pruebas iniciales MUST usar dobles y destinos/contenido ficticios. El envío real de
  prueba requerirá autorización posterior con destino y contenido concretos.
- **FR-042**: Cada evento MUST descomponerse en los componentes `resumen` y `documento`. Un
  componente ya aceptado MUST NOT reenviarse; un reintento posterior solo PUEDE cubrir componentes
  fallidos o no aceptados y MUST registrarse como nuevo intento del mismo evento.
- **FR-043**: La evaluación de una regla MUST ser idempotente por regla/versión e importación
  confirmada. Repetir el evento, reconfirmar el mismo CSV o reiniciar durante la evaluación MUST NOT
  crear un segundo envío.
- **FR-044**: Si una versión ya tiene un envío al mismo destinatario, otra regla o el flujo manual
  MUST reutilizar el evento existente y MUST NOT duplicar el contenido ya aceptado. El cruce de
  modos MUST quedar registrado en la evidencia del evento reutilizado.
- **FR-045**: El envío del código de verificación MUST solicitarse explícitamente desde la interfaz
  y MUST persistir un desafío con hash del código, fecha de creación, expiración, número de intentos,
  consumo y relación con el contacto y el bot. MUST limitar solicitudes y reintentos. MUST NOT
  registrar el código en claro ni el token. Un contacto no verificado MUST poder recibir el código
  aunque el envío de informes esté bloqueado.
- **FR-046**: La confirmación manual y la ejecución MUST compartir un manifiesto canónico de
  contenido aprobado que identifique la versión del informe, el texto saliente, el hash del PDF, la
  política de contenido y los destinatarios. Una modificación relevante del informe, del PDF, de la
  política o de los destinatarios MUST invalidar la confirmación manual o exigir reactivar la regla.
  Antes de enviar, la ejecución MUST comprobar que los artefactos coinciden con el manifiesto.
- **FR-047**: La generación automática MUST usar una clave de generación estable y única por
  evaluación. La creación o recuperación de la versión MUST reutilizar esa clave y MUST funcionar
  aunque el proceso termine antes o después de guardar el vínculo con la evaluación; MUST NOT crear
  una versión nueva para eludir la idempotencia. Los estados de resumen y PDF MUST ser independientes:
  un componente aceptado MUST NOT reenviarse y uno incierto MUST NOT reintentarse automáticamente.
- **FR-048**: Cada corte de implementación MUST poder verificarse sin tablas ni servicios previstos
  para un corte posterior. El corte de envío manual MUST incluir la persistencia de eventos,
  componentes e intentos y la infraestructura del ejecutor; el corte automático MUST reutilizarla.

### Key Entities *(include if feature involves data)*

- **Instantánea Qualys confirmada**: importación inmutable de un caso, con secuencia, origen, fecha y
  registros; fuente de todos los cálculos del informe.
- **Informe ejecutivo**: documento lógico de un caso y una instantánea, con identificador, alcance,
  filtros, resumen, focos, recomendaciones, limitaciones y estado de síntesis.
- **Versión de informe**: revisión inmutable de datos, texto, configuración, gráficas y PDF; una
  regeneración crea una nueva versión. La generación automática usa una clave de generación única por
  evaluación para recuperar la misma versión.
- **Contacto/canal**: alias, chat de Telegram, verificación, consentimiento, estado y casos
  autorizados; no contiene el token del bot.
- **Desafío de verificación**: hash del código, relación con contacto y bot, expiración, intentos y
  consumo; no contiene el código en claro ni el token.
- **Manifiesto de contenido aprobado**: versión del informe, texto saliente, hash del PDF, política de
  contenido y destinatarios; base común de confirmación y ejecución.
- **Síntesis del informe**: salida opcional `report-synthesis-v1` con hechos calculados, referencias
  documentales, propuestas y `claim_refs`; si falla o no está autorizada, se conserva el informe
  factual.
- **Regla de notificación**: configuración versionada por caso con destinatarios, disparador, filtros,
  contenido permitido, autor, fecha y estado activo.
- **Evento de notificación**: intento de envío de una versión a un destinatario, con modo, regla,
  contenido confirmado, estado, fechas e identificador del proveedor si existe.
- **Confirmación**: decisión humana ligada a una versión, destinatarios y contenido concretos; se
  invalida al editar.
- **Artefacto PDF**: representación imprimible e inmutable de una versión, con datos y configuración
  asociados.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Para una misma versión, el 100 % de las cifras, filtros, instantánea, títulos y
  contenido gerencial coincide entre la vista web y el PDF.
- **SC-002**: El PDF ejecutivo ocupa aproximadamente 2–3 páginas y no presenta imágenes cortadas,
  texto diminuto, páginas vacías ni contenido dependiente de una pantalla o de localhost.
- **SC-003**: El 100 % de los informes y envíos generados desde staging, rechazo, cancelación o vista
  previa es cero.
- **SC-004**: El 100 % de los envíos a contactos no verificados, no consentidos, desactivados o no
  vinculados al caso se bloquea antes de cualquier solicitud externa.
- **SC-005**: Cualquier combinación de doble clic, recarga, reimportación idéntica, repetición del
  evento o cruce entre modo manual y automático produce como máximo un envío aceptado por
  informe/versión y destinatario.
- **SC-006**: El 100 % de los envíos automáticos registra la regla, versión, autor, destinatarios y
  contenido; ningún envío automático se presenta como revisión humana individual.
- **SC-007**: Tras importar otro CSV, el 100 % de los informes históricos conserva su instantánea,
  cifras, texto y PDF sin cambios.
- **SC-008**: El informe y el mensaje por defecto no contienen IP, nombres internos, Results completos
  ni secretos; el contenido permitido puede verificarse antes de enviar.
- **SC-009**: Si la síntesis falla, el 100 % de los informes conserva cifras, gráficas y limitaciones
  y se identifica como «Sin síntesis de IA».
- **SC-010**: Una persona puede completar el recorrido manual de revisión y envío de un informe de
  prueba en menos de 3 minutos, sin ayuda externa y con confirmación explícita.
- **SC-011**: El 100 % de los envíos de informe verifica que la versión, el texto, el hash del PDF,
  la política y los destinatarios coinciden con el manifiesto aprobado; una discrepancia produce cero
  envíos.
- **SC-012**: Un contacto no verificado puede recibir el código de verificación aunque el envío de
  informes esté bloqueado; el 100 % de los desafíos persiste solo el hash, expira y limita intentos,
  y en ningún caso se guarda el código en claro ni el token.

## Out of Scope

- Correo electrónico, WhatsApp, mesa de ayuda y cualquier canal distinto de Telegram.
- Envío periódico, programado o por temporizador; solo envío manual confirmado o automático por
  una importación confirmada que cumpla una regla activa.
- Remedición automática, modificación de sistemas, cierre de vulnerabilidades o prioridades P1–P4.
- Entrenamiento, ajuste de modelos, promoción de proveedores o evaluación pagada adicional.
- Autenticación multiusuario, gestión de identidades y permisos de red.
- Nuevos cálculos de vulnerabilidades fuera de la instantánea Qualys y de las fuentes existentes.

## Assumptions

- La persona responsable configura y verifica el destino de Telegram mediante un procedimiento
  local registrado; la verificación no se infiere del identificador de chat. El mecanismo concreto de
  verificación se definirá en el plan.
- El token del bot permanece en configuración local excluida de Git; no se guarda en el almacenamiento
  persistente de datos de la aplicación, no se muestra y no se incluye en evidencia.
- El informe principal usa 5 activos con mayor concentración de registros críticos/altos como valor
  predeterminado, con desempate determinista; el informe declara el total y el recorte. No requiere
  una decisión bloqueante adicional; una revisión de producto posterior puede ajustarlo.
- La síntesis de IA es opcional. Si falla, el informe factual se genera igualmente y el envío
  automático puede usar ese fallback si la regla lo permite, siempre identificado.
- El PDF se compone localmente a partir de los mismos datos y opciones de gráficas; la tecnología de
  renderizado se elegirá en el plan sin CDN ni servicios externos de imágenes.
- El historial de informes y eventos se conserva localmente; una versión no se sobrescribe.
- No existe autenticación multiusuario: la identidad del autor y del revisor es declarada, no
  autenticada. La aprobación de la regla es una decisión local de la persona responsable.
- La activación de una regla es autorización previa para envíos que coincidan exactamente; no
  sustituye la confirmación individual en el flujo manual. Esta decisión del responsable se registrará
  en la documentación y en el registro de decisiones sin afirmar acuerdo del equipo ni aprobación
  académica.
- Las pruebas iniciales usan dobles y datos ficticios. No se enviarán mensajes reales hasta una
  autorización posterior con destino y contenido concretos.
- 005 conserva sus limitaciones documentadas; la especificación de 006 no exige otra evaluación
  pagada ni declara aceptación externa.

## Decisiones registradas

- **Confirmación individual frente a regla previa (registrada el 2026-11-23)**: el flujo manual exige
  confirmación del contenido y destino concretos; una regla activa es autorización previa para los
  envíos que cumplan exactamente sus condiciones. La regla registra autor declarado, versión, fecha,
  destinatarios verificados y contenido permitido; cualquier cambio exige reactivación. La decisión
  quedó en el registro de decisiones de la constitución 1.4.0, que también alineó el principio XIV y
  las prohibiciones de arquitectura. No constan acuerdos de Cristian Quebrada y Ruben Dario Sabogal,
  acta, firma ni aprobación académica.
- **Identidad de envío (registrada el 2026-11-23)**: informe/versión + destinatario, sin el modo. El
  modo manual o automático es metadato de evidencia y no permite duplicar.
