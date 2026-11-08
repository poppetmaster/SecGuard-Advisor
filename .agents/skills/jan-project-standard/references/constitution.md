# Anatomía del `CONSTITUTION.md`

El `CONSTITUTION.md` es la **fuente única de verdad** del proyecto. No es un README
bonito: es el contrato operativo que permite a una persona o a un agente trabajar sin
adivinar. Se **crea al inicio** y se **actualiza en el mismo commit** de cualquier cambio
significativo.

## Reglas de redacción

1. **Escribe la verdad, no el ideal.** Si algo aún no está definido, escribe
   `PENDIENTE` o `EN EVALUACIÓN` en lugar de inventarlo.
2. **Un hecho vive en un solo lugar.** La constitución es la referencia; el README
   enlaza hacia ella, no la duplica.
3. **Registra el *porqué*, no solo el *qué*.** El historial de decisiones es lo más
   valioso: fecha + decisión + motivo.
4. **Sé concreto.** Rutas de archivo, comandos reales, versiones exactas.
5. **Mantén el tono imperativo y el idioma del proyecto** (por defecto: español; el
   código y los identificadores en inglés).
6. **Marca lo pendiente** con checklists `- [ ]` para que sea accionable.

## Estructura canónica (secciones)

El orden importa: va de lo estable (identidad) a lo cambiante (tareas).

### 0. Directiva de mantenimiento (encabezado)

El bloque que recuerda que el archivo se actualiza. Es lo primero que ve el agente.

### 1. Identidad y propósito del proyecto

Tabla de identidad + `### Propósito` + `### No-propósito`. El no-propósito evita que un
agente (o colaborador) se desvíe hacia lo que el proyecto no es.

### 2. Alcance

`### Dentro del alcance` y `### Fuera del alcance (por ahora)`. Fases si aplica
(ej. `Fase 1`, `Fase 2` con estado ✅/🚧/⏳).

### 3. Stack técnico

Tabla `Categoría | Tecnología`. Marca explícitamente lo `EN EVALUACIÓN` o `PENDIENTE`.
Incluye la **regla dura** de `uv` (prohibido `pip`/`requirements.txt`).

### 4. Estructura del repositorio

Árbol `text` anotado con la responsabilidad de cada carpeta. Debe coincidir con la
realidad tras cada cambio estructural.

### 5. Convenciones de código

PEP 8/257, tipado, docstrings, naming, patrón AAA en pruebas, idioma, reglas propias
(p. ej. "las cifras monetarias son enteros", "cero lógica de negocio en la UI").

### 6. Calidad y automatización

Tabla de herramientas y comandos; reglas de CI (verde antes de fusionar, sin
`--no-verify`, dependencias solo con `uv add`).

### 7. Arquitectura / dominio (cuando aplique)

Diagramas de flujo de datos, capas, invariantes de dominio, "hechos no negociables",
gotchas que ya costaron tiempo. Es la sección que impide repetir errores.

### 8. Repositorio y Git

Remoto (SSH), rama principal, estrategia de ramas, Conventional Commits, identidad
git automática.

### 9. Flujo diario (commit + push)

Bloque `bash` numerado y copiable. Ajustado a la naturaleza del proyecto (app, curso,
investigación).

### 10. Historial de decisiones técnicas

Tabla `Fecha | Decisión | Motivo`. Es un log append-only: nunca borres filas.

### 11. Notas y tareas pendientes / roadmap

Checklists por tema. Siguiente paso inmediato destacado cuando exista.

### 12. Configuración local (no trackear)

Identidad Git, remotos, credenciales. Se documenta **como nota**, nunca como archivo
versionado con secretos.

---

## Plantilla

El scaffolder genera `assets/templates/base/CONSTITUTION.md` con esta estructura y
marcadores `<!-- ... -->` en las zonas a completar. Consulta el archivo directamente:

```text
<SKILL_DIR>/assets/templates/base/CONSTITUTION.md
```

## Ejemplo de historial de decisiones

```markdown
| Fecha | Decisión | Motivo |
|-------|----------|--------|
| 2026-10-01 | Adoptar `uv` como gestor único | Reproducibilidad; prohibido `pip`/`requirements.txt` |
| 2026-10-01 | Adoptar Conventional Commits | Historial legible y automatizable |
| 2026-10-02 | Migrar de `requests` a `httpx` | Unificar cliente HTTP con `TestClient` de FastAPI |
| 2026-10-03 | Usar puerto 5050 para el servidor de tracking | En macOS el puerto 5000 lo ocupa AirPlay (403) |
```

## Ejemplo de invariante de dominio

```markdown
## 3. Invariantes del dominio

- Los montos se manejan como **enteros en COP** (nunca `float`, nunca centavos).
- La versión de la UVT se lee de una constante versionada por año, no se hardcodea.
- Toda cifra debe rastrearse a un documento fuente; si no, se marca como `manual`.
```

## Antipatrones (evitar)

- Constitución genérica que podría ser de cualquier proyecto.
- Duplicar el README dentro de la constitución (o viceversa).
- Documentar el ideal sin marcar lo que falta.
- Cambiar arquitectura y **no** registrar la decisión ni actualizar la estructura.
- Guardar secretos o datos personales reales en el repo.
