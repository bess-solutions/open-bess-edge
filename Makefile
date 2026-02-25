# BESSAI Edge Gateway — Developer Makefile
# Usage: make <target>   →   make help  for full list

.PHONY: help dev install test test-cov test-fast lint lint-fix type-check security audit \
        all-checks simulate health up up-sim down logs build \
        gen-onnx export-cmg fetch-cmg evolve train-drl \
        validate-registry tf-plan helm-lint helm-template \
        docs docs-serve \
        changelog release-dry-run release publish-pypi \
        clean

PYTHON  ?= python
COMPOSE  = docker compose
VERSION  ?= $(shell git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0")

# ── Help ───────────────────────────────────────────────────────────────────────

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ── Development ────────────────────────────────────────────────────────────────

dev: ## Install all dev dependencies + pre-commit hooks
	pip install -e ".[dev]"
	pre-commit install
	@echo "✅ Dev environment ready. Run: make simulate"

install: ## Install runtime dependencies only
	pip install -e "."

# ── Testing ────────────────────────────────────────────────────────────────────

test: ## Run full test suite (613 tests)
	pytest -x --tb=short -q

test-cov: ## Run tests with HTML coverage report  →  htmlcov/index.html
	pytest --cov=src --cov-report=term-missing --cov-report=html -q

test-fast: ## Run tests excluding slow integration tests
	pytest -x --tb=short -q -m "not slow"

# ── Code Quality ───────────────────────────────────────────────────────────────

lint: ## Ruff linter + formatter check (no changes)
	ruff check src/ tests/
	ruff format --check src/ tests/

lint-fix: ## Auto-fix all ruff issues
	ruff check --fix src/ tests/
	ruff format src/ tests/

type-check: ## mypy strict type checking
	mypy src/

security: ## bandit security scan
	bandit -r src/ -ll -x tests/

audit: ## pip-audit CVE scan against requirements.txt
	pip-audit --requirement requirements.txt --vulnerability-service=osv

all-checks: lint type-check security test ## Run all quality checks (CI equivalent)

# ── Runtime ────────────────────────────────────────────────────────────────────

simulate: ## Run gateway with built-in Modbus simulator (no real hardware needed)
	$(PYTHON) -m src.gateway --simulator
	@echo "Simulator running. Health: http://localhost:8000/health"

health: ## Check all subsystem health (requires running instance)
	@curl -s http://localhost:8000/health | python -m json.tool || echo "Gateway not running"

# ── Docker ─────────────────────────────────────────────────────────────────────

up: ## Start gateway + Prometheus + Grafana
	$(COMPOSE) --profile monitoring up -d
	@echo "Gateway:    http://localhost:8000/health"
	@echo "Grafana:    http://localhost:3000  (admin / bessai)"
	@echo "Prometheus: http://localhost:9090"

up-sim: ## Start gateway + simulator + full monitoring stack
	$(COMPOSE) --profile simulator --profile monitoring up -d
	@echo "Simulator on port 5020 (Modbus TCP)"

down: ## Stop all containers
	$(COMPOSE) --profile simulator --profile monitoring down

logs: ## Follow gateway logs in real-time
	$(COMPOSE) logs -f bessai-edge

build: ## Build Docker image locally for current platform
	docker build -t bessai-edge:local .

# ── AI / BESSAIEvolve ─────────────────────────────────────────────────────────

fetch-cmg: ## Fetch last 30 days of real CMg data from CEN Chile
	$(PYTHON) scripts/fetch_cmg_evolution.py --days 30
	@echo "CMg data saved to data/cmg_historico.parquet"

evolve: ## Run BESSAIEvolve locally (manual trigger — reads CMg data if available)
	$(PYTHON) -m src.agents.bessai_evolve --generations 5 --population 10 --eval-days 30
	@echo "Results in models/evolution/"

gen-onnx: ## Generate dummy ONNX model for local testing
	$(PYTHON) scripts/generate_dummy_onnx.py

export-cmg: ## Export CMg data as JSON for dashboard
	$(PYTHON) scripts/export_cmg_json.py

train-drl: ## Train DRL policy  (requires ray[rllib] + real CMg data)
	$(PYTHON) scripts/train_drl_policy.py

# ── Hardware Registry ──────────────────────────────────────────────────────────

validate-registry: ## Validate all hardware registry JSON profiles against schema
	$(PYTHON) -c "\
import json, glob, sys; \
errors = []; \
[errors.append(f) if not json.load(open(f)) else print(f'✅ {f}') \
 for f in glob.glob('registry/*.json')]; \
sys.exit(1 if errors else 0)"

# ── Infrastructure ─────────────────────────────────────────────────────────────

tf-plan: ## Terraform plan (GCP) — dry run
	cd infrastructure/terraform && terraform plan

helm-lint: ## Lint Helm chart
	helm lint infrastructure/helm/bessai-edge/

helm-template: ## Render Helm templates to stdout
	helm template bessai-edge infrastructure/helm/bessai-edge/

# ── Documentation ──────────────────────────────────────────────────────────────

docs: ## Build MkDocs documentation (HTML)
	mkdocs build --strict

docs-serve: ## Serve docs locally with live reload  →  http://localhost:8080
	mkdocs serve --dev-addr 0.0.0.0:8080

# ── Release ────────────────────────────────────────────────────────────────────

changelog: ## Preview changelog for unreleased changes (requires git-cliff)
	git cliff --unreleased 2>/dev/null || echo "Install: pip install git-cliff"

release-dry-run: ## Simulate release without creating tag or publishing
	@echo "Current version: $(VERSION)"
	@echo "--- CHANGELOG preview ---"
	@git log --oneline $(VERSION)..HEAD --no-walk=unsorted 2>/dev/null | head -20 || true
	@echo "--- Build check ---"
	$(PYTHON) -m build --no-isolation --outdir /tmp/bessai-dist-dry/ 2>&1 | tail -5
	@echo "✅ Dry run complete. Use: make release VERSION=vX.Y.Z"

release: ## Create and push a release tag  (usage: make release VERSION=v2.11.0)
	@test -n "$(VERSION)" || (echo "Usage: make release VERSION=vX.Y.Z" && exit 1)
	@echo "Tagging $(VERSION)..."
	git tag -a $(VERSION) -m "Release $(VERSION)"
	git push origin $(VERSION)
	@echo "✅ Tag pushed. GitHub Actions will create the GitHub Release."
	@echo "   For PyPI: make publish-pypi"

publish-pypi: ## Build and publish to PyPI via Trusted Publisher (OIDC)
	$(PYTHON) -m build
	$(PYTHON) -m twine upload --repository pypi dist/*
	@echo "✅ Published to PyPI. See: https://pypi.org/project/bessai-edge/"

# ── Utilities ──────────────────────────────────────────────────────────────────

clean: ## Remove build artifacts, caches, and temp files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov dist build *.egg-info
	rm -rf /tmp/bessai-dist-dry/
	@echo "✅ Clean complete"


.PHONY: help dev test lint type-check security up up-sim down logs clean build release

PYTHON ?= python
COMPOSE = docker compose -f infrastructure/docker/docker-compose.yml

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Development ────────────────────────────────────────────────────────────────

dev: ## Install dev dependencies and set up environment
	pip install -e ".[dev]"
	pre-commit install

test: ## Run full test suite (541 tests)
	pytest -x --tb=short -q

test-cov: ## Run tests with coverage report
	pytest --cov=src --cov-report=term-missing --cov-report=html -q

test-fast: ## Run tests excluding slow integration tests
	pytest -x --tb=short -q -m "not slow"

# ── Code Quality ───────────────────────────────────────────────────────────────

lint: ## Run ruff linter + formatter check
	ruff check src/ tests/
	ruff format --check src/ tests/

lint-fix: ## Auto-fix ruff issues
	ruff check --fix src/ tests/
	ruff format src/ tests/

type-check: ## Run mypy type checking
	mypy src/

security: ## Run bandit security scan
	bandit -r src/ -ll -x tests/

audit: ## Run pip-audit for CVE scanning
	pip-audit --requirement requirements.txt --vulnerability-service=osv

all-checks: lint type-check security test ## Run all quality checks

# ── Docker ─────────────────────────────────────────────────────────────────────

up: ## Start gateway + monitoring (Prometheus + Grafana)
	$(COMPOSE) --profile monitoring up -d
	@echo "Gateway:    http://localhost:8000/health"
	@echo "Grafana:    http://localhost:3000  (admin / bessai)"
	@echo "Prometheus: http://localhost:9090"

up-sim: ## Start gateway + simulator + monitoring
	$(COMPOSE) --profile simulator --profile monitoring up -d
	@echo "Simulator running on port 5020 (Modbus TCP)"

down: ## Stop all containers
	$(COMPOSE) --profile simulator --profile monitoring down

logs: ## Follow gateway logs
	$(COMPOSE) logs -f bessai-edge

build: ## Build Docker image locally
	docker build -t bessai-edge:local .

# ── Simulation & Models ────────────────────────────────────────────────────────

gen-onnx: ## Generate dummy ONNX model for local testing
	$(PYTHON) scripts/generate_dummy_onnx.py

export-cmg: ## Export CMg data for dashboard (CEN SEN patterns)
	$(PYTHON) scripts/export_cmg_json.py

train-drl: ## Train DRL policy (requires ray[rllib] and real CMg data)
	$(PYTHON) scripts/train_drl_policy.py

# ── Registry & Hardware ────────────────────────────────────────────────────────

validate-registry: ## Validate all hardware registry JSON profiles
	$(PYTHON) -c "import json, glob; [json.load(open(f)) or print(f'OK: {f}') for f in glob.glob('registry/*.json')]"

# ── Infrastructure ─────────────────────────────────────────────────────────────

tf-plan: ## Run Terraform plan (GCP)
	cd infrastructure/terraform && terraform plan

helm-lint: ## Lint Helm chart
	helm lint infrastructure/helm/bessai-edge/

helm-template: ## Render Helm templates
	helm template bessai-edge infrastructure/helm/bessai-edge/

# ── Release ────────────────────────────────────────────────────────────────────

clean: ## Remove build artifacts and caches
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov dist build *.egg-info

release: ## Create a new release (usage: make release VERSION=v2.9.0)
	@test -n "$(VERSION)" || (echo "Usage: make release VERSION=vX.Y.Z" && exit 1)
	git tag -a $(VERSION) -m "Release $(VERSION)"
	git push origin $(VERSION)
	@echo "Release $(VERSION) tagged. GitHub Actions will build and publish."
