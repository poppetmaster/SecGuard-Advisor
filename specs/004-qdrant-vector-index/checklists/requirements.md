# Specification Quality Checklist: Migración del índice documental a Qdrant

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-11-11
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs) — se nombra Qdrant y Docker Compose
  como alcance de gobierno; no se fijan versiones, topología, payload ni configuración
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders — con vocabulario técnico acotado al cambio de backend
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic — miden reconstrucción, citas, aislamiento,
  persistencia y fallos; la tecnología objetivo es parte del alcance aprobado
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification — las decisiones de versiones, colecciones,
  payload, Docker Compose y backups se difieren expresamente al plan

## Governance Readiness

- [x] La especificación registra la ratificación comunicada por Edwin Perez L. el 2026-11-11.
- [x] La autorización de Edwin Perez L. se reconoce como registrada; no se vuelve a solicitar.
- [ ] No constan los acuerdos de Cristian Quebrada y Ruben Dario Sabogal, acta, firma ni aprobación
  académica — **evidencia de gobierno pendiente; no es un defecto de la especificación**
- [x] La simplificación de 004 está registrada: reconstrucción limpia, sin exportación de vectores,
  escritura dual, selección permanente, comparación obligatoria ni retorno a Chroma.
- [x] La funcionalidad 003 permanece suspendida y fuera de alcance.
- [x] No se presenta Qdrant como implementado ni se declara una mejora no medida.

## Instance and Lifecycle

- [x] Namespace de instancia estable aplicado a colecciones, aliases, generaciones, reportes y locks.
- [x] `SECGUARD_INSTANCE_ID` explícito, sin generación por arranque; marcador con hash de storage
  para detectar copias o namespaces incompatibles.
- [x] Primer documento: creación incremental de generación/alias solo tras validar; fallo sin alias
  nuevo; reintento sin duplicados.
- [x] Alcance vacío vs índice ausente: caso sin documentos, caso esperado sin alias, público
  esperado sin alias, público vacío y Qdrant inaccesible diferenciados.
- [x] Lock de archivo entre procesos, por instancia; rechazo mutuo ingesta/reconstrucción y
  liberación tras interrupción.
- [x] Escenario de dos instancias con el mismo `case_id` y contenidos distintos.

## Deferred Technical Decisions

Estas decisiones se resolvieron en `/speckit.plan`; se listan para trazabilidad:

- [x] Versiones de servidor y cliente Qdrant (`1.20.0` servidor y cliente).
- [x] Topología de colecciones, filtros y aislamiento por instancia y alcance.
- [x] Esquema de payload e índices de payload.
- [x] Configuración de Docker Compose, volumen y acceso por loopback.
- [ ] Backups, snapshots y recuperación de Qdrant; sin retorno a Chroma — se resuelve en la
  implementación con reconstrucción desde SQLite; no se exige snapshot de Qdrant en 004.
- [x] Estrategia de reconstrucción: regeneración de embeddings con el mismo modelo local.
- [x] Calibración del umbral de recuperación con la métrica y configuración de Qdrant.
- [x] Conjunto reproducible de preguntas y evaluación funcional sin comparación obligatoria.
- [x] Campos de evidencia para Qdrant, versión, índice, generación y error clasificado.

## Reconciliation After Consistency Analysis

Correcciones aplicadas al análisis de consistencia documental (2026-11-22), sin implementar nada:

- [x] Taxonomía de errores con códigos y estados propios para índice, disponibilidad y locks.
- [x] Propagación del fallo de índice en el turno: sin abstención y sin generación documental.
- [x] Fingerprint del marcador basado en ruta canónica + identidad de instancia, sin hashear
  contenido; rutas separadas entre volumen del servidor y control de la aplicación.
- [x] Cinco estados observables de reconstrucción con fuente definida y sin confundir lock con éxito.
- [x] Frontera de atomicidad Qdrant/SQLite y recuperación convergente.
- [x] Puntos huérfanos reportados como discrepancia y nunca resueltos como cita.
- [x] Interfaz operativa de reconstrucción: comando y reporte; sin pantalla web de administración.
- [x] Retiro de Chroma agrupado con fixtures, pruebas y dependencias en una sola unidad de trabajo.
- [x] Ingesta del corpus público en Qdrant dentro del corte que declara recuperación pública.
- [x] Actualización de `.specify/memory/constitution.md` asignada al commit del cambio de backend.
- [x] Pruebas de mapeo de errores en rutas escritas antes de adaptar la fábrica y las rutas.
- [x] Evaluación final dependiente del umbral calibrado ya aplicado y congelado, con conjunto separado.
- [x] Lock integrado en los escritores iniciales (documentos, corpus y reconstrucción) antes de
  declararlos operativos.
- [x] Registro de propietario del lock con operación e intento; metadatos obsoletos ignorados y
  distinción entre ingesta activa, reconstrucción activa y último resultado terminal.
- [x] Consulta de estado de solo lectura (`--status`) definida con sus seis valores, salida para
  ausencia de estado y ausencia de efectos de escritura; implementación y pruebas asignadas en
  T024/T025 y verificadas en T031.
- [x] Constitución en dos etapas: «backend sustituido; aceptación pendiente» al retirar Chroma y
  «implementado y aceptado localmente» solo con la aceptación observada.
- [x] Descripción del Corte 5 alineada con las dependencias reales de sus tareas (Corte 1 y Corte 2).
- [x] Reporte terminal ilegible con contrato explícito: salida 2, mensaje en `stderr`, `state: null`,
  `last_terminal: null` y `error`, sin presentarlo como `not_started` ni reparar el reporte.
- [x] Resolvedor único de estado en `retrieval/status.py`, consumido por el reporte y por `--status`,
  con pruebas propias antes de sus consumidores.
- [x] Errores de `--status` completos: `instance_configuration_invalid`, `lock_unreadable` y
  `status_report_unreadable` con salida 2, `stderr`, JSON con `state: null`, `last_terminal: null` y
  `error`, sin crear archivos ni reparar información.

## Notes

- La especificación está **documentalmente completa y planificable** con la ratificación del
  responsable registrada. La evidencia de acuerdo de Cristian Quebrada y Ruben Dario Sabogal no
  consta y se registra sin inventarla.
- Plan, diseño y tareas están generados; el análisis de consistencia documental está aplicado. No se
  implementó código, no se instalaron dependencias, no se ejecutaron pruebas y no se declaró
  aceptación.
- Los vectores actuales no están persistidos en SQLite. La reconstrucción los regenera con el mismo
  modelo local; no se exportan desde Chroma.
- No hay migración de vectores, escritura dual, selección permanente de backend, comparación
  obligatoria Chroma/Qdrant ni retorno a Chroma.
- Los archivos y datos Chroma existentes no se borran en 004.
- No se inventaron métricas, umbrales observados ni resultados de comparación. Los umbrales
  propuestos se distinguen de los observados.
- No se incluyeron datos privados, filas Qualys, IP, activos ni títulos privados.
- La funcionalidad 003 sigue suspendida y su política P1–P4 no está aprobada.
