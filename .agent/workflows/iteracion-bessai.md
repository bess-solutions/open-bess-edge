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

## 2. Actualizar CHANGELOG.md — bloque AGENT HANDOFF
- Cambiar timestamp: `Estado actual del proyecto (YYYY-MM-DDTHH:MM -03:00)`.
- Actualizar tabla de archivos con todos los módulos nuevos marcados `✅ **NUEVO vX.X**`.
- Actualizar la línea de tests: `Suite de tests: N/N ✅ en X.XXs`.

## 3. Actualizar PROJECT_STATUS.md
- Cambiar línea `Actualizado:` con nueva versión y fecha.
- Añadir fila en tabla `Módulos implementados` con versión y estado.
- Actualizar bloque de tests con nuevo recuento.
- Actualizar barra de roadmap (`████`/`░░░░`).
- Añadir fila en tabla `Historial de Actualizaciones` al final.

## 4. Actualizar requirements.txt (si hubo nuevas dependencias)
- Añadir sección con comentario `# vX.X.0 — NombreFeatura`.
- Incluir comentario de propósito para cada nueva dep.

## 5. Actualizar task.md (artifact)
- Marcar todos los ítems completados con `[x]`.
- Añadir resumen de la iteración.

## 6. Git add + commit + push
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

## 7. Verificar push exitoso
- Confirmar que la salida muestra `→ main` sin errores.
- Anotar el hash del commit (ej: `abc1234..def5678`).

---

> **Regla:** Ninguna iteración se considera "completa" hasta que el push a `main` sea exitoso y los 3 archivos de proyecto estén actualizados.
