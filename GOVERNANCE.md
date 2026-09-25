# Política de Gobernanza y Contribución — Open BESS Edge

> **Versión:** 1.0  
> **Fecha de vigencia:** 2026-09-25  
> **Alcance:** Repositorio canónico `open-bess-edge` y dependencias directas.

---

## 1. Principio Fundamental de Integridad Técnica

Open BESS Edge es software de misión crítica destinado al control físico de almacenamiento de energía en subestaciones y plantas eléctricas. Los principios de **honestidad técnica, auditabilidad y transparencia** priman sobre cualquier meta de marketing o proyección comercial.

---

## 2. Política de Autoría y Commits

### 2.1 Prohibición de Bots Ficticios Autónomos
Queda **estrictamente prohibido** el uso de identidades automatizadas ficticias o "bots de rol" realizando commits directos sobre la rama `main` sin revisión humana explícita.

Las siguientes identidades (y variantes análogas) quedan **vetadas de autoría directa**:
- `docker-agent`
- `Gordon - Docker AI Assistant`
- `BESSAI V Bot`
- `Thermal Optimization Bot`
- `CEN Resilience Bot`
- `Ingeteam Specialist Bot`

Todo commit debe corresponder a un desarrollador o mantenedor humano verificable, o a herramientas de tooling institucional oficial (ej. dependabot / pre-commit.ci) debidamente configuradas.

### 2.2 Política de Ramas y Pull Requests
1. **Rama `main` protegida**: Ningún commit se realiza directamente sobre `main`. Todo cambio debe someterse mediante un **Pull Request (PR)**.
2. **Revisión Humana Obligatoria**: Cada PR requiere la aprobación de al menos un mantenedor del proyecto antes de la fusión.
3. **CI Obligatorio y Bloqueante**: El PR solo puede fusionarse si todos los jobs de CI pasan en verde:
   - `pytest` (278 tests del núcleo canónico)
   - `ruff check` (0 errores de linter)
   - `mypy` (0 errores de análisis estático)
   - `bandit` (0 vulnerabilidades de seguridad)
   - `verify_claims.py` (0 aserciones fallidas en documentación y registry)

---

## 3. Estándar de Veracidad Documental (Truth-in-Advertising)

1. **Prohibición de Datos No Físicos**: Ningún documento, reporte o simulación puede incorporar parámetros físicamente imposibles para el hardware especificado (ej. inyección de potencias cientos de veces superiores a la capacidad nominal del inversor o batería).
2. **Separación de Datos de Mercado y Simulaciones**: Toda cifra estimada o proyectada debe identificarse de forma explícita e inequívoca como *"Simulación Teórica"* o *"Backtest"*, indicando supuestos y advertencias de no garantía.
3. **Afirmaciones de Certificación y Homologación**:
   - Solo se declarará "homologado" o "certificado" el hardware o funcionalidad que cuente con informe formal emitido por entidad competente o protocolo HIL de 72 horas completado y documentado.
   - En ausencia de dicho informe, el estado mandatorio es **"Pendiente de homologación"** o **"Prototipo de laboratorio"**.
