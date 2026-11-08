# Presentaciones con Slidev (proyectos de curso)

Estándar para repositorios que incluyen presentaciones del curso. Se apoya en
[Slidev](https://sli.dev/) (Markdown + Vue + Tailwind) y se gestiona con **pnpm**,
mientras el resto del proyecto usa **`uv`**.

## Un solo monolito Slidev

> **Regla:** **un único** proyecto Slidev en `slides/` con **un solo** `package.json` y
> `pnpm-lock.yaml`. Cada clase vive en `slides/pages/claseN.md` y se importa en
> `slides/slides.md` con `src: ./pages/claseN.md`. Componentes, layouts, estilos y assets
> son compartidos.

```text
slides/
├── slides.md              # entry point maestro (importa todas las clases) + Hub
├── pages/claseN.md        # una clase por archivo
├── components/            # componentes Vue compartidos
├── layouts/               # layouts propios (uao-cover, two-cols-header, three-cols-header)
├── public/img/claseN/     # assets por clase (nomenclatura claseN_img_YY.ext)
├── styles.css
├── package.json
├── pnpm-lock.yaml
└── Makefile               # install, dev, build, export, format
```

## Frontmatter obligatorio

```yaml
---
theme: seriph
title: "Clase N - Título Descriptivo"   # OJO: entrecomillar títulos con ':'
info: |
  ## Clase N: Título Descriptivo
  Nombre del curso
routeAlias: claseN
transition: slide-left
mdc: true
---
```

- `routeAlias` habilita la URL directa `http://localhost:3030/claseN`.
- **Gotcha YAML:** un `title` con `: ` sin comillas rompe `slidev format` con un error
  opaco (*Document with errors cannot be stringified*). Entrecomilla siempre.

## Reglas de sintaxis (inquebrantables)

| Regla | Especificación |
|-------|----------------|
| Separador | `---` entre diapositivas. |
| Interacción | `<v-click>` / `<v-clicks>` en listas y tarjetas; **prohibidos muros de texto**. `v-click` solo en nodos hoja, nunca en un contenedor padre que envuelva `<v-clicks>`. |
| Código | Resaltado por pasos con anotaciones de línea: ` ```python {1-3|5-8} `. |
| Notas del orador | Comentarios `<!-- Notas: ... -->` (tecla `P`). |
| Native-First | Prohibidos `<p>`, `<b>`, `<strong>` y `<div>` decorativos **donde MDC parsea markdown**: usa `**negrita**`, listas y atributos MDC `{.text-sm}`. |
| Zona raw | Dentro de un bloque HTML **sin líneas en blanco** (cards compactas), CommonMark/MDC **no** parsea markdown: los `**` y `{.cls}` salen literales. Ahí el HTML inline (`<b>`, `<p class>`, `<code>`, `<br/>`) es correcto y queda exceptuado. |
| Columnas | 2 columnas independientes → `layout: two-cols-header` (`::left::`/`::right::`/`::bottom::`). 3 columnas → `three-cols-header`. Grid Tailwind reservado solo para galerías N-cards bajo un único `<v-clicks>` y para el Hub. |
| Imágenes | Viven en `slides/public/img/claseN/` y se referencian con ruta absoluta `/img/claseN/...`. Nomenclatura `clase<N>_img_<YY>.<ext>`. Usa `<img src>` en HTML (no `![]()`), porque el pipeline de Slidev compila `![]()` como import. |
| Legibilidad | Cada bloque de código ≤ ~23 líneas visibles; si es más largo, pártelo en slides numeradas (`1/3`, `2/3`, …). |
| Siglas | Expande cada sigla en su **primera aparición visible**: `Nombre Completo (SIGLA)`. |

## Hub de navegación

`slides/slides.md` incluye, tras la portada, una diapositiva **Hub** con una tarjeta por
sesión en `grid grid-cols-2`. Clases con deck → `<Link to="/claseN">` (componente nativo
de Slidev, navegación SPA); clases sin deck → tarjeta `hub-soon` no clicable.

> **Regla:** usa el componente `<Link>` de Slidev. **Prohibido** `<a href>` (recarga
> completa) y `@click="$slidev.nav..."` (API interna frágil).

## Validación obligatoria

Antes de dar por bueno un deck:

1. `slidev format` (gate de pre-commit) → sin cambios/errores.
2. Build aislado de la clase: `slidev build pages/claseN.md`.
3. Build del monolito: `make slidev-build`.
4. Escaneo del `dist/`: 0 literales `**` o `{.` en los chunks `md-*.js`.
5. Conteos balanceados: `<v-click>` ≡ `</v-click>`, `div` de apertura ≡ cierre,
   `two-cols-header` ≡ `::left::` ≡ `::right::`.
6. Máximos de *line-highlights* ≤ longitud real de cada bloque.

## Exportación a PDF (vía CLI, recomendada)

El diálogo de impresión del navegador es frágil (puede imprimir solo algunas páginas).
El PDF canónico se genera con el CLI de Playwright:

```bash
# devDependency: playwright-chromium
pnpm exec slidev export pages/claseN.md --output claseN-export
```

- `slides/pnpm-workspace.yaml` con `onlyBuiltDependencies: [playwright-chromium]`
  (pnpm 10 bloquea los scripts de build por defecto; sin esto no se descarga Chromium).
- Salida `slides/claseN-export.pdf` **ignorada por Git** (`slides/*-export.pdf`).
- Valida el número de páginas contra el número de diapositivas.

## Targets Makefile típicos

```bash
make slidev-dev            # monolito en http://localhost:3030
make slidev-build          # build de producción
make slidev-cN             # clase N aislada
make slidev-cN-export      # PDF de la clase N
make slidev-format         # slidev format
```
