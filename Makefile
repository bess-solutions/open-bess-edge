# BESSAI Edge Gateway — Developer Makefile
# Usage: make <target>

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
