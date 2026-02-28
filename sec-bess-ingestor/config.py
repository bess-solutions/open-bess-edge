"""
config.py — Configuración centralizada del proyecto sec-bess-ingestor
───────────────────────────────────────────────────────────────────────
Autor: BESSAI / Antigravity  •  Fecha: 2026-02-27
"""

import os
from pathlib import Path

# ─── Cargar .env automáticamente (si existe) ─────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env", override=False)
except ImportError:
    pass  # python-dotenv es opcional; las vars de entorno se toman del shell

# ─── Rutas base ─────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent.resolve()
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
REPORTS_DIR = DATA_DIR / "reports"
LOGS_DIR = ROOT_DIR / "logs"

for _d in [RAW_DIR, REPORTS_DIR, LOGS_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# ─── SEC Chile ───────────────────────────────────────────────────────────────
SEC_BASE_URL = "https://www.sec.cl"
SEC_USER_AGENT = (
    "Mozilla/5.0 (compatible; sec-bess-ingestor/1.0; "
    "+https://github.com/bess-solutions/open-bess-edge)"
)
SEC_REQUEST_DELAY = 1.5        # segundos entre requests (respetuoso)
SEC_REQUEST_TIMEOUT = 30       # segundos timeout
SEC_MAX_RETRIES = 3            # reintentos por página
SEC_MAX_PAGES = 50             # máximo de páginas paginadas por sección

# Secciones a raspar — (nombre_clave, URL_path, descripción)
SEC_SECTIONS = [
    {
        "key": "normativa",
        "url": f"{SEC_BASE_URL}/normativa/",
        "label": "Normativa y Legislación",
        "type": "normativa",
        "bess_relevant": True,
    },
    {
        "key": "resoluciones_exentas",
        "url": f"{SEC_BASE_URL}/resoluciones-exentas/",
        "label": "Resoluciones Exentas",
        "type": "resolucion",
        "bess_relevant": True,
    },
    {
        "key": "circulares",
        "url": f"{SEC_BASE_URL}/circulares/",
        "label": "Circulares",
        "type": "circular",
        "bess_relevant": True,
    },
    {
        "key": "reglamentos",
        "url": f"{SEC_BASE_URL}/reglamentos/",
        "label": "Reglamentos",
        "type": "reglamento",
        "bess_relevant": True,
    },
    {
        "key": "energias_renovables",
        "url": f"{SEC_BASE_URL}/energias-renovables-y-electromovilidad/",
        "label": "Energías Renovables y Electromovilidad",
        "type": "info",
        "bess_relevant": True,
    },
    {
        "key": "noticias",
        "url": f"{SEC_BASE_URL}/noticias/",
        "label": "Noticias SEC",
        "type": "noticia",
        "bess_relevant": False,
    },
    {
        "key": "fiscalizacion",
        "url": f"{SEC_BASE_URL}/fiscalizacion/",
        "label": "Fiscalización",
        "type": "fiscalizacion",
        "bess_relevant": True,
    },
    {
        "key": "sanciones",
        "url": f"{SEC_BASE_URL}/sanciones/",
        "label": "Sanciones y Expedientes",
        "type": "sancion",
        "bess_relevant": False,
    },
]

# Palabras clave para filtrar contenido relevante a BESS
BESS_KEYWORDS = [
    "bess", "batería", "baterias", "almacenamiento", "storage",
    "fotovoltaico", "solar", "renovable", "ernc", "pmgd", "pmpe",
    "microgrid", "generación distribuida", "generacion distribuida",
    "inversor", "inverter", "frecuencia", "tensión", "tension",
    "ntscys", "ntscys", "coordinador eléctrico", "cen", "sin",
    "interconexión", "interconexion", "inyección", "inyeccion",
    "tarifa", "subtransmisión", "decreto 88", "decreto 24",
    "ley 20.936", "ley 21.185", "ley 20.698",
    "calificación energética", "autoconsumo", "net metering",
    "sistema fotovoltaico", "energía solar", "energia solar",
    "control de potencia", "ramp rate", "despacho", "dispatch",
]

# ─── GitHub API ──────────────────────────────────────────────────────────────
GITHUB_OWNER = "bess-solutions"
GITHUB_REPO = "open-bess-edge"
GITHUB_BASE_BRANCH = "main"
GITHUB_API_URL = "https://api.github.com"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")  # Nunca hardcoded
GITHUB_COMMITTER_NAME = "sec-bess-ingestor[bot]"
GITHUB_COMMITTER_EMAIL = "sec-ingestor@bess-solutions.ai"

# Ruta en el repo donde se publicarán los reportes
GITHUB_REPORT_PATH = "docs/compliance/sec_gap_analysis.md"
GITHUB_SUMMARY_PATH = "docs/compliance/sec_gap_summary.md"
GITHUB_RAW_DATA_PATH = "data/sec_normativa_raw.json"

# ─── open-bess-edge local (si está clonado al lado) ──────────────────────────
BESS_EDGE_LOCAL = os.environ.get(
    "BESS_EDGE_LOCAL",
    str(ROOT_DIR.parent / "open-bess-edge"),
)
BESS_EDGE_GITHUB_RAW = (
    "https://raw.githubusercontent.com/bess-solutions/open-bess-edge/main/"
)

# Documentos de compliance BESSAI a leer para análisis
BESS_COMPLIANCE_DOCS = [
    "docs/compliance/ntscys_compliance.md",
    "docs/compliance/iec62443_mapping.md",
    "docs/compliance/iec_62443_sl2_certification_path.md",
    "docs/bep/BEP-0100.md",
    "docs/ROADMAP.md",
    "README.md",
]

# ─── Logging ─────────────────────────────────────────────────────────────────
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_FILE = LOGS_DIR / "sec_ingestor.log"
