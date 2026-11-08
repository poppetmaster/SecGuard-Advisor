# Guía de contribución

Gracias por contribuir a **SecGuard Advisor**.

La documentación normativa vive en [`CONSTITUTION.md`](./CONSTITUTION.md). Léela antes de tu
primera contribución: define el stack, las decisiones y las reglas que un cambio debe respetar.

## Requisitos previos

| Herramienta | Versión | Notas |
|---|---|---|
| Python | 3.14.6 | Fijada en `.python-version` |
| uv | Última estable | Gestión de dependencias y entornos |
| Node.js + npm | 26.11.1 | Fijada en `.nvmrc`; solo para compilar CSS y copiar recursos |
| Git | Última estable | Control de versiones |

Está prohibido usar `pip` o `requirements.txt`. Toda gestión de dependencias pasa por `uv`.

## Configuración del entorno

```bash
uv sync --locked
npm ci
uv run pre-commit install
make check
```

`make install` agrupa los tres primeros pasos. `make help` lista los comandos disponibles.

## Flujo de trabajo con Git

La rama `main` es la rama estable: no se trabaja directamente sobre ella.

1. Crea una rama descriptiva:
   - `feat/` para funcionalidad nueva.
   - `fix/` para correcciones.
   - `docs/` para documentación.
   - `test/` para pruebas.
   - `chore/` para mantenimiento.
2. Desarrolla en commits pequeños y atómicos.
3. Abre un Pull Request hacia `main`.

No se hace `push` a `main` ni se publica un remoto sin autorización explícita.

## Estándares de código

- PEP 8 y PEP 257.
- Anotaciones de tipo en funciones y firmas públicas.
- `snake_case` para funciones y variables, `PascalCase` para clases, `UPPER_CASE` para constantes.
- Pruebas con pytest y patrón AAA (Arrange, Act, Assert).
- Ruff para lint y formato.

```bash
make lint
make format
make test
make check
```

La documentación y la interfaz se escriben en español. El código, los identificadores, los nombres
de tablas y los comentarios se escriben en inglés.

Nunca subas secretos (`.env`, tokens, llaves), datos pesados, originales del corpus ni entornos
virtuales. Respeta `.gitignore`.

## Mensajes de commit

Se usa [Conventional Commits](https://www.conventionalcommits.org/):

```text
<tipo>(<ámbito opcional>): <descripción breve en imperativo>
```

| Tipo | Uso |
|---|---|
| `feat` | Funcionalidad nueva |
| `fix` | Corrección |
| `docs` | Documentación |
| `refactor` | Refactorización sin cambio de comportamiento |
| `style` | Formato o linting |
| `test` | Pruebas |
| `chore` | Mantenimiento o configuración |

No se añade atribución de IA a los commits.

## Pull Requests

1. Verifica que la rama esté actualizada respecto a `main`.
2. Completa la plantilla oficial.
3. Usa un título convencional y mantén un solo propósito por PR.
4. Marca los checklist aplicables: pruebas, lint, `uv.lock` y `CONSTITUTION.md`.
5. La integración se hace por Squash & Merge salvo indicación contraria.

## Reportar issues

Usa las plantillas de `.github/ISSUE_TEMPLATE/` e incluye contexto, pasos para reproducir y
evidencia cuando aplique.

## Regla de oro: mantener la constitución

Cualquier cambio arquitectónico, tecnológico o de proceso debe reflejarse en
[`CONSTITUTION.md`](./CONSTITUTION.md) en el mismo commit. El checklist del PR lo verifica.

## Licencia

Al contribuir aceptas que tus aportes se distribuyan bajo la [Licencia MIT](./LICENSE).
