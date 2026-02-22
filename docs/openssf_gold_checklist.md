# OpenSSF Best Practices — Gold Badge Checklist
# BESSAI Edge Gateway
# Referencia: https://www.bestpractices.dev/en/criteria/1
# Estado actual: PASSING ✅ — Target: GOLD 🥇

## Criterios en estado PASSING ya cumplidos
> Todos los criterios básicos (Passing) están verificados en bestpractices.dev/projects/12001

---

## Criterios SILVER requeridos para GOLD

### Documentación avanzada
- [x] Existe documentación de la arquitectura (docs/architecture.md)
- [x] CONTRIBUTING.md con instrucciones de desarrollo
- [x] CHANGELOG.md actualizado con cada release
- [x] ADRs documentados (5 decisiones en docs/adr/)
- [ ] **Guía de seguridad completa** para maintainers (docs/security_guide_maintainer.md)
- [ ] **Proceso de release documentado** (cómo hacer un release con tags y changelog)
- [x] Docs de API (docs/api_reference.md)

### Testing
- [x] Suite de tests automatizados (378 tests, pytest)
- [x] Coverage > 80% (codecov integrado en CI)
- [ ] **Statement coverage > 80% documentado** en bestpractices.dev
- [x] Tests de integración (chaos tests para auto-reconnect)
- [ ] **Mutation testing** documentado y score reportado (mutation-test.yml activo ✅, falta reportar)
- [ ] **CI ejecuta tests en cada push** documentado en el formulario

### Código
- [x] Linting automatizado (ruff en CI)
- [x] Type checking (mypy en CI)
- [x] SAST estático (bandit en CI)
- [x] Escaneo de dependencias (pip-audit, trivy)
- [ ] **Advertencias del compilador habilitadas** — documentar en formulario
- [ ] **CWE/OWASP** coverage documentado

### Seguridad
- [x] SECURITY.md con proceso de reporte
- [x] Política de vulnerabilidades documentada
- [ ] **Two-person code review** policy en CONTRIBUTING.md
- [ ] **Signed commits/releases** — configurar GPG signing en CI

### Proceso
- [x] Git branching model documentado
- [x] Conventional Commits (verificado en CONTRIBUTING.md)
- [ ] **2FA obligatoria** para todos los maintainers (requiere acción Rodrigo en GitHub settings)
- [x] GitHub Actions CI en cada PR (ci.yml)

---

## Criterios GOLD adicionales

### Buenas prácticas avanzadas
- [ ] **Verificación automática de dependencias** con hash pinning (requirements.txt con hashes)
- [x] Dependabot configurado (semanal)
- [ ] **Fuzzing** de inputs críticos (e.g., parsing de payloads Modbus)
- [ ] **Reproducible builds** documentados (Docker build args fijos)
- [ ] **SBOM (Software Bill of Materials)** generado en CI (syft o trivy sbom)

### Seguridad avanzada
- [x] OpenSSF Scorecard (scorecard.yml en CI)
- [ ] **Signed GitHub releases** con attestation (slsa-github-generator)
- [ ] **SLSA Level 2** build provenance
- [x] mTLS ready (configuración MQTT TLS disponible)

---

## Acciones inmediatas para avanzar a Silver/Gold

### Puedo implementar yo (Antigravity):
1. `requirements.txt` con hashes (`pip hash`)
2. SBOM job en CI (`syft` en cada release)
3. SLSA provenance en workflow de release
4. Two-person review policy en CONTRIBUTING.md actualizado

### Requiere acción de Rodrigo:
1. **2FA en GitHub** — Settings → Password and authentication → Enable 2FA
2. **Marcar criterios** en bestpractices.dev/projects/12001 (click en checkboxes)
3. **Statement coverage %** — subir una vez que Codecov muestre el % real

---

## Links clave
- Formulario: https://www.bestpractices.dev/projects/12001
- Criteria Gold: https://www.bestpractices.dev/en/criteria/2
- Scorecard: https://scorecard.dev/viewer/?uri=github.com/bess-solutions/open-bess-edge
