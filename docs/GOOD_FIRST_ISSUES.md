# Good First Issues — BESSAI Edge Gateway

Welcome to BESSAI! This document lists **12 concrete issues** ready for new contributors.
Each issue has a clear scope, the files involved, acceptance criteria, and estimated effort.

> **Before starting:** Read [CONTRIBUTING.md](../CONTRIBUTING.md) and join [Discord `#dev`](https://discord.gg/ZqpE8AZs) to claim an issue.

---

## 🟢 Beginner (1–3 hours)

### GFI-001 · Add `make simulate` alias for Windows PowerShell users

**Context:** `make simulate` fails on Windows because `make` is not installed by default.  
**Task:** Create a `scripts/simulate.ps1` PowerShell script that mirrors `make simulate`.  
**Files:** `scripts/simulate.ps1` (new), update `README.md` to mention it.  
**Acceptance:** Running `.\scripts\simulate.ps1` starts the gateway with the Modbus simulator on Windows.  
**Labels:** `good first issue`, `dx`, `windows`

---

### GFI-002 · Fix typos and grammar in docstrings across `src/`

**Context:** Some module docstrings have minor typos or incomplete descriptions.  
**Task:** Find and fix at least 10 docstring issues. Use `pydocstyle` or manual review.  
**Files:** Any file in `src/` — focus on `src/agents/`, `src/drivers/`, `src/core/`.  
**Acceptance:** No regressions in `pytest`. Each fix documented in the PR description.  
**Labels:** `good first issue`, `docs`, `easy`

---

### GFI-003 · Add missing `# SPDX-License-Identifier: Apache-2.0` headers

**Context:** The project policy (BEP-0202) requires SPDX headers in all source files.  
**Task:** Run `grep -rL "SPDX-License-Identifier" src/ tests/ scripts/` and add the header to files that are missing it.  
**Files:** Any `.py` files in `src/`, `tests/`, `scripts/`.  
**Acceptance:** `grep -rL "SPDX-License-Identifier" src/ tests/ scripts/` returns 0 files.  
**Labels:** `good first issue`, `compliance`, `easy`

---

### GFI-004 · Add `__all__` to all public modules in `src/`

**Context:** Public API modules should define `__all__` to make imports explicit and clean.  
**Task:** Add `__all__ = [...]` to the top-level `__init__.py` of each subpackage that is missing it.  
**Files:** `src/agents/__init__.py`, `src/drivers/__init__.py`, `src/interfaces/__init__.py`, `src/security/__init__.py`.  
**Acceptance:** `mypy src/` still passes with 0 errors after changes.  
**Labels:** `good first issue`, `code-quality`, `easy`

---

## 🟡 Intermediate (3–8 hours)

### GFI-005 · Add hardware profile for **Fronius GEN24** inverter

**Context:** The Hardware Registry currently has 7 profiles. Fronius GEN24 uses SunSpec over Modbus TCP.  
**Task:** Follow BEP-0100 to create `src/drivers/hardware_profiles/fronius_gen24.py` with at least 5 tests.  
**Files:** `src/drivers/hardware_profiles/fronius_gen24.py` (new), `tests/drivers/test_fronius_gen24.py` (new), update `registry/fronius_gen24.json`.  
**Acceptance:** `pytest tests/drivers/test_fronius_gen24.py` passes. Profile listed in `README.md` hardware registry table.  
**Labels:** `good first issue`, `hardware`, `drivers`

---

### GFI-006 · Write integration test for `SafetyGuard` boundary conditions

**Context:** `src/core/safety_guard.py` has unit tests but no edge-case integration tests.  
**Task:** Add a test file that verifies SafetyGuard blocks setpoints exactly at SOC/temperature limits (not just well outside them).  
**Files:** `tests/integration/test_safety_guard_boundaries.py` (new).  
**Acceptance:** Tests cover SOC at 95% (block), 94.9% (allow), temperature at 45°C (block), 44.9°C (allow). All pass.  
**Labels:** `good first issue`, `testing`, `safety`

---

### GFI-007 · Add Prometheus metric for `bess_evolve_champion_score`

**Context:** BESSAIEvolve runs weekly and updates the champion policy, but there is no Prometheus gauge tracking the champion's fitness score over time.  
**Task:** Add a `bess_evolve_champion_score` gauge to `src/monitoring/metrics.py` and emit it after each evolution run.  
**Files:** `src/monitoring/metrics.py`, `src/agents/bessai_evolve.py` or equivalent.  
**Acceptance:** `GET /metrics` returns `bess_evolve_champion_score` after `make evolve` runs. Unit test added.  
**Labels:** `good first issue`, `observability`, `evolve`

---

### GFI-008 · Improve `make help` output with categories grouping

**Context:** `make help` lists all targets alphabetically. Adding visual separators by category (Testing, Docker, Release…) would greatly improve DX.  
**Task:** Modify `Makefile` to add category comments that print as separators in `make help`.  
**Files:** `Makefile`.  
**Acceptance:** `make help` displays targets grouped by category with a visual separator line. No existing target functionality changes.  
**Labels:** `good first issue`, `dx`, `makefile`

---

## 🔵 Moderate (8–16 hours)

### GFI-009 · Port `fetch_cmg.py` to async (`asyncio` + `aiohttp`)

**Context:** `scripts/fetch_cmg_evolution.py` uses blocking `requests`. Making it async would allow fetching multiple data sources concurrently.  
**Task:** Rewrite the fetch logic using `asyncio` + `aiohttp`. Keep the same CLI interface and output format.  
**Files:** `scripts/fetch_cmg_evolution.py`, update `requirements.txt` if needed.  
**Acceptance:** `mypy` passes. `pytest` passes. Fetch time for 3 sources drops measurably. CLI unchanged.  
**Labels:** `good first issue`, `performance`, `async`

---

### GFI-010 · Add `/schedule` endpoint to the REST dashboard API

**Context:** The dashboard API (`src/interfaces/dashboard.py`) exposes SOC, power, revenue, and CMg. A `/schedule` endpoint showing the next 24h optimal charge/discharge windows is highly requested.  
**Task:** Add `GET /schedule` that returns the next 24 windows based on the last 30 days of CMg data.  
**Files:** `src/interfaces/dashboard.py`, add route; `tests/interfaces/test_dashboard_schedule.py` (new).  
**Acceptance:** `GET /schedule` returns valid JSON with `charge_windows` and `discharge_windows` arrays. At least 3 unit tests.  
**Labels:** `good first issue`, `api`, `feature`

---

### GFI-011 · Grafana dashboard JSON — add degradation panel

**Context:** The Grafana dashboard (`infrastructure/monitoring/grafana/dashboards/`) tracks power and revenue but lacks a battery degradation panel.  
**Task:** Add a panel showing `bess_degradation_pct_per_month` over the last 30 days.  
**Files:** `infrastructure/monitoring/grafana/dashboards/bessai_dashboard.json`.  
**Acceptance:** Dashboard JSON is valid. Panel visible in Grafana after `make up`. Screenshot included in PR.  
**Labels:** `good first issue`, `observability`, `grafana`

---

### GFI-012 · Write `docs/tutorials/raspberry_pi_docker.md`

**Context:** `docs/quickstart_rpi.md` covers bare-metal Pi setup. A Docker-specific tutorial for Pi 4/5 is missing.  
**Task:** Write a step-by-step tutorial for deploying BESSAI on Raspberry Pi 4/5 using the pre-built arm64 Docker image.  
**Files:** `docs/tutorials/raspberry_pi_docker.md` (new).  
**Acceptance:** Tutorial covers: hardware requirements, OS setup, Docker install, `docker pull ghcr.io/...`, `docker run`, health check, and viewing Grafana. Reviewed by a maintainer for accuracy.  
**Labels:** `good first issue`, `docs`, `raspberry-pi`, `docker`

---

## How to claim an issue

1. Comment "I'd like to work on GFI-XXX" on the corresponding GitHub Issue.
2. A maintainer will assign it to you within 24h.
3. Fork → branch `feature/GFI-XXX-short-description` → PR against `main`.
4. Ping `@bessai-core` in the PR when ready for review.

> Questions? Join [Discord `#dev`](https://discord.gg/ZqpE8AZs) — the team responds within hours.
