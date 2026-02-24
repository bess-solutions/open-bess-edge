# 🛠️ Manual de Acciones Manuales — Rodrigo

> **Versión:** 2026-02-24 · Solo estas tareas requieren acceso de propietario al repositorio GitHub.  
> Tiempo estimado total: ~45 minutos.

---

## 🔴 URGENTE — Seguridad del repositorio

### 1. Branch Protection en GitHub (~5 min)

**Qué hace:** Evita que alguien (incluyendo tú mismo por error) haga push directo a `main` sin revisión. Requerido por OpenSSF Scorecard para subir de 4/10.

**Pasos:**
1. Ve a: `https://github.com/bess-solutions/open-bess-edge/settings/branches`
2. Click en **"Add branch ruleset"** (o "Add classic branch protection rule")
3. **Branch name pattern:** `main`
4. Activa estas opciones:
   - ☑️ **Require a pull request before merging**
     - ☑️ Require approvals: **1**
   - ☑️ **Require status checks to pass before merging**
     - Busca y añade: `lint-typecheck`, `test`, `security`
   - ☑️ **Do not allow bypassing the above settings**
5. Click **"Create"** o **"Save changes"**

---

### 2. Cosign Keypair — Firma de releases (~10 min)

**Qué hace:** Firma criptográficamente cada release con cosign, permitiendo verificar la integridad del software. Requerido para SLSA Level 2.

**Pasos:**

**Paso 1 — Instalar cosign** (si no lo tienes):
```powershell
# En PowerShell como administrador:
winget install sigstore.cosign
# O descarga directo: https://github.com/sigstore/cosign/releases
```

**Paso 2 — Generar el keypair:**
```powershell
cd "c:\Users\TCI-GECOMP\Desktop\02_BESSAI_SOFTWARE\00 SISTEMA AI-BESS\Antigravity Repository\open-bess-edge"
cosign generate-key-pair
# Ingresa una contraseña segura cuando la pida
# Genera: cosign.key (PRIVADA) y cosign.pub (pública)
```

**Paso 3 — Añadir secrets a GitHub:**
1. Ve a: `https://github.com/bess-solutions/open-bess-edge/settings/secrets/actions`
2. Click **"New repository secret"**
3. Añade estos 2 secrets:

| Name | Value |
|---|---|
| `COSIGN_PRIVATE_KEY` | Contenido completo de `cosign.key` (abre con Notepad) |
| `COSIGN_PASSWORD` | La contraseña que pusiste al generar el keypair |

**Paso 4 — Guardar cosign.pub en el repo:**
```powershell
copy cosign.pub "c:\Users\TCI-GECOMP\Desktop\02_BESSAI_SOFTWARE\00 SISTEMA AI-BESS\Antigravity Repository\open-bess-edge\cosign.pub"
```
Luego hacer commit:
```powershell
git add cosign.pub
git commit -m "chore: add cosign public key for release verification"
git push
```

> ⚠️ **NUNCA** subas `cosign.key` al repositorio. Solo `cosign.pub`.

---

## 🟡 IMPORTANTE — Visibilidad y certificaciones

### 3. OpenSSF CII Best Practices — Nivel Silver (~20 min)

**Qué hace:** Sube el badge de "Passing" a "Silver", aumenta confianza de adopters.

1. Ve a: `https://bestpractices.coreinfrastructure.org/projects/12001`
2. Click **"Edit"** → sección por sección completar los checkboxes
3. Los más importantes que ya tenemos:
   - ☑️ Tests automatizados con cobertura ≥ 80% → `pytest --cov`
   - ☑️ CI/CD en GitHub Actions → `.github/workflows/ci.yml`
   - ☑️ SAST → CodeQL activo
   - ☑️ Fuzzing → Hypothesis en `fuzzing.yml`
   - ☑️ Análisis de vulnerabilidades → Trivy + Bandit
   - ☑️ Changelog → `CHANGELOG.md`
   - ☑️ SBOM → CycloneDX en `release.yml`

---

### 4. LF Energy Landscape — Aparecer en el mapa global (~15 min)

**Qué hace:** El repo aparece en el mapa oficial de proyectos de LF Energy, visible para utilities, reguladores e inversores de todo el mundo.

1. Fork del repo: `https://github.com/lf-energy/lfenergy-landscape`
2. Editar `landscape.yml`, buscar la sección `BESS` o `Energy Storage`
3. Añadir entrada:
```yaml
- item:
    name: BESSAI Edge Gateway
    homepage_url: https://github.com/bess-solutions/open-bess-edge
    logo: bessai.svg
    twitter: ''
    repo_url: https://github.com/bess-solutions/open-bess-edge
    crunchbase: https://www.crunchbase.com/organization/bess-solutions
    description: >
      Industrial-grade open-source BESS edge gateway with AI, IEC 62443 SL-2
      compliance, and IEEE 2030.5 / SEP 2.0 support.
```
4. Subir logo SVG en `hosted_logos/bessai.svg` (mínimo 500px, fondo transparente)
5. Abrir Pull Request a `main` del repo original

---

### 5. GitHub Sponsors — Botón de donación (~5 min)

**Qué hace:** Habilita financiamiento comunitario y señala al proyecto como activo.

1. Ve a: `https://github.com/sponsors`
2. Click **"Get started"** → sigue el flujo de registro
3. Una vez aprobado (24-48h), el botón ♥ Sponsor aparece automáticamente en el repo

---

## 🟢 CUANDO HAYA TIEMPO

### 6. Crear Hackathon 2026 — Anuncio público (~30 min)

1. **GitHub Discussions:** `https://github.com/bess-solutions/open-bess-edge/discussions`
   - Nueva discusión → Categoría: Announcements
   - Título: "🏆 BESSAI Hackathon 2026 — May 15-17 | Add your inverter profile, win recognition"

2. **LinkedIn:** Publicar post de anuncio (redactar con: fecha, premios, cómo participar, enlace al repo)

3. **Discord LF Edge:** `https://discord.gg/lfenergy` → canal `#projects`

---

### 7. Crear release oficial v2.9.0 en GitHub (~5 min)

```powershell
cd "c:\...\open-bess-edge"
git tag -a v2.9.0 -m "Release v2.9.0: MILP optimizer, degradation model, benchmark suite, CMg dashboard, OpenSSF hardening"
git push origin v2.9.0
```

Luego en `https://github.com/bess-solutions/open-bess-edge/releases/new`:
- Tag: `v2.9.0`
- Title: `v2.9.0 — MILP Optimizer + DRL Dashboard + OpenSSF Hardening`
- Pega el bloque correspondiente del `CHANGELOG.md`
- Click **"Publish release"**

---

### 8. Contactar certificadoras IEC 62443 SL-2 (~1 h)

Escribir a estas entidades para presupuesto de certificación formal:
- **TÜV SÜD:** `https://www.tuvsud.com/en/industries/energy/` → formulario contacto
- **Bureau Veritas:** `https://www.bureauveritas.com/` → contacto industrial
- **SGS:** `https://www.sgs.com/en/industries/energy`

Asunto sugerido:
> "Solicitud de presupuesto — Certificación IEC 62443 SL-2 para software de gestión BESS edge (Apache 2.0, open-source)"

---

## ✅ Checklist rápido

- [ ] Branch-Protection activada en `main`
- [ ] cosign keypair generado + secrets añadidos en GitHub
- [ ] Tags GitHub añadidos (✅ ya hecho hoy)
- [ ] OpenSSF Silver level checkboxes completados
- [ ] LF Energy Landscape PR abierto
- [ ] GitHub Sponsors configurado
- [ ] Release v2.9.0 publicada en GitHub
- [ ] Contactar TÜV SÜD / Bureau Veritas
