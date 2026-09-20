.PHONY: install lint type test cov sec claims simulate build check
install:  ; pip install -e ".[dev]"
lint:     ; ruff check src tests
type:     ; mypy
test:     ; pytest -q
cov:      ; pytest -q --cov=open_bess_edge --cov-report=term-missing
sec:      ; bandit -q -r src/open_bess_edge -x src/open_bess_edge/experimental && pip-audit
claims:   ; python scripts/verify_claims.py
simulate: ; open-bess-edge simulate --duration 12
build:    ; python -m build
check: lint type test claims sec
