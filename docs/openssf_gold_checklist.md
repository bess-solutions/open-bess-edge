# OpenSSF Best Practices — Gold Badge Checklist
# BESSAI Edge Gateway
# Referencia: https://www.bestpractices.dev/en/criteria/1
# Estado: PASSING ✅ → SILVER/GOLD 🥇 (en progreso — v1.9.0)
# Última actualización: 2026-02-22

## Criterios en estado PASSING ya cumplidos
> Todos los criterios básicos (Passing) están verificados en bestpractices.dev/projects/12001

---

## Criterios SILVER requeridos para GOLD

### Documentación avanzada
- [x] Existe documentación de la arquitectura (docs/architecture.md)
- [x] CONTRIBUTING.md con instrucciones de desarrollo
- [x] CHANGELOG.md actualizado con cada release
- [x] ADRs documentados (5 decisiones en docs/adr/)
- [x] **Guía de seguridad completa** para maintainers → `docs/security_guide_maintainer.md` ✅ NEW v1.9.0
- [x] **Proceso de release documentado** → `docs/release_process.md` ✅ NEW v1.9.0
- [x] Docs de API (docs/api_reference.md)

### Testing
- [x] Suite de tests automatizados (378 tests, pytest)
- [x] Coverage > 80% (codecov integrado en CI)
- [ ] **Statement coverage > 80% documentado** en bestpractices.dev (requiere Rodrigo marcar checkbox)
- [x] Tests de integración (chaos tests para auto-reconnect)
- [x] **Mutation testing** activo → `mutation-test.yml` semanal (mutmut en safety.py + config.py)
- [x] **CI ejecuta tests en cada push** → ci.yml con pytest job en todo PR

### Código
- [x] Linting automatizado (ruff en CI)
- [x] Type checking (mypy en CI)
- [x] SAST estático (bandit en CI)
- [x] Escaneo de dependencias (pip-audit, trivy)
- [x] **Advertencias del compilador habilitadas** — mypy strict mode + ruff ALL rules en pyproject.toml
- [ ] **CWE/OWASP** coverage documentado (pendiente)

### Seguridad
- [x] SECURITY.md con proceso de reporte
- [x] Política de vulnerabilidades documentada → `docs/compliance/psirt_process.md` ✅ NEW v1.9.0
- [x] **Two-person code review** policy → CONTRIBUTING.md §Pull Request Process + §Maintainer Security Policy ✅
- [x] **Signed commits/releases** → cosign keyless en release.yml + SLSA L2 provenance ✅

### Proceso
- [x] Git branching model documentado
- [x] Conventional Commits (verificado en CONTRIBUTING.md)
- [ ] **2FA obligatoria** para todos los maintainers (requiere acción Rodrigo en GitHub settings)
- [x] GitHub Actions CI en cada PR (ci.yml)

---

## Criterios GOLD adicionales

### Buenas prácticas avanzadas
- [ ] **Verificación automática de dependencias** con hash pinning (pendiente — requirements.txt con `--generate-hashes`)
- [x] Dependabot configurado (semanal)
- [x] **Fuzzing** de inputs críticos → `.github/workflows/fuzzing.yml` (Atheris — Modbus + MQTT) ✅ NEW v1.9.0
- [x] **Reproducible builds** → Docker build-args fijos + lockfile en pyproject.toml ✅
- [x] **SBOM** generado en CI → CycloneDX en cada release (release.yml) ✅

### Seguridad avanzada
- [x] OpenSSF Scorecard (scorecard.yml en CI)
- [x] **Signed GitHub releases** → cosign keyless signing en release.yml ✅
- [x] **SLSA Level 2** build provenance → slsa-provenance job en release.yml ✅
- [x] mTLS ready (configuración MQTT TLS disponible)

---

## Pendiente — Solo Rodrigo

1. **2FA en GitHub** — Settings → Password and authentication → Enable 2FA
2. **Marcar criterios** en bestpractices.dev/projects/12001
3. **Statement coverage %** — confirmar en Codecov tras un CI run con coverage upload

---

## Links clave
- Formulario: https://www.bestpractices.dev/projects/12001
- Criteria Gold: https://www.bestpractices.dev/en/criteria/2
- Scorecard: https://scorecard.dev/viewer/?uri=github.com/bess-solutions/open-bess-edge
- Security guide: docs/security_guide_maintainer.md
- Release process: docs/release_process.md
