# 🇨🇱 sec-bess-ingestor
## Mega-Scraper SEC Chile + Analizador de Brechas Normativas para open-bess-edge

> Sistema autónomo que raspa la Superintendencia de Electricidad y Combustibles
> (SEC Chile), identifica brechas regulatorias entre la normativa nacional y el
> repositorio [open-bess-edge](https://github.com/bess-solutions/open-bess-edge),
> y publica los reportes automáticamente vía Pull Request.

---

## ⚡ Quick Start

```bash
# 1. Clonar e instalar
cd sec-bess-ingestor
pip install -r requirements.txt

# 2. Raspar SEC Chile
python cli.py scrape

# 3. Analizar brechas normativas
python cli.py analyze

# 4. Generar reporte Markdown
python cli.py report --print

# 5. Publicar al repo (requiere GITHUB_TOKEN)
$env:GITHUB_TOKEN = "ghp_xxxxxxxxxxxx"   # PowerShell
python cli.py publish --no-dry-run

# --- o todo en uno ---
python cli.py update --no-dry-run
```

---

## 📋 Comandos CLI

| Comando | Descripción |
|---|---|
| `python cli.py scrape` | Raspa SEC Chile y guarda JSON en `data/raw/` |
| `python cli.py scrape --section normativa` | Solo raspa una sección |
| `python cli.py scrape --bess-only` | Solo guarda documentos BESS relevantes |
| `python cli.py analyze` | Analiza brechas usando último scraping |
| `python cli.py analyze --data-file <path>` | Analiza un archivo JSON específico |
| `python cli.py report` | Genera reporte Markdown en `data/reports/` |
| `python cli.py report --print` | Adicionalmente imprime resumen en pantalla |
| `python cli.py publish` | Publica al repo (**dry-run por defecto**) |
| `python cli.py publish --no-dry-run` | Publica de verdad (requiere `GITHUB_TOKEN`) |
| `python cli.py update` | Flujo completo: scrape→analyze→report→publish |
| `python cli.py update --no-dry-run` | Flujo completo con push real |
| `python cli.py --verbose <cmd>` | Logging detallado (DEBUG) |

---

## 🔍 Secciones Raspadas de SEC Chile

| Key | Sección |
|---|---|
| `normativa` | Normativa y Legislación |
| `resoluciones_exentas` | Resoluciones Exentas |
| `circulares` | Circulares |
| `reglamentos` | Reglamentos |
| `energias_renovables` | Energías Renovables y Electromovilidad |
| `noticias` | Noticias (filtradas por BESS relevance) |
| `fiscalizacion` | Fiscalización |
| `sanciones` | Sanciones y Expedientes |

---

## 🚨 Brechas Normativas Detectadas (Snapshot 2026-02)

| ID | Norma | Prioridad | Estado BESSAI |
|---|---|---|---|
| GAP-001 | NTSyCS Cap. 4.2 — Ramp Rate Limiting | 🔴 Crítico | 🔄 Planificado v2.0 |
| GAP-002 | NTSyCS Cap. 4.3 — PFR Droop Curve | 🔴 Crítico | 🔄 Planificado v2.0 |
| GAP-003 | NTSyCS Cap. 6.1 — Telemetría CEN | 🔴 Crítico | ⚠️ Parcial |
| GAP-004 | NTSyCS Cap. 6.2 — IEC 60870-5-104 SCADA | 🔴 Crítico | 🔄 Planificado v2.0 |
| GAP-005 | NTSyCS 2024 — Canal TLS mTLS→CEN | 🟡 Medio | 🔄 Planificado v1.5 |
| GAP-006 | IEEE 2030.5 — DER en distribución | 🟡 Medio | ⚠️ Parcial |
| GAP-007 | Decreto 88/2023 — PMGD con BESS | 🟡 Medio | 🔄 Planificado |
| GAP-008 | Ley 21.185 — ERNC almacenamiento | 🟢 Bajo | 🔄 Planificado |
| GAP-009 | Res. SEC 2024 — IEC 62443 SL-2 | 🟡 Medio | 🔄 Planificado |
| GAP-010 | NTCSE — Calidad de Energía THD/Flicker | 🟡 Medio | ⚠️ Parcial |
| GAP-011 | NTSyCS Cap. 4.4 — Control Potencia Reactiva | 🟡 Medio | ⚠️ Parcial |

---

## 🏗️ Arquitectura del Proyecto

```
sec-bess-ingestor/
├── scraper/
│   ├── sec_scraper.py        # Motor principal (paginación, dispatcher, persistencia)
│   └── utils.py              # robots.txt, rate-limiting, HTML→text, BESS relevance
├── analysis/
│   ├── bess_context.py       # Carga docs open-bess-edge (local o GitHub raw)
│   ├── gap_analyzer.py       # 11 reglas normativas → GapItem list
│   └── report_builder.py     # Genera Markdown completo + resumen ejecutivo
├── publisher/
│   └── github_publisher.py   # GitHub API: branch → upsert → PR
├── tests/
│   ├── fixtures/             # sample_sec_data.json
│   ├── test_scraper_utils.py
│   ├── test_gap_analyzer.py
│   └── test_publisher.py
├── data/
│   ├── raw/                  # JSONs de scraping (generados en runtime)
│   └── reports/              # Reportes Markdown (generados en runtime)
├── cli.py                    # CLI principal (argparse)
├── config.py                 # Configuración centralizada
├── pyproject.toml            # pytest config
└── requirements.txt
```

---

## 🔐 Configuración variables de entorno

| Variable | Descripción | Requerida |
|---|---|---|
| `GITHUB_TOKEN` | PAT con scope `repo` en `bess-solutions/open-bess-edge` | Solo para `publish --no-dry-run` |
| `BESS_EDGE_LOCAL` | Ruta local a clone de open-bess-edge (optimiza lectura de docs) | Opcional |
| `LOG_LEVEL` | Nivel de logging (`DEBUG`, `INFO`, `WARNING`) | Opcional |

```powershell
# PowerShell
$env:GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxx"
$env:BESS_EDGE_LOCAL = "C:\repos\open-bess-edge"
```

---

## 🧪 Ejecutar Tests

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

---

## 📚 Marco Normativo Cubierto

- **NTSyCS 2022** — Norma Técnica de Seguridad y Calidad del Servicio (CEN)
- **Decreto N°88/2020** (mod. 2023) — Reglamento PMGD
- **Ley N°21.185** — ERNC y almacenamiento
- **Resolución Exenta SEC 2024** — Ciberseguridad infraestructura crítica
- **IEC 62443 SL-1/SL-2** — Ciberseguridad sistemas industriales
- **IEC 60870-5-104** — Protocolo SCADA para generación/almacenamiento
- **IEEE 2030.5** — Comunicación DER en distribución
- **NTCSE** — Norma Técnica de Calidad de Servicio Eléctrico

---

## 🔄 Flujo de Actualización Automática

```
SEC Chile   →   scrape   →   data/raw/sec_YYYYMMDD.json
                               ↓
open-bess-edge docs  →   analyze  →   11 GapItems con prioridad
                               ↓
                          report   →   data/reports/gap_analysis_*.md
                               ↓
                          publish  →   branch: sec-update/YYYYMMDD
                                       ↓
                               PUT docs/compliance/sec_gap_analysis.md
                                       ↓
                               Pull Request → main (¡para revisión humana!)
```

> **Nota de seguridad:** El paso `publish` siempre crea un PR (no hace merge directo).  
> Un humano debe revisar y aprobar antes de que los cambios entren a `main`.

---

*Proyecto generado por [BESSAI / Antigravity](https://github.com/bess-solutions/open-bess-edge) — 2026*
