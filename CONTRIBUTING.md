# Contributing to BESSAI Edge Gateway

Thank you for your interest in contributing! BESSAI Edge Gateway is an open-source industrial system — every contribution, from bug reports to new drivers, makes the global energy transition more accessible.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How to Report Issues](#how-to-report-issues)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Pull Request Process](#pull-request-process)
- [Commit Convention](#commit-convention)
- [Coding Standards](#coding-standards)
- [Testing Requirements](#testing-requirements)
- [Adding a New Device Driver](#adding-a-new-device-driver)

---

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md). Please read it before contributing.

---

## How to Report Issues

- **Bug reports:** Use the [Bug Report template](.github/ISSUE_TEMPLATE/bug_report.yml)
- **Feature requests:** Use the [Feature Request template](.github/ISSUE_TEMPLATE/feature_request.yml)
- **Security vulnerabilities:** See [SECURITY.md](SECURITY.md) — **do NOT open public issues**

---

## Development Setup

### Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | 3.10+ | [python.org](https://www.python.org/) |
| Docker Desktop | 24.x+ | [docker.com](https://www.docker.com/) |
| Git | 2.40+ | [git-scm.com](https://git-scm.com/) |

### Local Environment

```bash
# 1. Fork and clone the repository
git clone https://github.com/<your-username>/open-bess-edge.git
cd open-bess-edge

# 2. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.\.venv\Scripts\Activate.ps1    # Windows PowerShell

# 3. Install all dependencies (production + dev)
pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt

# 4. Set up environment variables
cp config/.env.example config/.env
# Edit config/.env — minimum required: SITE_ID and INVERTER_IP

# 5. Verify setup — run the full test suite
pytest tests/ -v --tb=short
# Expected: 372 passed ✅
```

### Running with Docker (Simulator)

```bash
# Full stack: gateway + Modbus simulator + Prometheus + Grafana
docker compose -f infrastructure/docker/docker-compose.yml \
  --profile simulator --profile monitoring up -d

# Verify
curl http://localhost:8000/health      # Gateway health
curl http://localhost:8000/metrics     # Prometheus metrics
# Grafana: http://localhost:3000 (admin / bessai)
```

---

## Making Changes

1. **Create a branch** from `main`:
   ```bash
   git checkout -b feat/my-feature-name    # new feature
   git checkout -b fix/issue-123-brief     # bug fix
   git checkout -b docs/update-adr         # documentation
   ```

2. **Make your changes** following the [Coding Standards](#coding-standards)

3. **Write or update tests** — PRs without tests will not be merged

4. **Run the full validation suite locally** before pushing:
   ```bash
   ruff check src/ tests/             # linting
   ruff format src/ tests/            # formatting
   mypy src/ --ignore-missing-imports # type checking
   pytest tests/ -v --cov=src --cov-fail-under=80   # tests + coverage
   bandit -r src/ -ll                 # security static analysis
   ```

5. **Update documentation** if applicable:
   - `CHANGELOG.md` — add entry under `[Unreleased]`
   - Docstrings on all public functions/classes
   - `docs/` if architectural changes

---

## Pull Request Process

1. Ensure all CI checks pass (see `.github/workflows/ci.yml`)
2. Fill in the [Pull Request template](.github/pull_request_template.md) completely
3. Link the related Issue(s): `Closes #123`
4. Request review from at least one Maintainer
5. **Squash commits** before merge if you have more than 3 WIP commits
6. Do not merge your own PR — at least one other Maintainer must approve

### PR Review Turnaround

We aim to provide initial feedback within **5 business days**. If you haven't heard back, feel free to ping `@bess-solutions` in the PR comments.

---

## Commit Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short summary>

[optional body]

[optional footer]
```

### Types

| Type | Use when |
|---|---|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `test` | Adding or updating tests |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `perf` | Performance improvement |
| `ci` | CI/CD configuration changes |
| `chore` | Dependency updates, tooling |
| `security` | Security fix |

### Scopes (optional)

`core`, `drivers`, `interfaces`, `ai`, `infra`, `helm`, `terraform`, `tests`, `docs`

### Examples

```
feat(drivers): add support for Sungrow SH-RT inverter
fix(safety): correct SOC threshold calculation for LFP chemistry
security(dashboard_api): add rate limiting to /api/v1/status endpoint
docs(adr): add ADR-006 for OpenADR 3.0 broker selection
ci: add Trivy container scanning job
```

---

## Coding Standards

### Python Style

- **Formatter:** `ruff format` (line length: 99)
- **Linter:** `ruff check` (see `pyproject.toml` for enabled rules)
- **Type hints:** Required on all public functions. Use `mypy`-clean annotations.
- **Docstrings:** Required on all public classes and functions (Google style)

```python
def compute_arbitrage_revenue(
    schedule: list[DispatchSlot],
    capacity_kwh: float,
    efficiency: float = 0.92,
) -> float:
    """Calculate net arbitrage revenue for a given dispatch schedule.

    Args:
        schedule: List of dispatch slots from ArbitrageEngine.
        capacity_kwh: Battery usable capacity in kWh.
        efficiency: Round-trip efficiency (0–1). Defaults to 0.92.

    Returns:
        Estimated net revenue in CLP.

    Raises:
        ValueError: If capacity_kwh is non-positive.
    """
```

### Safety-Critical Code Rules

Because this software controls physical battery hardware, we apply additional rules:

1. **Never suppress exceptions silently** in safety-critical paths (core/, drivers/)
2. **Always have a safe fallback** in AI inference paths (return `None`, let SafetyGuard decide)
3. **Document physical limits** in code comments (e.g., `# IEC 62619: max 60°C for LFP`)
4. **Unit tests must cover failure modes** — not just happy paths

---

## Testing Requirements

- **Minimum coverage:** 80% overall (enforced by CI)
- **Test style:** `pytest` with `pytest-asyncio` for async code
- Every new module in `src/interfaces/` must have a corresponding `tests/test_<module>.py`
- Use `pytest.mark.parametrize` for data-driven tests
- Do not use `time.sleep()` in tests — use `pytest-asyncio` + `asyncio.sleep` or mock

---

## Adding a New Device Driver

Drivers live in `src/drivers/`. To add support for a new inverter/BESS:

1. Create `src/drivers/<manufacturer>_<model>_driver.py`
2. Implement the async interface:
   ```python
   async def connect(self) -> None: ...
   async def read_tag(self, tag_name: str) -> float: ...
   async def write_tag(self, tag_name: str, value: float) -> None: ...
   async def disconnect(self) -> None: ...
   ```
3. Create a device profile JSON in `registry/<manufacturer>_<model>.json`
4. Add tests in `tests/test_<manufacturer>_<model>_driver.py`
5. Document the device in `docs/` with supported registers and known quirks

---

## Questions?

- Open a [GitHub Discussion](https://github.com/bess-solutions/open-bess-edge/discussions)
- Email: ingenieria@bess-solutions.cl
