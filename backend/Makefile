# ──────────────────────────────────────────────────────────────────────
#  Relict backend — developer convenience targets
#
#  All targets assume your working directory is `backend/` and that
#  `docker compose` v2 is on the PATH. A few targets also work against
#  a local .venv for fast iteration without containers.
# ──────────────────────────────────────────────────────────────────────

.SHELLFLAGS := -euc
SHELL := bash
.DEFAULT_GOAL := help

PROJECT := relict
COMPOSE := docker compose
RUN_API := $(COMPOSE) exec api
RUN_WORKER := $(COMPOSE) exec worker

# ─── Meta ──────────────────────────────────────────────────────────────

.PHONY: help
help: ## Show this help.
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ─── First-time setup ─────────────────────────────────────────────────

.PHONY: env
env: ## Create backend/.env from backend/.env.example if missing.
	@if [ ! -f .env ]; then \
	  cp .env.example .env; \
	  echo "Created backend/.env — fill in the real secrets before running 'make up'."; \
	else \
	  echo "backend/.env already exists — leaving it alone."; \
	fi

.PHONY: jwt-secret
jwt-secret: ## Generate a strong JWT_SECRET and print it.
	@python -c "import secrets; print(secrets.token_urlsafe(64))"

# ─── Docker lifecycle ─────────────────────────────────────────────────

.PHONY: build
build: ## Build API + worker images.
	$(COMPOSE) build

.PHONY: up
up: ## Bring the stack up in the background.
	$(COMPOSE) up -d --build

.PHONY: up-fg
up-fg: ## Bring the stack up in the foreground (ctrl-c to stop).
	$(COMPOSE) up --build

.PHONY: down
down: ## Stop and remove containers (volumes preserved).
	$(COMPOSE) down

.PHONY: down-volumes
down-volumes: ## Stop, remove containers AND volumes. DESTRUCTIVE.
	$(COMPOSE) down -v

.PHONY: ps
ps: ## Show service status.
	$(COMPOSE) ps

.PHONY: logs
logs: ## Tail logs for all services.
	$(COMPOSE) logs -f --tail=200

.PHONY: logs-api
logs-api: ## Tail logs for the api container.
	$(COMPOSE) logs -f --tail=200 api

.PHONY: logs-worker
logs-worker: ## Tail logs for the worker container.
	$(COMPOSE) logs -f --tail=200 worker

# ─── Shells & debugging ───────────────────────────────────────────────

.PHONY: shell-api
shell-api: ## Open a bash shell inside the running api container.
	$(RUN_API) bash

.PHONY: shell-worker
shell-worker: ## Open a bash shell inside the running worker container.
	$(RUN_WORKER) bash

.PHONY: psql
psql: ## Open psql in the postgres container.
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER:-relict} -d $${POSTGRES_DB:-relict}

.PHONY: redis-cli
redis-cli: ## Open redis-cli in the redis container.
	$(COMPOSE) exec redis redis-cli

# ─── Database ─────────────────────────────────────────────────────────

.PHONY: migrate
migrate: ## Run alembic upgrade head inside the api container.
	$(RUN_API) alembic upgrade head

.PHONY: migrate-new
migrate-new: ## Generate a new Alembic migration. Use: make migrate-new MSG="describe change"
	$(RUN_API) alembic revision --autogenerate -m "$(MSG)"

.PHONY: migrate-down
migrate-down: ## Roll back the most recent migration.
	$(RUN_API) alembic downgrade -1

# ─── Quality gates ────────────────────────────────────────────────────

.PHONY: lint
lint: ## Run ruff lint (inside api container).
	$(RUN_API) ruff check app worker tests

.PHONY: format
format: ## Run ruff format.
	$(RUN_API) ruff format app worker tests

.PHONY: typecheck
typecheck: ## Run mypy --strict.
	$(RUN_API) mypy app worker

.PHONY: test
test: ## Run pytest with coverage gate.
	$(RUN_API) pytest

.PHONY: test-unit
test-unit: ## Run only unit tests (skip integration).
	$(RUN_API) pytest -m "not integration"

.PHONY: test-integration
test-integration: ## Run only integration tests (needs Postgres/Redis/MinIO up).
	$(RUN_API) pytest -m "integration"

.PHONY: ci
ci: lint typecheck test ## Run the full CI quality gate.

# ─── Cleanup ──────────────────────────────────────────────────────────

.PHONY: clean
clean: ## Remove Python caches, coverage data, build artifacts.
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov .coverage
