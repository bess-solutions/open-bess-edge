## Description

<!-- Describe your changes in detail. What does this PR do? -->

## Motivation / Related Issue

Closes #<!-- Issue number -->

## Type of Change

- [ ] 🐛 Bug fix (non-breaking change which fixes an issue)
- [ ] ✨ New feature (non-breaking change which adds functionality)
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] 🔒 Security fix
- [ ] 📝 Documentation update
- [ ] ♻️ Refactor (no functional changes)
- [ ] 🧪 Tests (adding or updating tests only)
- [ ] 🚀 CI/CD / Infrastructure change

## Component(s) Affected

<!-- Check all that apply -->
- [ ] `src/core/` — Core orchestrator
- [ ] `src/drivers/` — Hardware drivers
- [ ] `src/interfaces/` — Interfaces (API, metrics, AI, etc.)
- [ ] `src/simulation/` — BESS simulation / DRL
- [ ] `infrastructure/` — Docker, Helm, Terraform
- [ ] `tests/` — Test suite
- [ ] `docs/` — Documentation
- [ ] `.github/workflows/` — CI/CD

## Testing

<!-- Describe the tests you ran to verify your changes -->

```bash
# Commands used to test this change
pytest tests/test_<module>.py -v
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/ --ignore-missing-imports
```

**Test results:**
- Tests added: <!-- number -->
- Tests modified: <!-- number -->  
- Coverage change: <!-- e.g., 82% → 84% -->

## Safety Impact Assessment

<!-- This is an industrial system. Answer honestly. -->

- [ ] This change affects safety-critical code paths (SafetyGuard, SOC limits, Modbus write operations)
- [ ] This change modifies the ONNX inference pipeline
- [ ] This change affects GCP/cloud connectivity
- [ ] No safety-critical paths affected

If you checked any of the first three: describe in detail how safety is preserved:

<!-- Your explanation here -->

## Checklist

- [ ] My code follows the project's [coding standards](CONTRIBUTING.md#coding-standards)
- [ ] I have added/updated docstrings for all public functions changed
- [ ] I have updated `CHANGELOG.md` under `[Unreleased]`
- [ ] Tests pass locally: `pytest tests/ --tb=short`
- [ ] Linting passes: `ruff check src/ tests/`
- [ ] Format passes: `ruff format --check src/ tests/`
- [ ] Type check passes: `mypy src/ --ignore-missing-imports`
- [ ] PR title follows Conventional Commits: `type(scope): summary`
- [ ] I have read [CONTRIBUTING.md](CONTRIBUTING.md)

## Screenshots / Output (if applicable)

<!-- For UI changes, API changes, or metric additions — paste relevant output -->
