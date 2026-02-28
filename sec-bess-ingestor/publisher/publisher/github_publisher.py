"""
publisher/github_publisher.py — Publica reportes en open-bess-edge via GitHub API
──────────────────────────────────────────────────────────────────────────────────
Estrategia:
  1. Crea branch  sec-update/<YYYYMMDD>
  2. Upsert archivos vía PUT /repos/.../contents/...
  3. Abre Pull Request apuntando a `main`
  4. En dry-run mode: sólo muestra el payload sin hacer push

Requiere: GITHUB_TOKEN con scope `repo` en bess-solutions/open-bess-edge
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

from config import (
    GITHUB_API_URL, GITHUB_BASE_BRANCH, GITHUB_COMMITTER_EMAIL,
    GITHUB_COMMITTER_NAME, GITHUB_OWNER, GITHUB_RAW_DATA_PATH,
    GITHUB_REPO, GITHUB_REPORT_PATH, GITHUB_SUMMARY_PATH, GITHUB_TOKEN,
)

logger = logging.getLogger(__name__)


class GitHubPublisher:
    """
    Publica reportes de brechas al repositorio open-bess-edge.

    Ejemplo de uso:
        pub = GitHubPublisher()
        pub.publish(full_report_path, summary_path)

    En modo dry-run:
        pub = GitHubPublisher(dry_run=True)
        pub.publish(full_report_path, summary_path)
    """

    def __init__(self, dry_run: bool = False, token: Optional[str] = None):
        self.dry_run = dry_run
        self._token = token or GITHUB_TOKEN
        if not self._token and not dry_run:
            raise RuntimeError(
                "GITHUB_TOKEN no configurado. "
                "Exporta: $env:GITHUB_TOKEN='ghp_xxxx' (PowerShell) "
                "o set GITHUB_TOKEN=ghp_xxxx (cmd)"
            )
        self._session = self._build_session()
        self._branch: Optional[str] = None

    # ── Sesión HTTP ─────────────────────────────────────────────────────────

    def _build_session(self) -> requests.Session:
        s = requests.Session()
        s.headers.update({
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "sec-bess-ingestor/1.0",
        })
        if self._token:
            s.headers["Authorization"] = f"Bearer {self._token}"
        return s

    def _api(self, method: str, path: str, **kwargs) -> dict:
        url = f"{GITHUB_API_URL}{path}"
        if self.dry_run:
            logger.info(f"[DRY-RUN] {method.upper()} {url}")
            if "json" in kwargs:
                logger.info(f"  Payload: {json.dumps(kwargs['json'], indent=2)[:500]}…")
            return {"dry_run": True, "url": url}
        resp = self._session.request(method, url, **kwargs)
        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            logger.error(f"GitHub API error: {exc}\nBody: {resp.text[:500]}")
            raise
        return resp.json() if resp.content else {}

    # ── Branch ──────────────────────────────────────────────────────────────

    def _get_base_sha(self) -> str:
        """SHA del HEAD de la rama base (main)."""
        data = self._api("get", f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/git/ref/heads/{GITHUB_BASE_BRANCH}")
        if self.dry_run:
            return "dryrun_sha_000000"
        return data["object"]["sha"]

    def _create_branch(self, branch_name: str, sha: str) -> None:
        """Crea un branch a partir del SHA del HEAD base."""
        self._api(
            "post",
            f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/git/refs",
            json={"ref": f"refs/heads/{branch_name}", "sha": sha},
        )
        logger.info(f"Branch creado: {branch_name}")

    def _ensure_branch(self) -> str:
        """Crea el branch sec-update/<fecha> si no existe."""
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        branch_name = f"sec-update/{today}"
        if self._branch == branch_name:
            return branch_name
        sha = self._get_base_sha()
        # Verificar si ya existe
        check = self._api("get", f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/git/ref/heads/{branch_name}")
        if not self.dry_run and "ref" not in check:
            self._create_branch(branch_name, sha)
        elif self.dry_run:
            logger.info(f"[DRY-RUN] Branch que se crearía: {branch_name}")
        self._branch = branch_name
        return branch_name

    # ── Upsert de archivo ───────────────────────────────────────────────────

    def _get_file_sha(self, path: str, branch: str) -> Optional[str]:
        """Obtiene el SHA del archivo si ya existe en el repo."""
        try:
            data = self._api(
                "get",
                f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{path}",
                params={"ref": branch},
            )
            if self.dry_run:
                return None
            return data.get("sha")
        except Exception:
            return None

    def _upsert_file(
        self,
        repo_path: str,
        content: str,
        commit_message: str,
        branch: str,
    ) -> dict:
        """Crea o actualiza un archivo en el repositorio."""
        b64_content = base64.b64encode(content.encode("utf-8")).decode("ascii")
        existing_sha = self._get_file_sha(repo_path, branch)

        payload: dict = {
            "message": commit_message,
            "content": b64_content,
            "branch": branch,
            "committer": {
                "name": GITHUB_COMMITTER_NAME,
                "email": GITHUB_COMMITTER_EMAIL,
            },
        }
        if existing_sha:
            payload["sha"] = existing_sha

        result = self._api(
            "put",
            f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{repo_path}",
            json=payload,
        )
        action = "Actualizado" if existing_sha else "Creado"
        logger.info(f"📁 {action}: {repo_path} en branch {branch}")
        return result

    # ── Pull Request ─────────────────────────────────────────────────────────

    def _create_pull_request(
        self,
        branch: str,
        title: str,
        body: str,
    ) -> dict:
        """Abre un PR de branch → main."""
        result = self._api(
            "post",
            f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/pulls",
            json={
                "title": title,
                "body": body,
                "head": branch,
                "base": GITHUB_BASE_BRANCH,
                "draft": False,
            },
        )
        if not self.dry_run:
            pr_url = result.get("html_url", "N/A")
            logger.info(f"🚀 PR creado: {pr_url}")
        return result

    # ── Método público ──────────────────────────────────────────────────────

    def publish(
        self,
        full_report_path: str,
        summary_path: str,
        sec_raw_path: Optional[str] = None,
    ) -> dict:
        """
        Flujo completo de publicación:
        1. Crea branch sec-update/<fecha>
        2. Sube reporte completo, resumen y (opcionalmente) datos crudos
        3. Abre PR

        Retorna dict con URLs del PR y archivos subidos.
        """
        if self.dry_run:
            logger.info("=" * 60)
            logger.info("🧪 MODO DRY-RUN — No se hará ningún push al repo")
            logger.info("=" * 60)

        branch = self._ensure_branch()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        commit_base = f"chore(sec): normative gap analysis update {today}"

        results = {}

        # 1. Reporte completo
        full_content = Path(full_report_path).read_text(encoding="utf-8")
        results["full_report"] = self._upsert_file(
            GITHUB_REPORT_PATH,
            full_content,
            f"{commit_base} — full report",
            branch,
        )

        # 2. Resumen ejecutivo
        summary_content = Path(summary_path).read_text(encoding="utf-8")
        results["summary"] = self._upsert_file(
            GITHUB_SUMMARY_PATH,
            summary_content,
            f"{commit_base} — executive summary",
            branch,
        )

        # 3. Datos crudos (opcional)
        if sec_raw_path and Path(sec_raw_path).exists():
            raw_content = Path(sec_raw_path).read_text(encoding="utf-8")
            # Comprimir datos crudos si son muy grandes
            if len(raw_content) > 1_000_000:
                logger.warning("Datos crudos > 1MB, omitiendo del PR")
            else:
                results["raw_data"] = self._upsert_file(
                    GITHUB_RAW_DATA_PATH,
                    raw_content,
                    f"{commit_base} — raw SEC data",
                    branch,
                )

        # 4. Pull Request
        pr_body = summary_content + "\n\n---\n*Generado por sec-bess-ingestor*"
        pr_result = self._create_pull_request(
            branch=branch,
            title=f"🔍 SEC Normative Gap Analysis — {today}",
            body=pr_body[:65_000],  # GitHub PR body limit
        )
        results["pull_request"] = pr_result

        if self.dry_run:
            logger.info("✅ Dry-run completado. Payload revisado, nada fue publicado.")
        else:
            pr_url = pr_result.get("html_url", "N/A")
            logger.info(f"✅ Publicación completada. PR: {pr_url}")

        return results
