# Diagramas de arquitectura con Archify

[Archify](https://github.com/tt-a1i/archify) convierte una descripción (o un repositorio) en
un **diagrama interactivo autocontenido** (HTML con SVG inline, temas claro/oscuro, pan/zoom,
búsqueda, trazado de relaciones y exportación). El resultado es un único archivo HTML que se
comparte sin instalar nada, más un **JSON tipado** que es la fuente reproducible.

> 💡 **Cuándo usarlo:** cuando un proyecto necesite un mapa de arquitectura, un flujo, una
> secuencia, un data flow o un ciclo de vida que deba vivir versionado y enlazarse desde el
> README (documentación viva). Es la forma estándar de cumplir "README con arquitectura".

## Instalación (skill externa)

```bash
# Instalar la skill Archify globalmente (OpenCode, Claude Code, Cursor, Codex…)
npx skills add tt-a1i/archify -g

# Instalación explícita no interactiva (ejemplo Cursor)
npx -y skills add tt-a1i/archify --skill archify --agent cursor --global --copy --yes
```

Requiere **Node.js** disponible para los validadores/renderizadores del skill.

## Los 5 tipos de diagrama

| Tipo | Para qué |
|------|----------|
| `architecture` | Componentes, servicios, almacenamiento, límites de confianza/infraestructura. |
| `workflow` | Procesos, CI/CD, aprobaciones, runbooks, tool calls. |
| `sequence` | Llamadas API, ciclo de una petición, fallback de caché, trazas asíncronas. |
| `dataflow` | Pipelines, ETL/ELT, linaje, sensibilidad y consumidores. |
| `lifecycle` | Máquinas de estado, reintentos, esperas y estados terminales. |

Ante la duda: `node bin/archify.mjs guide "<escenario>" --json`.

## Flujo recomendado

1. **Instalar** la skill (arriba).
2. **Elegir el tipo** según el sistema (tabla anterior).
3. **Generar** con un prompt al agente, pidiendo explícitamente evidencia del repositorio
   cuando el diagrama deba reflejar el código real:

   ```text
   Analiza este repositorio y usa Archify para crear un diagrama de arquitectura de runtime
   de alto nivel. Muestra 8–12 componentes centrales, un camino principal, dependencias
   externas y límites de confianza. Deja el detalle en tarjetas, no en más aristas.
   ```
4. **Validar** (perfil `showcase`, 0 errores y 0 advertencias en las 9 comprobaciones):

   ```bash
   node bin/archify.mjs validate architecture docs/arquitectura.json --quality showcase --json
   ```
5. **Entregar** el HTML (comando de aceptación final; no describe éxito si el exit code ≠ 0):

   ```bash
   node bin/archify.mjs deliver architecture docs/arquitectura.json docs/arquitectura.html \
     --quality showcase --json
   ```
6. **Evidencia en navegador** (no modifica ni re-renderiza el HTML):

   ```bash
   node bin/archify.mjs visual-check docs/arquitectura.html --json
   ```

   `deliver` prueba comprobaciones deterministas; `visual-check` prueba comportamiento en un
   navegador real; la revisión **perceptual** requiere un humano o un revisor con visión.

## Convención de archivos

Los artefactos viven en `docs/` (o en la carpeta canónica de documentación del proyecto) con
esta nomenclatura:

| Archivo | Rol |
|---------|-----|
| `docs/arquitectura.json` | **Fuente tipada** (versionada, reproducible). |
| `docs/arquitectura.html` | Diagrama interactivo autocontenido (versionado). |
| `docs/arquitectura.visual-check.json` | Recibo de la verificación en navegador. |
| `docs/arquitectura.visual-check.html` | Sidecar de la verificación. |
| `docs/arquitectura.visual-check.<WxH>.<tema>.png` | Capturas por tamaño y tema (p. ej. `2048x1320.dark.png`). |

> El JSON **siempre** se versiona: es la fuente. El HTML también (es el artefacto que se
> comparte). Las capturas *visual-check* sirven de evidencia y para el README.

## Enlace desde el README

Se embebe una captura (tema oscuro, tamaño grande) que **enlaza al HTML interactivo**:

```markdown
## 🗺️ Arquitectura del Repositorio

Mapa de arquitectura interactivo (autocontenido, generado con Archify). Ábrelo en el
navegador: `docs/arquitectura.html`.

[![Arquitectura del proyecto (tema oscuro)](docs/arquitectura.visual-check.2048x1320.dark.png)](docs/arquitectura.html)

Incluye tema claro/oscuro, pan/zoom, búsqueda, focus, trazado de relaciones y exportaciones.
```

## Idioma

`meta.locale` controla solo la interfaz del visor: `en` y `zh-CN` vienen integrados. Para
**español**, aporta `meta.translations` (ver `examples/locales/es.json` del skill) o el visor
cae a inglés y lo advierte. El contenido que tú escribes nunca se traduce automáticamente.

## Buenas prácticas

- Un diagrama = una pregunta. No mezcles runtime, despliegue y datos en una sola figura.
- Empieza con **una ruta principal** y ≤ 12 nodos primarios; el resto va en tarjetas.
- **Conserva los nombres reales** (servicios, comandos, rutas de API, protocolos).
- Regenerar = editar el JSON y volver a `validate` + `deliver`; nunca editar el HTML a mano.
- Revisa el HTML a 1440×900, 1600×1000, 1920×1080 y 2048×1320 (sin scroll horizontal).

## Checklist

- [ ] `npx skills add tt-a1i/archify -g` ejecutado (o el skill ya está instalado).
- [ ] Tipo elegido entre architecture/workflow/sequence/dataflow/lifecycle.
- [ ] `docs/arquitectura.json` versionado y validado en `--quality showcase`.
- [ ] `docs/arquitectura.html` entregado con `deliver` (SIN editar a mano).
- [ ] `visual-check` corrido y capturas generadas.
- [ ] README con la sección de arquitectura enlazando `docs/arquitectura.html`.
- [ ] Decisión registrada en `CONSTITUTION.md` (herramienta y ubicación del diagrama).
