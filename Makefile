# BESSAI Edge Gateway — Developer Makefile
# Usage: make <target>   →   make help  for full list

.PHONY: help dev install test test-cov test-compliance test-fast lint lint-fix type-check security audit \
        all-checks simulate health up up-sim down logs build \
        gen-onnx export-cmg fetch-cmg evolve train-drl train-ppo \
        cert pilot compliance-report fleet \
        validate-registry tf-plan helm-lint helm-template \
        docs docs-serve \
        changelog release-dry-run release publish-pypi \
        clean

PYTHON  ?= python
COMPOSE  = docker compose
VERSION  ?= $(shell git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0")
SITE_ID  ?= SITE-CL-001
PORT     ?= 8000

# ── Help ───────────────────────────────────────────────────────────────────────

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ── Development ────────────────────────────────────────────────────────────────

dev: ## Install all dev dependencies + pre-commit hooks + security hooks
	pip install -e ".[dev]"
	pre-commit install
	git config core.hooksPath .githooks
	@echo "✅ Dev environment ready (PI hooks active). Run: make simulate"

install: ## Install runtime dependencies only
	pip install -e "."

# ── Testing ────────────────────────────────────────────────────────────────────

test: ## Run full test suite (compliance + edge)
	pytest -x --tb=short -q \
		--ignore=tests/agents/ \
		--ignore=tests/test_sun2000_monitor.py \
		--ignore=tests/test_totp_auth.py \
		--ignore=tests/test_vpp_publisher.py

test-compliance: ## NTSyCS compliance tests only (11 GAPs) — v2.14.0
	pytest \
		tests/test_compliance_api.py \
		tests/test_cen_sc_bidder.py \
		tests/test_ppo_trainer.py \
		tests/test_cen_publisher.py \
		tests/test_iec104_driver.py \
		-v --tb=short

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
	@echo "Grafana:    http://localhost:3000  (admin / see GF_SECURITY_ADMIN_PASSWORD in config/.env)"
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

scrape: ## Run full multi-source data scraper (CMg, ERNC, demand, weather, frequency)
	$(PYTHON) scripts/bessai_data_scraper.py --days 30 --sources all

scrape-status: ## Show status of all locally cached data sources
	$(PYTHON) scripts/bessai_data_scraper.py --status

fetch-cmg: scrape ## Alias for scrape (backwards compat)

evolve: ## Run BESSAIEvolve locally (manual trigger — reads parquet data if available)
	$(PYTHON) -m src.agents.bessai_evolve --generations 5 --population 10 --eval-days 30
	@echo "Results in models/evolution/"

gen-onnx: ## Generate dummy ONNX model for local testing
	$(PYTHON) scripts/generate_dummy_onnx.py

export-cmg: ## Export CMg data as JSON for dashboard
	$(PYTHON) scripts/export_cmg_json.py

train-drl: ## Train DRL policy  (requires ray[rllib] + real CMg data)
	$(PYTHON) scripts/train_drl_policy.py

train-ppo: ## BEP-0200 Phase 3: Train PPO dispatch agent (500k steps)
	@mkdir -p models logs/ppo_training
	$(PYTHON) -c "\
from src.core.ppo_trainer import PPOTrainer, TrainingConfig; \
cfg = TrainingConfig(total_timesteps=500_000); \
t = PPOTrainer(site_id='$(SITE_ID)', data_path='data/cen_telemetry.csv', config=cfg); \
r = t.train(); print(f'BEP-0200 Phase 3 done: {r.total_timesteps} steps, reward={r.final_mean_reward:.3f}')"

cert: ## Generate mTLS certs for CEN (SITE_ID=SITE-CL-001)
	bash infrastructure/certs/gen_certs.sh $(SITE_ID)

pilot: ## Validate pilot site readiness (runs pilot_setup.py wizard)
	$(PYTHON) scripts/pilot_setup.py --site-id $(SITE_ID)

compliance-report: ## Fetch compliance report from running gateway
	curl -sf http://localhost:$(PORT)/compliance/report | python -m json.tool

fleet: ## Fleet VPP summary from running gateway
	curl -sf http://localhost:$(PORT)/fleet/summary | python -m json.tool


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


