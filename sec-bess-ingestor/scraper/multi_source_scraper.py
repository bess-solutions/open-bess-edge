"""
scraper/multi_source_scraper.py — Scraper multi-fuente para normativa chilena
──────────────────────────────────────────────────────────────────────────────
Fuentes adicionales a sec.cl que contienen normativa BESS relevante:

  • coordinador.cl  — NTSyCS, instrucciones de operación, ERNC
  • bcn.cl          — Biblioteca del Congreso: leyes, decretos, reglamentos
  • minenergia.cl   — Ministerio de Energía: políticas, PELP, licitaciones
  • cnenergia.cl    — Comisión Nacional de Energía: tarifas, normativas PMG

Se alimenta al GapAnalyzer junto con los datos de SEC para un análisis
más completo y enriquecido.
"""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from config import (
    BESS_KEYWORDS, RAW_DIR, SEC_REQUEST_DELAY,
    SEC_REQUEST_TIMEOUT, SEC_USER_AGENT,
)
from scraper.utils import (
    bess_relevance_score, content_hash, extract_date,
    extract_pdf_links, html_to_clean_text, is_bess_relevant,
)

logger = logging.getLogger(__name__)

# ─── Fuentes adicionales ─────────────────────────────────────────────────────

EXTRA_SOURCES = [
    # ── Coordinador Eléctrico Nacional ──────────────────────────────────────
    {
        "source": "coordinador",
        "label": "Coordinador Eléctrico Nacional",
        "base_url": "https://www.coordinador.cl",
        "sections": [
            {"key": "normativa_cen", "url": "https://www.coordinador.cl/normativa/", "type": "normativa"},
            {"key": "ntscys", "url": "https://www.coordinador.cl/normativa/ntscys/", "type": "normativa"},
            {"key": "instrucciones", "url": "https://www.coordinador.cl/normativa/instrucciones/", "type": "instruccion"},
            {"key": "ernc_cen", "url": "https://www.coordinador.cl/mercados/documentos/ernc/", "type": "info"},
            {"key": "bess_cen", "url": "https://www.coordinador.cl/mercados/documentos/almacenamiento/", "type": "info"},
        ],
        "bess_relevant": True,
    },
    # ── Biblioteca del Congreso Nacional ────────────────────────────────────
    {
        "source": "bcn",
        "label": "Biblioteca del Congreso Nacional",
        "base_url": "https://www.bcn.cl",
        "sections": [
            # Ley 20.936 — nueva transmisión
            {"key": "ley_20936", "url": "https://www.bcn.cl/leychile/navegar?idNorma=1091578", "type": "ley"},
            # Ley 21.185 — ERNC y almacenamiento
            {"key": "ley_21185", "url": "https://www.bcn.cl/leychile/navegar?idNorma=1148107", "type": "ley"},
            # Decreto 88 PMGD
            {"key": "decreto_88", "url": "https://www.bcn.cl/leychile/navegar?idNorma=1159484", "type": "decreto"},
            # Ley General de Electricidad
            {"key": "ley_general_elect", "url": "https://www.bcn.cl/leychile/navegar?idNorma=22657", "type": "ley"},
        ],
        "bess_relevant": True,
    },
    # ── Ministerio de Energía ────────────────────────────────────────────────
    {
        "source": "minenergia",
        "label": "Ministerio de Energía",
        "base_url": "https://energia.gob.cl",
        "sections": [
            {"key": "almacenamiento", "url": "https://energia.gob.cl/tema/almacenamiento", "type": "info"},
            {"key": "ernc_min", "url": "https://energia.gob.cl/tema/energias-renovables", "type": "info"},
            {"key": "normativa_min", "url": "https://energia.gob.cl/normativa", "type": "normativa"},
            {"key": "pelp", "url": "https://energia.gob.cl/planificacion/plan-electrico", "type": "info"},
        ],
        "bess_relevant": True,
    },
    # ── Comisión Nacional de Energía ─────────────────────────────────────────
    {
        "source": "cne",
        "label": "Comisión Nacional de Energía",
        "base_url": "https://www.cne.cl",
        "sections": [
            {"key": "normativa_cne", "url": "https://www.cne.cl/normativa/", "type": "normativa"},
            {"key": "tarifas_cne", "url": "https://www.cne.cl/tarifas/", "type": "info"},
            {"key": "pmg_cne", "url": "https://www.cne.cl/licitaciones/", "type": "info"},
        ],
        "bess_relevant": True,
    },
]


class MultiSourceScraper:
    """
    Raspa múltiples fuentes regulatorias en paralelo usando ThreadPoolExecutor.
    Combina los resultados de todas las fuentes en un único dataset unificado.
    """

    def __init__(self, max_workers: int = 4, delay: float = 1.0):
        self.max_workers = max_workers
        self.delay = delay
        self._session = self._build_session()

    def _build_session(self) -> requests.Session:
        s = requests.Session()
        s.headers.update({
            "User-Agent": SEC_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "es-CL,es;q=0.9",
        })
        return s

    def scrape_all_sources(
        self, sources: Optional[list[str]] = None
    ) -> list[dict]:
        """
        Raspa todas las fuentes en paralelo.
        sources: lista de keys de fuente a incluir, o None para todas.
        """
        active = EXTRA_SOURCES
        if sources:
            active = [s for s in EXTRA_SOURCES if s["source"] in sources]

        logger.info(f"🌐 Scrapeando {len(active)} fuentes adicionales en paralelo...")

        tasks = []
        for source_def in active:
            for section in source_def["sections"]:
                tasks.append((source_def, section))

        all_records: list[dict] = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._scrape_section, src, sec): (src, sec)
                for src, sec in tasks
            }
            for future in as_completed(futures):
                src, sec = futures[future]
                try:
                    records = future.result()
                    logger.info(
                        f"  ✓ [{src['source']}] {sec['key']}: "
                        f"{len(records)} docs "
                        f"({sum(1 for r in records if r.get('bess_relevant'))} BESS)"
                    )
                    all_records.extend(records)
                except Exception as exc:
                    logger.warning(f"  ✗ [{src['source']}] {sec['key']}: {exc}")

        logger.info(
            f"✅ Multi-source completo: {len(all_records)} docs totales "
            f"({sum(1 for r in all_records if r.get('bess_relevant'))} BESS relevantes)"
        )
        return all_records

    def _scrape_section(self, source_def: dict, section: dict) -> list[dict]:
        records: list[dict] = []
        url = section["url"]

        resp = self._get(url)
        if resp is None:
            return records

        soup = BeautifulSoup(resp.text, "html.parser")
        title = self._get_title(soup) or section["key"]
        body = html_to_clean_text(resp.text)
        pdf_links = extract_pdf_links(soup, url)
        date = extract_date(body)
        combined = body + " " + title

        # Registro principal de la sección
        records.append({
            "id": content_hash(url + title),
            "type": section["type"],
            "section": section["key"],
            "source": source_def["source"],
            "source_label": source_def["label"],
            "title": title,
            "url": url,
            "date": date,
            "body_text": body[:8000],
            "pdf_links": pdf_links,
            "bess_relevant": is_bess_relevant(combined),
            "relevance_score": bess_relevance_score(combined),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        })

        # Seguir sub-links relevantes dentro del mismo dominio
        links = self._extract_internal_links(soup, url, source_def["base_url"])
        for link in links[:15]:  # Máximo 15 sub-links por sección
            time.sleep(self.delay * 0.5)
            sub_resp = self._get(link["url"])
            if not sub_resp:
                continue
            sub_soup = BeautifulSoup(sub_resp.text, "html.parser")
            sub_title = self._get_title(sub_soup) or link["text"] or link["url"]
            sub_body = html_to_clean_text(sub_resp.text)
            sub_pdfs = extract_pdf_links(sub_soup, link["url"])
            sub_combined = sub_body + " " + sub_title

            if not is_bess_relevant(sub_combined):
                continue  # Solo guardar relevantes en sub-links

            records.append({
                "id": content_hash(link["url"] + sub_title),
                "type": section["type"],
                "section": section["key"],
                "source": source_def["source"],
                "source_label": source_def["label"],
                "title": sub_title,
                "url": link["url"],
                "date": extract_date(sub_body),
                "body_text": sub_body[:8000],
                "pdf_links": sub_pdfs,
                "bess_relevant": True,
                "relevance_score": bess_relevance_score(sub_combined),
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            })

        return records

    def _get(self, url: str) -> Optional[requests.Response]:
        for attempt in range(1, 4):
            try:
                time.sleep(self.delay)
                resp = self._session.get(url, timeout=SEC_REQUEST_TIMEOUT)
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp
            except requests.HTTPError as exc:
                if exc.response and exc.response.status_code in (404, 403):
                    return None
                time.sleep(self.delay * attempt)
            except Exception:
                time.sleep(self.delay * attempt)
        return None

    def _get_title(self, soup) -> Optional[str]:
        for tag in ("h1", "h2", "title"):
            el = soup.find(tag)
            if el:
                return el.get_text(strip=True)
        return None

    def _extract_internal_links(
        self, soup, base_url: str, domain_base: str
    ) -> list[dict]:
        from urllib.parse import urlparse
        base_domain = urlparse(domain_base).netloc
        links = []
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith(("javascript:", "mailto:", "#")):
                continue
            abs_url = urljoin(base_url, href)
            if urlparse(abs_url).netloc != base_domain:
                continue
            if abs_url in seen:
                continue
            seen.add(abs_url)
            text = a.get_text(strip=True)
            if text:
                links.append({"url": abs_url, "text": text})
        return links

    def save(self, records: list[dict]) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = RAW_DIR / f"multi_source_{ts}.json"
        payload = {
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "total_records": len(records),
            "bess_relevant_count": sum(1 for r in records if r.get("bess_relevant")),
            "sources": list({r.get("source", "unknown") for r in records}),
            "records": records,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"💾 Multi-source guardado: {path}")
        return str(path)
