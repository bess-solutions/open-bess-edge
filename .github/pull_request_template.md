## Summary

<!-- One-line description of the change -->

## Motivation

<!-- Why is this change needed? Link to a related issue or BEP if applicable.
     Closes #XXX | Implements BEP-0XXX -->

## Changes

<!-- Describe what was changed, added, or removed -->

- [ ] Source code
- [ ] Tests (unit / integration)
- [ ] Documentation
- [ ] Hardware profile
- [ ] Configuration / schema

## Type of Change

<!-- Mark all that apply -->

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (requires version bump + CHANGELOG entry)
- [ ] Hardware profile addition
- [ ] Documentation / tests only
- [ ] Refactor / performance improvement

## Testing

<!-- Describe how you tested the changes -->

```bash
make test          # all tests pass?
make lint          # no linting errors?
```

**Test results:**
- [ ] `make test` passes (all N tests)
- [ ] `make lint` passes (ruff + mypy + bandit)
- [ ] Tested on real hardware (if applicable): _describe_

## Checklist

- [ ] Conventional Commit message format (`feat(scope):`, `fix(scope):`, etc.)
- [ ] SPDX license header in all new source files
- [ ] `CHANGELOG.md` updated (for features and fixes)
- [ ] Docs updated if behavior changed
- [ ] No hardcoded secrets or credentials
- [ ] IEC 62443 / safety implications considered (if touching SafetyGuard or drivers)
