"""
publisher/full_project_publisher.py — Publica el proyecto COMPLETO al repo
──────────────────────────────────────────────────────────────────────────────
Publica al repositorio open-bess-edge:
  1. Reportes de análisis (docs/compliance/)
  2. BEPs generados (docs/bep/)
  3. Datos crudos comprimidos (data/)
  4. El proyecto sec-bess-ingestor completo (sec-bess-ingestor/)
  5. GitHub Actions workflow (.github/workflows/)

Esto garantiza que el repo tenga TODO lo necesario para reproducir el análisis
independientemente de lo que esté o no esté en el repo en el momento de publicar.
"""

from __future__ import annotations

import base64
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from config import (
    GITHUB_API_URL,
    GITHUB_BASE_BRANCH,
    GITHUB_OWNER,
    GITHUB_REPO,
    GITHUB_TOKEN,
    RAW_DIR,
    REPORTS_DIR,
)

# Aliases para compatibilidad interna
BESS_EDGE_REPO = f"{GITHUB_OWNER}/{GITHUB_REPO}"
GITHUB_API_BASE = f"{GITHUB_API_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
GITHUB_DEFAULT_BRANCH = GITHUB_BASE_BRANCH


logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent.parent


# ─── Qué publicar ────────────────────────────────────────────────────────────

PUBLISH_MANIFEST = [
    # Reportes de análisis normativa
    {
        "local": REPORTS_DIR,
        "glob": "gap_analysis_*.md",
        "remote": "docs/compliance/sec_gap_analysis.md",
        "description": "Reporte completo de brechas normativas",
        "take_latest": True,
    },
    {
        "local": REPORTS_DIR,
        "glob": "gap_summary_*.md",
        "remote": "docs/compliance/sec_gap_summary.md",
        "description": "Resumen ejecutivo de brechas",
        "take_latest": True,
    },
    # BEPs generados
    {
        "local": ROOT_DIR / "data" / "beps",
        "glob": "BEP-04*.md",
        "remote_prefix": "docs/bep/",
        "description": "BEPs normativos SEC Chile (BEP-0400+)",
        "take_latest": False,  # Subir todos
    },
    # Datos de scraping crudos (solo BESS, compacto)
    {
        "local": RAW_DIR,
        "glob": "sec_aggressive_*.json",
        "remote": "data/sec_normativa_raw.json",
        "description": "Datos crudos de SEC Chile (modo agresivo)",
        "take_latest": True,
        "max_size_kb": 500,  # Limite de tamaño para el repo
    },
    # Workflow de automatización
    {
        "local": ROOT_DIR,
        "glob": "sec_gap_analysis.yml",
        "remote": ".github/workflows/sec_gap_analysis.yml",
        "description": "GitHub Actions workflow p/ automatización semanal",
        "take_latest": True,
    },
    # Proyecto completo sec-bess-ingestor
    {
        "local": ROOT_DIR,
        "glob": "scraper/**/*.py",
        "remote_prefix": "sec-bess-ingestor/scraper/",
        "description": "Scraper modules",
        "take_latest": False,
        "is_code": True,
    },
    {
        "local": ROOT_DIR,
        "glob": "analysis/**/*.py",
        "remote_prefix": "sec-bess-ingestor/analysis/",
        "description": "Analysis modules",
        "take_latest": False,
        "is_code": True,
    },
    {
        "local": ROOT_DIR,
        "glob": "publisher/**/*.py",
        "remote_prefix": "sec-bess-ingestor/publisher/",
        "description": "Publisher modules",
        "take_latest": False,
        "is_code": True,
    },
    {
        "local": ROOT_DIR,
        "glob": "scripts/**/*.py",
        "remote_prefix": "sec-bess-ingestor/scripts/",
        "description": "Scripts",
        "take_latest": False,
        "is_code": True,
    },
    {
        "local": ROOT_DIR,
        "glob": "*.py",
        "remote_prefix": "sec-bess-ingestor/",
        "description": "Root Python files (cli.py, config.py)",
        "take_latest": False,
        "is_code": True,
    },
    {
        "local": ROOT_DIR,
        "glob": "*.txt",
        "remote_prefix": "sec-bess-ingestor/",
        "description": "requirements.txt",
        "take_latest": False,
        "is_code": True,
        "exclude": [],
    },
    {
        "local": ROOT_DIR,
        "glob": "*.toml",
        "remote_prefix": "sec-bess-ingestor/",
        "description": "pyproject.toml",
        "take_latest": False,
        "is_code": True,
    },
    {
        "local": ROOT_DIR,
        "glob": "README.md",
        "remote": "sec-bess-ingestor/README.md",
        "description": "README del proyecto",
        "take_latest": True,
    },
    {
        "local": ROOT_DIR,
        "glob": ".env.example",
        "remote": "sec-bess-ingestor/.env.example",
        "description": "Template de variables de entorno",
        "take_latest": True,
    },
]


class FullProjectPublisher:
    """
    Publica el proyecto completo al repositorio open-bess-edge.
    Crea o actualiza todos los archivos en una sola rama y abre un PR.
    """

    def __init__(
        self,
        dry_run: bool = True,
        token: str | None = None,
        repo: str = BESS_EDGE_REPO,
    ):
        self.dry_run = dry_run
        self._token = token or GITHUB_TOKEN
        self._repo = repo
        self._api_base = f"{GITHUB_API_URL}/repos/{repo}"
        self._branch: str | None = None


        if not self._token and not dry_run:
            raise RuntimeError(
                "GITHUB_TOKEN no configurado. "
                "Exporta: $env:GITHUB_TOKEN='ghp_xxxx'"
            )

        self._session = self._build_session()

    def _build_session(self) -> requests.Session:
        s = requests.Session()
        if self._token:
            s.headers.update({
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            })
        s.headers.update({"Content-Type": "application/json"})
        return s

    # ── Publicación principal ────────────────────────────────────────────────

    def publish_all(self) -> dict:
        """
        Publica ALL artefactos al repo.
        Retorna dict con resultados de cada categoría.
        """
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self._branch = f"sec-update/{ts}"

        results = {
            "branch": self._branch,
            "files_published": [],
            "files_skipped": [],
            "errors": [],
            "pull_request": None,
        }

        if not self.dry_run:
            logger.info(f"Creando rama: {self._branch}")
            self._create_branch()
        else:
            logger.info(f"[DRY-RUN] Rama que se crearía: {self._branch}")

        # Recolectar todos los archivos a publicar
        to_publish = self._collect_files()
        logger.info(f"Total archivos a publicar: {len(to_publish)}")

        for item in to_publish:
            try:
                self._publish_file(item, results)
                time.sleep(0.2)  # Rate limiting gentil
            except Exception as exc:
                logger.error(f"Error publicando {item['remote_path']}: {exc}")
                results["errors"].append({
                    "path": item["remote_path"],
                    "error": str(exc),
                })

        # Abrir PR
        pr = self._open_pr(results)
        results["pull_request"] = pr

        logger.info(
            f"\n{'[DRY-RUN] ' if self.dry_run else ''}Resumen de publicación:\n"
            f"  Archivos publicados: {len(results['files_published'])}\n"
            f"  Archivos omitidos:   {len(results['files_skipped'])}\n"
            f"  Errores:             {len(results['errors'])}\n"
            f"  PR:                  {pr.get('html_url', '[dry-run]')}"
        )
        return results

    def _collect_files(self) -> list[dict]:
        """Recolecta todos los archivos según el manifest."""
        files = []
        for spec in PUBLISH_MANIFEST:
            local_dir = Path(spec["local"])
            glob = spec["glob"]

            # Buscar archivos
            matches = sorted(local_dir.glob(glob))
            if not matches:
                logger.debug(f"Sin archivos para: {local_dir}/{glob}")
                continue

            # Tomar el más reciente o todos
            if spec.get("take_latest"):
                matches = [matches[-1]]  # Último generado (glob ordena por nombre↑, timestamp en nombre)

            for path in matches:
                # Verificar tamaño
                size_kb = path.stat().st_size / 1024
                max_kb = spec.get("max_size_kb", 5000)
                if size_kb > max_kb:
                    logger.warning(f"Archivo muy grande ({size_kb:.0f}KB > {max_kb}KB): {path.name}")
                    continue

                # Calcular ruta remota
                if "remote" in spec:
                    remote_path = spec["remote"]
                elif "remote_prefix" in spec:
                    # Para globos con **/, conservar subcarpeta
                    try:
                        rel = path.relative_to(local_dir)
                    except ValueError:
                        rel = Path(path.name)
                    remote_path = spec["remote_prefix"] + str(rel).replace("\\", "/")
                else:
                    continue

                files.append({
                    "local_path": path,
                    "remote_path": remote_path,
                    "description": spec.get("description", ""),
                    "is_code": spec.get("is_code", False),
                })

        return files

    def _publish_file(self, item: dict, results: dict) -> None:
        local_path: Path = item["local_path"]
        remote_path: str = item["remote_path"]

        content_bytes = local_path.read_bytes()
        content_b64 = base64.b64encode(content_bytes).decode("ascii")

        if self.dry_run:
            logger.info(f"  [DRY-RUN] PUT {remote_path} ({len(content_bytes)/1024:.1f} KB)")
            results["files_published"].append(remote_path)
            return

        # Obtener SHA si el archivo ya existe (para updates)
        sha = self._get_file_sha(remote_path)

        payload: dict = {
            "message": f"sec-ingestor: upsert {remote_path}",
            "content": content_b64,
            "branch": self._branch,
        }
        if sha:
            payload["sha"] = sha

        resp = self._api("PUT", f"/contents/{remote_path}", json=payload)
        if resp and resp.status_code in (200, 201):
            logger.info(f"  ✅ {remote_path}")
            results["files_published"].append(remote_path)
        else:
            status = resp.status_code if resp else "N/A"
            results["errors"].append({"path": remote_path, "status": status})

    def _get_file_sha(self, path: str) -> str | None:
        resp = self._api("GET", f"/contents/{path}", params={"ref": self._branch})
        if resp and resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict):
                return data.get("sha")
        return None

    def _create_branch(self) -> None:
        # Obtener SHA del branch base
        resp = self._api("GET", f"/git/ref/heads/{GITHUB_DEFAULT_BRANCH}")
        if not resp or resp.status_code != 200:
            raise RuntimeError(f"No se pudo obtener ref de {GITHUB_DEFAULT_BRANCH}")
        sha = resp.json()["object"]["sha"]

        # Crear rama
        self._api("POST", "/git/refs", json={
            "ref": f"refs/heads/{self._branch}",
            "sha": sha,
        })

    def _open_pr(self, results: dict) -> dict:
        n_files = len(results["files_published"])
        n_errors = len(results["errors"])

        body = (
            "## Actualización normativa automática — SEC Chile 🇨🇱\n\n"
            f"**Generado:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n"
            f"**Archivos publicados:** {n_files}\n"
            f"**Errores:** {n_errors}\n\n"
            "### Contenido de este PR\n\n"
            "| Carpeta | Contenido |\n|---|---|\n"
            "| `docs/compliance/` | Reporte de brechas normativas + resumen ejecutivo |\n"
            "| `docs/bep/` | BEPs normativos BEP-0400 a BEP-0403 |\n"
            "| `sec-bess-ingestor/` | Proyecto completo de ingesta: scraper, análisis, publisher |\n"
            "| `.github/workflows/` | Workflow de automatización semanal |\n"
            "| `data/` | Datos crudos de scraping SEC Chile |\n\n"
            "### Brechas críticas identificadas\n\n"
            "| GAP | Norma | Estado |\n|---|---|---|\n"
            "| GAP-001 | NTSyCS Ramp Rate | 🔄 Planificado |\n"
            "| GAP-002 | NTSyCS PFR Droop | 🔄 Planificado |\n"
            "| GAP-003 | Telemetría CEN | ⚠️ Parcial |\n"
            "| GAP-004 | IEC 60870-5-104 | 🔄 Planificado |\n\n"
            "> ⚠️ **Este PR requiere revisión humana antes de hacer merge.**\n"
            "> No se hacen merges automáticos.\n\n"
            "---\n"
            "*Generado por [sec-bess-ingestor](sec-bess-ingestor/README.md)*"
        )

        if self.dry_run:
            logger.info(f"  [DRY-RUN] PR que se abriría: {self._branch} → {GITHUB_DEFAULT_BRANCH}")
            return {"html_url": f"[DRY-RUN] {self._branch} → {GITHUB_DEFAULT_BRANCH}", "dry_run": True}

        resp = self._api("POST", "/pulls", json={
            "title": f"🇨🇱 SEC Normative Update — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            "head": self._branch,
            "base": GITHUB_DEFAULT_BRANCH,
            "body": body,
            "draft": False,
        })

        if resp and resp.status_code == 201:
            pr_data = resp.json()
            logger.info(f"  🚀 PR abierto: {pr_data.get('html_url')}")
            return pr_data
        else:
            logger.error(f"  ❌ No se pudo abrir PR: {resp.status_code if resp else 'N/A'}")
            return {}

    def _api(self, method: str, path: str, **kwargs) -> requests.Response | None:
        url = self._api_base + path
        try:
            resp = self._session.request(method, url, timeout=30, **kwargs)
            return resp
        except Exception as exc:
            logger.error(f"API error {method} {path}: {exc}")
            return None
