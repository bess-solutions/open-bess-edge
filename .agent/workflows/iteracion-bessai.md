---
description: Iteración BESSAI — actualizar archivos de proyecto y hacer push a GitHub
---

# Workflow: Iteración BESSAI con actualización de proyecto

Ejecuta estos pasos al **final de cada iteración** (v0.x.0) en BESSAI.

## 1. Ejecutar tests completos y verificar 100% pass
// turbo
```powershell
.venv\Scripts\python.exe -m pytest tests/ --tb=short -q
```
- Si hay fallos, corregirlos antes de continuar.
- Documentar recuento final (`N passed in Xs`).

## 2. Verificar nuevos o modificados workflows de GitHub Actions
- Listar los YAMLs nuevos con: `git diff --name-only HEAD~1 -- .github/workflows/`
- Para cada workflow nuevo/modificado:
  - Verificar que tenga `permissions:` explícito (nunca depender de defaults).
  - Verificar que tenga `timeout-minutes:` en cada job.
  - Verificar que tenga `workflow_dispatch:` para trigger manual.
  - Si toca el scraper (`bessai_data_scraper.py`), verificar que `data-pipeline.yml` también esté actualizado.

## 3. Verificar el scraper de datos (si hubo cambios)
- Si se modificó `scripts/bessai_data_scraper.py` o `scripts/fetch_cmg_evolution.py`:
  - Correr en modo local: `.venv\Scripts\python.exe scripts/bessai_data_scraper.py --status`
  - Verificar que `data/scraper_manifest.json` se genera correctamente.
  - Actualizar la lista de fuentes en `README.md` si se añadieron nuevas fuentes.

## 4. Actualizar CHANGELOG.md — bloque AGENT HANDOFF
- Cambiar timestamp: `Estado actual del proyecto (YYYY-MM-DDTHH:MM -03:00)`.
- Actualizar tabla de archivos con todos los módulos nuevos marcados `✅ **NUEVO vX.X**`.
- Incluir workflows nuevos en la tabla (columna "Archivo", descripción corta).
- Actualizar la línea de tests: `Suite de tests: N/N ✅ en X.XXs`.

## 5. Actualizar PROJECT_STATUS.md
- Cambiar línea `Actualizado:` con nueva versión y fecha.
- Añadir fila en tabla `Módulos implementados` con versión y estado.
- Actualizar bloque de tests con nuevo recuento.
- Actualizar barra de roadmap (`████`/`░░░░`).
- Añadir fila en tabla `Historial de Actualizaciones` al final.
- Si se añadieron workflows, incluirlos en la sección de CI/CD.

## 6. Actualizar requirements.txt (si hubo nuevas dependencias)
- Añadir sección con comentario `# vX.X.0 — NombreFeatura`.
- Incluir comentario de propósito para cada nueva dep.

## 7. Actualizar task.md (artifact)
- Marcar todos los ítems completados con `[x]`.
- Añadir resumen de la iteración.

## 8. Git add + commit + push
// turbo
```powershell
git add -A
git commit -m "chore(docs): actualizar archivos de proyecto a vX.X.0

- CHANGELOG.md: AGENT HANDOFF actualizado a vX.X.0
- PROJECT_STATUS.md: tabla de módulos y roadmap actualizados
- requirements.txt: deps vX.X añadidas
- Nnn tests / Nnn passed en X.XXs"
git push origin main
```

## 9. Verificar push exitoso
- Confirmar que la salida muestra `→ main` sin errores.
- Anotar el hash del commit (ej: `abc1234..def5678`).

---

> **Regla:** Ninguna iteración se considera "completa" hasta que el push a `main` sea exitoso y los 3 archivos de proyecto estén actualizados.

---

## Referencia rápida — Workflows activos (24 total)

| Workflow | Trigger | Propósito |
|---|---|---|
| `ci.yml` | push/PR | Lint · mypy · pytest · bandit · trivy |
| `bessai-evolve.yml` | Lunes 00:00 | Evolución genética DRL |
| `data-pipeline.yml` | **Daily 03:00** | Scraper diario CMg/ERNC/clima/frecuencia |
| `model-drift.yml` | **Lunes 01:00** | Detecta drift del modelo DRL (warn/revert) |
| `performance-regression.yml` | push/PR | Falla PR si regresión >10% en latencia/throughput |
| `hardware-ci.yml` | Martes 05:00 | Tests por perfil hardware vs simulador Modbus |
| `security-full.yml` | Domingo 02:00 | Semgrep + TruffleHog + SBOM + licencias |
| `interop-test.yml` | Miércoles 04:00 | IEEE 2030.5 + SunSpec + IEC 61850 |
| `stale-bot.yml` | Daily 06:00 | Limpieza de issues/PRs + reporte Discord |
| `changelog-bot.yml` | push main | Auto-actualiza CHANGELOG + notifica Discord |
| `benchmark.yml` | push/semanal | Benchmarks base de rendimiento |
| `codeql.yml` | push/semanal | CodeQL SAST |
| `scorecard.yml` | Lunes | OpenSSF Scorecard |
| `deps-audit.yml` | Lunes 09:00 | pip-audit CVE scan |
| `compliance-report.yml` | Lunes 07:00 | IEC 62443 compliance report |
| `fuzzing.yml` | Domingo 04:00 | Hypothesis property-based fuzzing |
| `mutation-test.yml` | Domingo 06:00 | mutmut mutation testing |
| `docs.yml` | push/PR | MkDocs → GitHub Pages |
| `docker-multiarch.yml` | push/PR | amd64 + arm64 → ghcr.io |
| `release.yml` | tag push | GitHub Release + SBOM |
| `pypi.yml` | tag push | PyPI publish |
| `weekly-update.yml` | Lunes 12:00 | Discord weekly stats |
| `deploy-website.yml` | push | Deploy bess-solutions.cl |
| `create_good_first_issues.yml` | manual | Crea Good First Issues |

**Secrets necesarios en GitHub Settings:**
- `DISCORD_WEBHOOK_URL` — para stale-bot, changelog-bot, weekly-update
- `SEMGREP_APP_TOKEN` — opcional para Semgrep cloud dashboard
