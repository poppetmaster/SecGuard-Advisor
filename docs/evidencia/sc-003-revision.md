# SC-003 — Revisión humana de diez afirmaciones normativas

**Estado**: preparado para revisión humana. Las decisiones de esta tabla están **pendientes** y no se
completan en este documento.

**Selección fijada antes de evaluar**: primeras diez afirmaciones normativas explícitas con cita válida,
en este orden: P1 seis funciones, P2 GOVERN, P3 IDENTIFY, P4 PROTECT, P5 DETECT, P6 RESPOND,
P7 RECOVER, P8 AI RMF, P9 integración de riesgos, P10 MAP. Se descartan afirmaciones sin cita y no se
sustituyen por resultados favorables.

**Origen**: instancia de demostración `storage/demo`, casos `d2504098eb3b4f2e9415d187087a4b79` y
`add80facd4fe4a8f9ea9ca6fffb62096`. No se usan bases temporales de aceptación. Las afirmaciones y citas
proceden de respuestas reales del agente; no son texto redactado para la tabla.

**Distinción**: diez citas de una misma afirmación no cuentan como diez afirmaciones. Cada fila es una
afirmación distinta. Una cita con control automático válido no acredita respaldo semántico; eso lo
decide la persona revisora.

## Tabla de revisión

| ID | Ejecución | Respuesta | Afirmación exacta | Documento · versión · localizador | Cita | Auto | Decisión humana | Observación / responsable | Fragmento |
|---|---|---|---|---|---|---|---|---|---|
| SC003-01 | `79e8bd64f34444fcaeca090bd96eaca0` | `6852c7690df64447a0900a2fe48b32bf` | Las seis funciones centrales del NIST Cybersecurity Framework (CSF) 2.0 son: GOVERN (GV), IDENTIFY (ID), PROTECT (PR), DETECT (DE), RESPOND (RS) y RECOVER (RC). | The NIST Cybersecurity Framework (CSF) 2.0 · NIST CSWP 29 · p:31#30 | «There are six CSF Functions: Govern, Identify, Protect, Detect, Respond, and Recover.» | válida | pendiente |  | [abrir](http://127.0.0.1:8000/cases/d2504098eb3b4f2e9415d187087a4b79/documents/da97339adfe145b590431d13dda8f57b/versions/6cf03d59b1644900ac2257d952c2e92c/fragments/cad17597664345129d13917342a1a093?from=consultation) |
| SC003-02 | `910e390b454643a7a45a67b3a25aa2c7` | `808efccaaf0546b38e7993ca9060ecf6` | GOVERN establece que la estrategia, expectativas y políticas de gestión de riesgos cibernéticos se establecen, comunican y monitorean. | The NIST Cybersecurity Framework (CSF) 2.0 · NIST CSWP 29 · p:8#7 | «• GOVERN (GV) — The organization’s cybersecurity risk management strategy, expectations, and policy are established, communicated, and monitored.» | válida | pendiente |  | [abrir](http://127.0.0.1:8000/cases/add80facd4fe4a8f9ea9ca6fffb62096/documents/da97339adfe145b590431d13dda8f57b/versions/6cf03d59b1644900ac2257d952c2e92c/fragments/2ddc0e00882542a283ec5ca6e3c6cb4c?from=consultation) |
| SC003-03 | `910e390b454643a7a45a67b3a25aa2c7` | `808efccaaf0546b38e7993ca9060ecf6` | IDENTIFY establece que los riesgos cibernéticos actuales se comprenden al entender activos y proveedores. | The NIST Cybersecurity Framework (CSF) 2.0 · NIST CSWP 29 · p:8#7 | «• IDENTIFY (ID) — The organization’s current cybersecurity risks are understood. Understanding the organization’s assets (e.g., data, hardware, software, systems, facilities, services, people), suppliers, and related cybersecurity risks enables an organization to prioritize its efforts consistent with its risk management strategy and the mission needs identified under GOVERN.» | válida | pendiente |  | [abrir](http://127.0.0.1:8000/cases/add80facd4fe4a8f9ea9ca6fffb62096/documents/da97339adfe145b590431d13dda8f57b/versions/6cf03d59b1644900ac2257d952c2e92c/fragments/2ddc0e00882542a283ec5ca6e3c6cb4c?from=consultation) |
| SC003-04 | `3dd264741102423fa3b3d8f49bbb2785` | `9064d6fc35b64c728e608a1ce2e94ead` | La función PROTECT establece que se utilizan salvaguardas para gestionar los riesgos cibernéticos de la organización una vez identificados y priorizados los activos y riesgos, con el fin de asegurar esos activos y prevenir o reducir la probabilidad e impacto de eventos adversos. | The NIST Cybersecurity Framework (CSF) 2.0 · NIST CSWP 29 · p:9#8 | «• PROTECT (PR) — Safeguards to manage the organization’s cybersecurity risks are used. Once assets and risks are identified and prioritized, PROTECT supports the ability to secure those assets to prevent or lower the likelihood and impact of adverse cybersecurity events» | válida | pendiente |  | [abrir](http://127.0.0.1:8000/cases/add80facd4fe4a8f9ea9ca6fffb62096/documents/da97339adfe145b590431d13dda8f57b/versions/6cf03d59b1644900ac2257d952c2e92c/fragments/ac88c2da4eec4c3faecc66ebd1261d9b?from=consultation) |
| SC003-05 | `910e390b454643a7a45a67b3a25aa2c7` | `808efccaaf0546b38e7993ca9060ecf6` | DETECT establece que posibles ataques y compromisos cibernéticos se encuentran y analizan. | The NIST Cybersecurity Framework (CSF) 2.0 · NIST CSWP 29 · p:9#8 | «• DETECT (DE) — Possible cybersecurity attacks and compromises are found and analyzed. DETECT enables the timely discovery and analysis of anomalies, indicators of compromise, and other potentially adverse events that may indicate that cybersecurity attacks and incidents are occurring.» | válida | pendiente |  | [abrir](http://127.0.0.1:8000/cases/add80facd4fe4a8f9ea9ca6fffb62096/documents/da97339adfe145b590431d13dda8f57b/versions/6cf03d59b1644900ac2257d952c2e92c/fragments/ac88c2da4eec4c3faecc66ebd1261d9b?from=consultation) |
| SC003-06 | `910e390b454643a7a45a67b3a25aa2c7` | `808efccaaf0546b38e7993ca9060ecf6` | RESPOND establece que se toman acciones respecto a un incidente de ciberseguridad detectado. | The NIST Cybersecurity Framework (CSF) 2.0 · NIST CSWP 29 · p:9#8 | «• RESPOND (RS) — Actions regarding a detected cybersecurity incident are taken. RESPOND supports the ability to contain the effects of cybersecurity incidents.» | válida | pendiente |  | [abrir](http://127.0.0.1:8000/cases/add80facd4fe4a8f9ea9ca6fffb62096/documents/da97339adfe145b590431d13dda8f57b/versions/6cf03d59b1644900ac2257d952c2e92c/fragments/ac88c2da4eec4c3faecc66ebd1261d9b?from=consultation) |
| SC003-07 | `910e390b454643a7a45a67b3a25aa2c7` | `808efccaaf0546b38e7993ca9060ecf6` | RECOVER establece que los activos y operaciones afectados por un incidente de ciberseguridad se restauran. | The NIST Cybersecurity Framework (CSF) 2.0 · NIST CSWP 29 · p:9#8 | «• RECOVER (RC) — Assets and operations affected by a cybersecurity incident are restored. RECOVER supports the timely restoration of normal operations to reduce the effects of cybersecurity incidents and enable appropriate communication during recovery efforts.» | válida | pendiente |  | [abrir](http://127.0.0.1:8000/cases/add80facd4fe4a8f9ea9ca6fffb62096/documents/da97339adfe145b590431d13dda8f57b/versions/6cf03d59b1644900ac2257d952c2e92c/fragments/ac88c2da4eec4c3faecc66ebd1261d9b?from=consultation) |
| SC003-08 | `a83afd2062da4fe680a6e8c786f04a02` | `775b755e714b4e9e8424deaeb1ee8011` | El NIST AI Risk Management Framework (AI RMF) define cuatro funciones centrales: GOVERN, MAP, MEASURE y MANAGE. | The NIST Cybersecurity Framework (CSF) 2.0 · NIST CSWP 29 · p:19#18 | «The AI RMF Core uses Functions, Categories, and Subcategories to describe AI outcomes and help manage risks related to AI.» | válida | pendiente |  | [abrir](http://127.0.0.1:8000/cases/d2504098eb3b4f2e9415d187087a4b79/documents/da97339adfe145b590431d13dda8f57b/versions/6cf03d59b1644900ac2257d952c2e92c/fragments/de40e582635a4385be0aad520d00f89b?from=consultation) |
| SC003-09 | `a06255c45ba64649a3ff247d80ff38c5` | `f95af65778c843b69b2a747137195b35` | Los riesgos de IA se integran en la gestión de riesgos empresariales al tratarlos junto con otros riesgos críticos como ciberseguridad y privacidad, evitando considerarlos de forma aislada para lograr resultados más integrados y eficiencias organizacionales. | Artificial Intelligence Risk Management Framework (AI RMF 1.0) · NIST AI 100-1 · p:13#12 | «Treating AI risks along with other critical risks, such as cybersecurity and privacy, will yield a more integrated outcome and organizational efficiencies.» | válida | pendiente |  | [abrir](http://127.0.0.1:8000/cases/d2504098eb3b4f2e9415d187087a4b79/documents/11312259a3ca4539b5223aafd94d9160/versions/28dfdb4766b94c6aa33905991b569f59/fragments/a0f5b3cbecbd4f32bd85079265718011?from=consultation) |
| SC003-10 | `1986a4ab8daa41a4b71e24807b8bf492` | `c1d29c36a4ff4cb485b81cd5a9362869` | La función MAP (Mapping) establece que se recopila información para prevenir riesgos negativos y fundamentar decisiones iniciales sobre la idoneidad de una solución de IA. | Artificial Intelligence Risk Management Framework (AI RMF 1.0) · NIST AI 100-1 · p:30#29 | «The MAP function is intended to enhance an organization’s ability to identify risks and broader contributing factors.» | válida | pendiente |  | [abrir](http://127.0.0.1:8000/cases/add80facd4fe4a8f9ea9ca6fffb62096/documents/11312259a3ca4539b5223aafd94d9160/versions/28dfdb4766b94c6aa33905991b569f59/fragments/6425247ab2c249e6aa13be858fa3392d?from=consultation) |

## Preguntas de origen

| Ejecución | Pregunta |
|---|---|
| `1986a4ab8daa41a4b71e24807b8bf492` | ¿Qué hace la función MAP del NIST AI Risk Management Framework? |
| `3dd264741102423fa3b3d8f49bbb2785` | ¿Qué establece la función PROTECT del CSF 2.0 y qué tipo de salvaguardas usa? |
| `79e8bd64f34444fcaeca090bd96eaca0` | ¿Cuáles son las seis funciones centrales del NIST Cybersecurity Framework 2.0? |
| `910e390b454643a7a45a67b3a25aa2c7` | Enumera en oraciones separadas qué establece cada una de las seis funciones del CSF 2.0: GOVERN, IDENTIFY, PROTECT, DETECT, RESPOND y RECOVER. |
| `a06255c45ba64649a3ff247d80ff38c5` | ¿Cómo se relacionan los riesgos de IA con la gestión de riesgos empresariales? |
| `a83afd2062da4fe680a6e8c786f04a02` | ¿Qué funciones define el NIST AI Risk Management Framework y cómo se organizan? |

## Cómo abrir cada fragmento

1. Arrancar la instancia de demostración con `make demo` (prepara y sirve `storage/demo`).
2. Abrir el enlace de la columna **Fragmento** (`http://127.0.0.1:8000/...`). El fragmento muestra el
   documento, versión, página o sección y el texto completo.
3. Si el enlace no abre, comprobar que el servidor sigue activo y que el caso indicado existe.

## Cómo registrar la revisión humana

1. Antes de arrancar, exportar `SECGUARD_REVIEWER_NAME="Nombre Apellido"`. Sin esa variable la
   revisión se rechaza con 409 y no se escribe.
2. Abrir la conversación del caso y localizar la respuesta indicada por `message_id` (o la pregunta
   correspondiente).
3. En el bloque de la cita, usar **Respaldo semántico**:
   - «Respaldada por el fragmento» si la cita sostiene la afirmación.
   - «No respaldada» si no la sostiene.
   - Añadir una observación breve si hace falta.
4. Pulsar **Registrar revisión**. El control automático no cambia; la revisión humana queda con autor
   y fecha del servidor.
5. Trasladar el resultado a esta tabla: `pendiente`, `respaldada` o `no respaldada`, con observación y
   responsable. No borrar ni sustituir una afirmación no respaldada para obtener 10 de 10.

## Cómo comunicar el resultado

- Adjuntar esta tabla completada y, si se desea, capturas de las citas.
- Reportar el número de afirmaciones respaldadas, no respaldadas y pendientes.
- Si alguna no está respaldada, informarlo explícitamente. El cierre formal de SC-003 requiere las
  diez decisiones humanas; una revisión de prueba o una identidad automatizada no lo sustituye.


## Resumen de resultado humano

| Métrica | Valor |
|---|---|
| Afirmaciones revisadas | |
| Respaldadas | |
| No respaldadas | |
| Pendientes | |
| Responsable | |
| Fecha | |

No cerrar SC-003 hasta que las diez filas tengan una decisión humana y el resumen esté completo.
