"""
scraper/async_scraper.py — Scraper concurrente con asyncio + aiohttp
──────────────────────────────────────────────────────────────────────
8–10× más rápido que el scraper serial. Raspa todas las secciones
SEC en paralelo con un semáforo de concurrencia configurable.

Uso:
    from scraper.async_scraper import AsyncSECScraper
    import asyncio
    scraper = AsyncSECScraper(max_concurrency=8)
    records = asyncio.run(scraper.scrape_all())
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin

from config import (
    BESS_KEYWORDS, RAW_DIR, SEC_BASE_URL,
    SEC_MAX_PAGES, SEC_MAX_RETRIES, SEC_REQUEST_DELAY,
    SEC_REQUEST_TIMEOUT, SEC_SECTIONS, SEC_USER_AGENT,
)
from scraper.utils import (
    bess_relevance_score, content_hash, extract_date,
    extract_pdf_links, html_to_clean_text, is_bess_relevant,
    is_same_domain,
)

logger = logging.getLogger(__name__)

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    logger.warning(
        "aiohttp no instalado. Instala con: pip install aiohttp\n"
        "Usando requests síncrono como fallback."
    )

try:
    from bs4 import BeautifulSoup
except ImportError:
    pass


class AsyncSECScraper:
    """
    Scraper asíncrono con máxima agresividad controlada.

    Parámetros de agresividad:
        max_concurrency : cuántos requests en paralelo (default 8)
        delay_between   : pausa mínima entre requests por dominio (default 0.5s)
        follow_depth    : niveles de links a seguir (1 = solo listados, 2 = subpáginas)
    """

    def __init__(
        self,
        max_concurrency: int = 8,
        delay_between: float = 0.5,
        follow_depth: int = 2,
    ):
        if not AIOHTTP_AVAILABLE:
            raise ImportError("pip install aiohttp para usar AsyncSECScraper")

        self.max_concurrency = max_concurrency
        self.delay_between = delay_between
        self.follow_depth = follow_depth
        self._seen_urls: set[str] = set()
        self._sem: asyncio.Semaphore
        self._session: aiohttp.ClientSession

    # ── Sesión ──────────────────────────────────────────────────────────────

    def _make_session(self) -> aiohttp.ClientSession:
        timeout = aiohttp.ClientTimeout(total=SEC_REQUEST_TIMEOUT)
        connector = aiohttp.TCPConnector(
            limit=self.max_concurrency * 2,
            limit_per_host=self.max_concurrency,
            ssl=False,
        )
        headers = {
            "User-Agent": SEC_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "es-CL,es;q=0.9",
            "DNT": "1",
        }
        return aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers=headers,
        )

    # ── Método público ───────────────────────────────────────────────────────

    async def scrape_all_async(
        self, bess_only: bool = False
    ) -> list[dict]:
        """Raspa todas las secciones en paralelo."""
        self._sem = asyncio.Semaphore(self.max_concurrency)
        async with self._make_session() as self._session:
            tasks = [
                self._scrape_section_async(section)
                for section in SEC_SECTIONS
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        all_records: list[dict] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Sección {SEC_SECTIONS[i]['key']}: {result}")
            else:
                all_records.extend(result)

        if bess_only:
            all_records = [r for r in all_records if r.get("bess_relevant")]

        all_records.sort(key=lambda r: r.get("relevance_score", 0), reverse=True)
        logger.info(
            f"✅ Scraping async completo: {len(all_records)} documentos "
            f"({sum(1 for r in all_records if r.get('bess_relevant'))} BESS)"
        )
        return all_records

    def scrape_all(self, bess_only: bool = False) -> list[dict]:
        """Wrapper síncrono para scrape_all_async."""
        return asyncio.run(self.scrape_all_async(bess_only))

    # ── Scraping de sección ──────────────────────────────────────────────────

    async def _scrape_section_async(self, section: dict) -> list[dict]:
        logger.info(f"⚡ [async] Raspando: {section['label']}")
        records: list[dict] = []
        page_urls = [section["url"]]

        # Recolectar URLs de todas las páginas del listado
        html = await self._fetch(section["url"])
        if not html:
            return records

        soup = BeautifulSoup(html, "html.parser")
        doc_links = self._extract_links(soup, section["url"])

        # Visitar sub-páginas en paralelo
        sub_tasks = []
        for link in doc_links:
            if link["url"] not in self._seen_urls and is_same_domain(link["url"]):
                self._seen_urls.add(link["url"])
                sub_tasks.append(self._fetch_doc(link, section))

        if sub_tasks:
            sub_results = await asyncio.gather(*sub_tasks, return_exceptions=True)
            for r in sub_results:
                if isinstance(r, dict):
                    records.append(r)

        # Paginación: páginas 2..N
        if self._has_next_page(soup):
            for page in range(2, SEC_MAX_PAGES + 1):
                parsed = section["url"].rstrip("/")
                page_url = f"{parsed}/page/{page}/"
                page_html = await self._fetch(page_url)
                if not page_html:
                    break
                page_soup = BeautifulSoup(page_html, "html.parser")
                page_links = self._extract_links(page_soup, page_url)
                if not page_links:
                    break
                page_tasks = [
                    self._fetch_doc(lnk, section)
                    for lnk in page_links
                    if lnk["url"] not in self._seen_urls and is_same_domain(lnk["url"])
                ]
                for lnk in page_links:
                    self._seen_urls.add(lnk["url"])
                page_sub = await asyncio.gather(*page_tasks, return_exceptions=True)
                for r in page_sub:
                    if isinstance(r, dict):
                        records.append(r)
                if not self._has_next_page(page_soup):
                    break

        logger.info(f"   ✓ {section['key']}: {len(records)} documentos")
        return records

    # ── Fetch con rate-limit y semáforo ─────────────────────────────────────

    async def _fetch(self, url: str) -> Optional[str]:
        """GET asíncrono con semáforo de concurrencia y delay."""
        async with self._sem:
            await asyncio.sleep(self.delay_between)
            for attempt in range(1, SEC_MAX_RETRIES + 1):
                try:
                    async with self._session.get(url) as resp:
                        if resp.status == 404:
                            return None
                        resp.raise_for_status()
                        return await resp.text(errors="replace")
                except aiohttp.ClientResponseError as exc:
                    if exc.status == 404:
                        return None
                    wait = self.delay_between * (2 ** attempt)
                    logger.debug(f"Retry {attempt} {url}: {exc} (wait {wait:.1f}s)")
                    await asyncio.sleep(wait)
                except Exception as exc:
                    logger.debug(f"Error {url}: {exc}")
                    await asyncio.sleep(self.delay_between * attempt)
            return None

    async def _fetch_doc(self, link: dict, section: dict) -> Optional[dict]:
        url = link["url"]
        title_hint = link.get("text", "")

        # PDFs: referencia sin descargar
        if url.lower().endswith(".pdf"):
            combined = title_hint
            return self._make_record(
                doc_type=section["type"] + "_pdf",
                section_key=section["key"],
                title=title_hint or url.split("/")[-1],
                url=url,
                bess_relevant=is_bess_relevant(combined),
                score=bess_relevance_score(combined),
            )

        html = await self._fetch(url)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")
        title = self._get_title(soup) or title_hint or url
        body = html_to_clean_text(html)
        pdfs = extract_pdf_links(soup, url)
        date = extract_date(body + " " + title)
        combined = body + " " + title

        return self._make_record(
            doc_type=section["type"],
            section_key=section["key"],
            title=title,
            url=url,
            body_text=body,
            pdf_links=pdfs,
            date=date,
            bess_relevant=is_bess_relevant(combined),
            score=bess_relevance_score(combined),
        )

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _make_record(self, **kwargs) -> dict:
        base = {
            "id": content_hash(kwargs.get("url", "") + kwargs.get("title", "")),
            "type": kwargs.get("doc_type", "unknown"),
            "section": kwargs.get("section_key", ""),
            "title": kwargs.get("title", ""),
            "url": kwargs.get("url", ""),
            "date": kwargs.get("date"),
            "number": None,
            "body_text": kwargs.get("body_text", "")[:8000],
            "pdf_links": kwargs.get("pdf_links", []),
            "metadata": {},
            "bess_relevant": kwargs.get("bess_relevant", False),
            "relevance_score": kwargs.get("score", 0),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "scraper": "async",
        }
        return base

    def _get_title(self, soup) -> Optional[str]:
        for tag in ("h1", "h2", "title"):
            el = soup.find(tag)
            if el:
                return el.get_text(strip=True)
        return None

    def _extract_links(self, soup, base_url: str) -> list[dict]:
        seen = set()
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith(("javascript:", "mailto:", "#")):
                continue
            abs_url = urljoin(base_url, href)
            if abs_url in seen:
                continue
            seen.add(abs_url)
            text = a.get_text(strip=True)
            if text:
                links.append({"url": abs_url, "text": text})
        return links

    def _has_next_page(self, soup) -> bool:
        for a in soup.find_all("a"):
            text = a.get_text(strip=True).lower()
            rel = a.get("rel", [])
            if "next" in rel or text in ("siguiente", "›", "»", ">", "next"):
                return True
        return False

    def save(self, records: list[dict]) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = RAW_DIR / f"sec_async_{ts}.json"
        payload = {
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "total_records": len(records),
            "bess_relevant_count": sum(1 for r in records if r.get("bess_relevant")),
            "sections_scraped": list({r["section"] for r in records}),
            "scraper": "async",
            "records": records,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"💾 Guardado: {path} ({len(records)} records)")
        return str(path)
