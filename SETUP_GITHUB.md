# 🚀 Guía: Crear el Repositorio en GitHub y Hacer el Primer Push

> El commit inicial ya está listo localmente (`04dcaa1` — 37 archivos).  
> Solo falta crear el repo en GitHub y subirlo.

---

## Paso 1 — Crear el repositorio en GitHub

En la pantalla que tienes abierta ([github.com/organizations/bess-solutions/repositories/new](https://github.com/organizations/bess-solutions/repositories/new)):

| Campo | Valor |
|---|---|
| **Owner** | `bess-solutions` ✅ (ya seleccionado) |
| **Repository name** | `open-bess-edge` |
| **Description** | `BESSAI Edge Gateway — Industrial BESS management via Modbus TCP, GCP Pub/Sub & OpenTelemetry` |
| **Visibility** | `Public` |
| **Add README** | ❌ Off (ya tenemos README) |
| **Add .gitignore** | ❌ No .gitignore (ya tenemos uno) |
| **Add license** | Apache 2.0 *(opcional)* |

➡ Clic en **"Create repository"**

---

## Paso 2 — Hacer el push desde PowerShell

Abre **PowerShell** en la carpeta del proyecto y ejecuta **bloque por bloque**:

```powershell
# Ir a la carpeta del proyecto
cd "c:\Users\TCI-GECOMP\Desktop\00 SISTEMA AI-BESS\Antigravity Repository\open-bess-edge"

# Alias para git (necesario porque no está en el PATH aún)
$git = "C:\Program Files\Git\bin\git.exe"

# Verificar que el commit está listo
& $git log --oneline -5
```

Deberías ver:
```
04dcaa1 feat: initial commit — BESSAI Edge Gateway v0.4.0-dev
```

Luego:

```powershell
# Configurar la URL del remote con tu PAT para autenticar
# Reemplaza TU_PAT con el token que generaste (ghp_...)
$token = "ghp_REPLACE_WITH_YOUR_PERSONAL_ACCESS_TOKEN"
& $git remote set-url origin "https://bess-solutions:${token}@github.com/bess-solutions/open-bess-edge.git"

# Push
& $git push -u origin main

# ⚠️ IMPORTANTE: limpiar el PAT de la URL del remote después del push
& $git remote set-url origin "https://github.com/bess-solutions/open-bess-edge.git"

Write-Host "✅ Push completado. PAT eliminado de la configuración."
```

---

## Paso 3 — Verificar en GitHub

Abre [github.com/bess-solutions/open-bess-edge](https://github.com/bess-solutions/open-bess-edge)

Deberías ver:
- ✅ **37 archivos** en la rama `main`
- ✅ **README.md** renderizado correctamente
- ✅ **`.github/workflows/`** con `ci.yml` y `release.yml`

---

## Paso 4 — Configurar GitHub Secrets para CI/CD

> Ir a: **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Descripción | Cuándo es necesario |
|---|---|---|
| `GCP_PROJECT_ID` | ID del proyecto GCP (ej: `bessai-prod-123`) | Cuando tengas proyecto GCP |
| `GCP_REGION` | Región del registry (ej: `us-central1`) | Cuando tengas proyecto GCP |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | Output de `terraform output` | Después de `terraform apply` |
| `GCP_SERVICE_ACCOUNT` | Email del SA (`bessai-edge-sa-dev@...`) | Después de `terraform apply` |

> 💡 Sin estos secrets, el pipeline ejecuta lint + tests + docker-build sin problemas.  
> Solo el job `docker-push` fallará hasta que estén configurados.

---

## Paso 5 — Verificar que el CI pasa

Una vez hecho el push, ir a:  
[github.com/bess-solutions/open-bess-edge/actions](https://github.com/bess-solutions/open-bess-edge/actions)

El pipeline **CI** debería ejecutarse automáticamente y mostrar:
- ✅ `lint` — ruff 0 errores
- ✅ `typecheck` — mypy
- ✅ `test` — 45/45
- ✅ `docker-build` — imagen multi-platform
- ⏭️ `docker-push` — skipped (solo corre en `main` con secrets configurados)

---

## Resumen de comandos (todo junto)

```powershell
$git = "C:\Program Files\Git\bin\git.exe"
$token = "ghp_REPLACE_WITH_YOUR_PERSONAL_ACCESS_TOKEN"

& $git remote set-url origin "https://bess-solutions:${token}@github.com/bess-solutions/open-bess-edge.git"
& $git push -u origin main
& $git remote set-url origin "https://github.com/bess-solutions/open-bess-edge.git"
Write-Host "✅ Listo"
```
