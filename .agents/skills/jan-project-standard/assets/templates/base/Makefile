# =============================================================================
# {{PROJECT_NAME}} — automatización de tareas
# =============================================================================

SHELL := /bin/bash

.DEFAULT_GOAL := help
.PHONY: help install dev pre-commit-install pre-commit lint format format-check typecheck test check build clean

help: ## Muestra esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Sincroniza el entorno virtual e instala dependencias
	uv sync

dev: install pre-commit-install ## Prepara el entorno de desarrollo (sync + hooks)

pre-commit-install: ## Instala los hooks de pre-commit en el repositorio local
	uv run pre-commit install

pre-commit: ## Ejecuta todos los hooks de pre-commit sobre el repositorio
	uv run pre-commit run --all-files

lint: ## Ejecuta Ruff (lint)
	uv run ruff check .

format: ## Formatea el código con Ruff
	uv run ruff format .

format-check: ## Verifica el formato sin modificarlo
	uv run ruff format --check .

{{#if TYPES}}typecheck: ## Verifica los tipos con ty (Astral)
	uv run ty check

{{/if}}test: ## Ejecuta las pruebas
	uv run pytest

{{#if TYPES}}check: lint format-check typecheck test ## Verificación completa (lint + formato + tipos + pruebas)
{{/if}}{{#unless TYPES}}check: lint format-check test ## Verificación completa (lint + formato + pruebas)
{{/unless}}
{{#if PACKAGE}}build: ## Construye el paquete (sdist + wheel)
	uv build

{{/if}}clean: ## Limpia cachés y artefactos
	rm -rf .pytest_cache .ruff_cache .mypy_cache dist build htmlcov .coverage
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
