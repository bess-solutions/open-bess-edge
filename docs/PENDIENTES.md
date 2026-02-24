# 📋 PENDIENTES — BESSAI Edge Gateway v2.9.0-dev

> **Actualizado:** 2026-02-24 · **Fuente:** CHANGELOG.md + PROJECT_STATUS.md  
> Este archivo consolida todas las tareas pendientes, ordenadas por prioridad.  
> Actualizar en cada sesión de trabajo junto con `CHANGELOG.md`.

---

## 🔴 Prioridad Alta — Bloquean release o seguridad

| # | Tarea | Archivo/Contexto | Tipo |
|---|---|---|---|
| 1 | Refactor `handle_der_control` (C901 complejidad 15) | `sep2_adapter.py:569` | Código |
| 2 | Fix SSL test mock PEM inválido | `test_sep2_adapter.py:447` | Test |
| 3 | **Branch-Protection en GitHub** (requiere Rodrigo) | GH Settings → Branches → main | Manual infra |
| 4 | **cosign keypair** → `cosign generate-keypair` + Secrets GH | `release.yml` + GitHub Secrets | Manual infra |
| 5 | mypy `modbus_driver.py:179` — `# type: ignore[arg-type]` + bug report pymodbus | `modbus_driver.py` | Type fix |
| 6 | mypy `totp_auth.py:201` — guard `if self._totp is not None` | `totp_auth.py` | Type fix |

---

## 🟡 Prioridad Media — Mejoras funcionales importantes

| # | Tarea | Archivo/Contexto | Tipo |
|---|---|---|---|
| 7 | Tests de integración para MILP Optimizer | `tests/agents/test_milp_optimizer.py` | Test |
| 8 | Tests para `degradation_model.py` y `benchmark_suite.py` | `tests/agents/` | Test |
| 9 | BEP-0200 Fase 3 — Entrenar PPO con datos reales CEN 2023-2025 | `models/drl_arbitrage_v1.onnx` | AI/ML |
| 10 | Activar `write_tag()` en DRL (observe → control real) tras staging | `main.py:Step5e`, `BESSAI_DRL_ENABLED` | Feature |
| 11 | OpenSSF Scorecard Fase 2 — verificar CodeQL en GH Security tab | GitHub Security tab | Manual |
| 12 | OpenSSF CII Best Practices — completar checkboxes Silver level | bestpractices.dev/projects/12001 | Manual |
| 13 | BEP-0201 Digital Twin PINN para RUL prediction (<2% error) | `src/agents/digital_twin.py` [NEW] | AI/ML |

---

## 🟢 Prioridad Baja — Deuda técnica y mejoras futuras

| # | Tarea | Archivo/Contexto | Tipo |
|---|---|---|---|
| 14 | Configurar `pyrightconfig.json` con venvPath (Pyre2 falsos positivos) | `pyrightconfig.json` | Config |
| 15 | Implementar `BatteryState` dataclass en drivers (BESSAI-SPEC-004) | `src/drivers/` | Spec |
| 16 | Conectar dashboard CMg a API CEN real (hoy: datos simulados SEN) | `dashboard/data/` | Data |
| 17 | Repo `bessai-postulaciones` → Push a GitHub privado | `bessai-postulaciones/` | Infra |
| 18 | BDF exporter (Battery Data Format LF Energy) — BEP-0202 Fase 1 | `src/interfaces/bdf_exporter.py` | Feature |
| 19 | Protocol Registry — DNP3 driver (BEP-0202 Fase 2) | `src/drivers/dnp3_driver.py` | Feature |

---

## 📅 Pendientes Manuales (solo Rodrigo)

| Tarea | Desbloqueador | Urgencia |
|---|---|---|
| **Branch-Protection GitHub** | GH Settings → Branches → Add rule `main` (2 approvals) | 🔴 Alta |
| **cosign keypair** | `cosign generate-keypair` → añadir `COSIGN_PRIVATE_KEY` + `COSIGN_PASSWORD` a GH Secrets | 🔴 Alta |
| **LF Energy Landscape** | Fork `lfenergy/lfenergy-landscape` + PR YAML + SVG logo + Crunchbase | 🟡 Media |
| **OpenSSF Gold** | bestpractices.dev/projects/12001 — completar checkboxes | 🟡 Media |
| **Hackathon 2026** | Anunciar Discord + LinkedIn + GitHub Discussions (Mayo 15-17) | 🟡 Media |
| **IEC 62443 SL-2** | Contactar TÜV SÜD / Bureau Veritas para presupuesto | 🟡 Media |
| **GitHub Pages** | Settings → Pages → branch `gh-pages` → activar MkDocs site | 🟢 Baja |
| **bessai-postulaciones** | Crear repo privado en github.com/new + git push | 🟢 Baja |

---

## ✅ Completadas recientemente (v2.7-v2.9)

- [x] BEP-0200 Fase 1+2 — DRL Agent integrado en main.py (observe-only)
- [x] BEP-0100 — IEEE 2030.5 / SEP 2.0 Adapter completo
- [x] OpenSSF Scorecard CI + fuzzing (Hypothesis) + CodeQL SAST
- [x] Separación estándar vs estrategia de crecimiento (docs/)
- [x] BEP-0202 diseño + OpenFMB adapter + BDF alignment + OCPP docs
- [x] Registry: SolarEdge, BYD, Tesla (7 dispositivos total)
- [x] Dashboard DRL Optimizer con CMg Maitencillo 48 días
- [x] MILP Optimizer + Degradation Model + Benchmark Suite
- [x] Revisión 360°: ruff 35/36 + structlog migration
