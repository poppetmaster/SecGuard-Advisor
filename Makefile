# =============================================================================
# SecGuard Advisor — automatización de tareas
# =============================================================================

SHELL := /bin/bash

.DEFAULT_GOAL := help
.PHONY: help install assets dev demo corpus seed-demo lint format format-check test test-integration check clean

help: ## Muestra esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Sincroniza el entorno e instala hooks y recursos
	uv sync --locked
	uv run pre-commit install
	npm ci

assets: ## Compila Tailwind y copia los recursos vendorizados
	npm run build

dev: ## Servidor local en 127.0.0.1 con un worker
	@if [ ! -f src/secguard_advisor/web/app.py ]; then echo "no implementado: la aplicación llega en T019"; exit 1; fi
	uv run uvicorn --factory secguard_advisor.web.app:create_app --host 127.0.0.1 --port 8000 --workers 1 --reload

demo: ## Servidor con datos de demostración (no implementado)
	@echo "no implementado: requiere T019 (aplicación) y T024 (seed)"
	@echo "previsto: uvicorn --factory secguard_advisor.web.app:create_app --workers 1"
	@exit 1

corpus: ## Descarga y verifica el corpus oficial (no implementado)
	@echo "no implementado: requiere T045"
	@exit 1

seed-demo: ## Carga los datos sintéticos de demostración
	uv run python scripts/seed_demo.py

lint: ## Ejecuta Ruff (lint)
	uv run ruff check .

format: ## Formatea el código con Ruff
	uv run ruff format .

format-check: ## Verifica el formato sin modificarlo
	uv run ruff format --check .

test: ## Ejecuta las pruebas rápidas
	uv run pytest

test-integration: ## Ejecuta las pruebas de integración reales
	uv run pytest -m integration

check: lint format-check test ## Verificación completa (lint + formato + pruebas)

clean: ## Limpia cachés y artefactos locales
	rm -rf .pytest_cache .ruff_cache .mypy_cache dist build htmlcov .coverage
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
