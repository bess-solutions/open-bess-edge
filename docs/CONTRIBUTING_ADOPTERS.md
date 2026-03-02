# 🤝 Cómo contribuir como Early Adopter

> Esta guía está dirigida a usuarios que quieren contribuir con su primera mejora al proyecto — sin necesidad de ser expertos en el código interno.

---

## Contribuciones más valoradas por la comunidad

| Tipo | Dificultad | Impacto |
|------|-----------|---------|
| ➕ Perfil JSON de nuevo hardware | ⭐ Baja | 🔴 Alto |
| 🐛 Reportar bug con logs completos | ⭐ Baja | 🔴 Alto |
| 📝 Mejorar documentación / traducción | ⭐ Baja | 🟡 Medio |
| 🧪 Escribir test para un caso de borde | ⭐⭐ Media | 🟡 Medio |
| ✨ Implementar feature de GOOD_FIRST_ISSUES | ⭐⭐ Media | 🔴 Alto |
| 🏗️ Nuevo conector de mercado (CENACE, REE…) | ⭐⭐⭐ Alta | 🔴 Alto |

---

## Contribución 1 — Perfil de hardware (más común)

Tienes un inversor que no está en `registry/`. En 30 minutos puedes aportarlo.

### Paso 1 — Revisar el formato existente

```bash
cat registry/huawei_sun2000.json | python3 -m json.tool
```

La estructura es:
```json
{
  "profile_id": "huawei_sun2000_v1",
  "manufacturer": "Huawei",
  "model": "SUN2000",
  "protocol": "modbus_tcp",
  "default_port": 502,
  "default_slave_id": 0,
  "registers": {
    "soc_pct":   {"address": 37760, "type": "uint16", "scale": 0.1, "unit": "%"},
    "power_kw":  {"address": 37113, "type": "int32",  "scale": 0.001, "unit": "kW"},
    "temp_c":    {"address": 35182, "type": "int16",  "scale": 0.1, "unit": "°C"}
  }
}
```

### Paso 2 — Crear tu perfil

```bash
cp registry/huawei_sun2000.json registry/mi_inversor_modelo.json
# Editar con los registros Modbus de tu fabricante
```

Los tres registros **obligatorios** son `soc_pct`, `power_kw` y `temp_c`. Los demás son opcionales.

### Paso 3 — Validar el perfil

```bash
make validate-registry
# Debe pasar sin errores antes de abrir el PR
```

### Paso 4 — Abrir el PR

```bash
git checkout -b feat/hardware-profile-FABRICANTE-MODELO
git add registry/mi_inversor_modelo.json
git commit -m "feat(registry): add FABRICANTE MODELO profile"
git push origin feat/hardware-profile-FABRICANTE-MODELO
```

Luego ve a GitHub y abre el Pull Request. El team lo revisa en ≤ 3 días hábiles.

> **TIP:** Menciona en el PR qué firmware version del inversor usaste para identificar los registros.

---

## Contribución 2 — Reportar un bug

Usa el template de issue en GitHub:  
→ [Nuevo issue → Bug Report](https://github.com/bess-solutions/open-bess-edge/issues/new?template=bug_report.yml)

Los logs más útiles para el equipo:

```bash
# Logs del gateway (últimas 50 líneas)
docker logs bessai-edge 2>&1 | tail -50

# Estado de compliance
curl http://localhost:8000/compliance/report | python3 -m json.tool

# Versión exacta
git log --oneline -1
docker inspect bessai-edge | python3 -c "import sys,json; d=json.load(sys.stdin)[0]; print(d['Config']['Image'])"
```

---

## Contribución 3 — Mejorar documentación

La documentación está en `docs/` en formato Markdown. Para visualizarla localmente:

```bash
pip install mkdocs-material
mkdocs serve   # → http://localhost:8001
```

Para traducir partes al inglés (el repo está en español/inglés mezclado):
- Abre un PR con la traducción
- El team la revisa y la integra

---

## Proceso de revisión — qué esperar

```
Tu PR abierto
    │
    ▼
CI automático (~5 min)  ← lint, type-check, tests, security scan
    │
    ▼
Revisión del team (~3 días hábiles)
    │
    ├── ✅ Aprobado → Merge a main
    └── 💬 Cambios solicitados → Iterar
```

### Estándares de calidad obligatorios

- `make lint` debe pasar sin errores
- `make test` debe pasar (o documentar por qué el test no aplica)
- Nuevos archivos Python deben tener type hints
- Commits en formato [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, etc.

---

## Primeros issues recomendados para newcomers

Ver [GOOD_FIRST_ISSUES.md](GOOD_FIRST_ISSUES.md) para issues etiquetados con `good-first-issue`.

Los más accesibles actualmente:
- Agregar un perfil JSON de hardware faltante
- Mejorar el mensaje de error cuando `MODBUS_HOST` no es accesible
- Traducir secciones del `ADOPTER_HUB.md` al inglés

---

## Stack técnico de referencia

| Capa | Tecnología |
|------|-----------|
| Runtime | Python 3.11+ / asyncio |
| Protocolo industrial | pymodbus 3.x |
| API REST | FastAPI + uvicorn |
| Observabilidad | Prometheus + structlog + OpenTelemetry |
| IA / ML | ONNX Runtime + scikit-learn |
| Tests | pytest + pytest-asyncio |
| Linter | ruff + mypy strict |
| Contenedores | Docker multi-arch (amd64/arm64) |
| CI | GitHub Actions |

---

*¿Tienes dudas? [Abre un issue](https://github.com/bess-solutions/open-bess-edge/issues/new?labels=question) o escríbenos a `ingenieria@bess-solutions.cl`.*
