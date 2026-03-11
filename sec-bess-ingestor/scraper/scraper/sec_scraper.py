"""
scraper/sec_scraper.py — Motor principal de scraping para sec.cl
─────────────────────────────────────────────────────────────────
Extrae resoluciones, circulares, normativas, reglamentos y noticias
de la Superintendencia de Electricidad y Combustibles (SEC Chile).
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from config import (
    RAW_DIR,
    SEC_MAX_PAGES,
    SEC_REQUEST_DELAY,
    SEC_SECTIONS,
)

from scraper.utils import (
    bess_relevance_score,
    build_session,
    content_hash,
    extract_date,
    extract_links,
    extract_meta,
    extract_pdf_links,
    html_to_clean_text,
    is_bess_relevant,
    is_same_domain,
    rate_limited_get,
)

logger = logging.getLogger(__name__)

# ─── Tipos ─────────────────────────────────────────────────────────────────

DocumentRecord = dict  # Estructura de un documento extraído


def make_record(
    *,
    doc_type: str,
    section_key: str,
    title: str,
    url: str,
    date: str | None = None,
    number: str | None = None,
    body_text: str = "",
    pdf_links: list[dict] | None = None,
    metadata: dict | None = None,
    bess_relevant: bool = False,
    relevance_score: int = 0,
) -> DocumentRecord:
    return {
        "id": content_hash(url + title),
        "type": doc_type,
        "section": section_key,
        "title": title,
        "url": url,
        "date": date,
        "number": number,
        "body_text": body_text[:8_000],  # Limitar tamaño
        "pdf_links": pdf_links or [],
        "metadata": metadata or {},
        "bess_relevant": bess_relevant,
        "relevance_score": relevance_score,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


# ─── Scrapers por sección ──────────────────────────────────────────────────

class SECScraper:
    """
    Motor principal de scraping para sec.cl.

    Uso:
        scraper = SECScraper()
        records = scraper.scrape_all()
        scraper.save(records)
    """

    def __init__(self):
        self.session = build_session()
        self._seen_urls: set[str] = set()

    # ── Método público principal ────────────────────────────────────────────

    def scrape_all(self, bess_only: bool = False) -> list[DocumentRecord]:
        """
        Raspa todas las secciones configuradas en SEC_SECTIONS.
        Si bess_only=True, filtra solo documentos relevantes a BESS/ERNC.
        """
        all_records: list[DocumentRecord] = []
        for section in SEC_SECTIONS:
            logger.info(f"🔍 Raspando sección: {section['label']}")
            try:
                records = self._scrape_section(section)
                logger.info(
                    f"   ✅ {len(records)} documentos extraídos "
                    f"({sum(1 for r in records if r['bess_relevant'])} BESS relevantes)"
                )
                all_records.extend(records)
            except Exception as exc:
                logger.error(f"   ❌ Error en {section['key']}: {exc}", exc_info=True)

        if bess_only:
            all_records = [r for r in all_records if r["bess_relevant"]]
            logger.info(f"Filtrado BESS: {len(all_records)} documentos")

        return all_records

    def scrape_section(self, section_key: str) -> list[DocumentRecord]:
        """Raspa solo una sección por su key."""
        section = next((s for s in SEC_SECTIONS if s["key"] == section_key), None)
        if section is None:
            raise ValueError(f"Sección no encontrada: {section_key!r}")
        return self._scrape_section(section)

    # ── Dispatcher interno ──────────────────────────────────────────────────

    def _scrape_section(self, section: dict) -> list[DocumentRecord]:
        """Despacha a estrategia específica según tipo de sección."""
        scraper_map = {
            "normativa": self._scrape_list_section,
            "resolucion": self._scrape_list_section,
            "circular": self._scrape_list_section,
            "reglamento": self._scrape_list_section,
            "info": self._scrape_info_page,
            "noticia": self._scrape_news_section,
            "fiscalizacion": self._scrape_list_section,
            "sancion": self._scrape_list_section,
        }
        strategy = scraper_map.get(section["type"], self._scrape_info_page)
        return strategy(section)

    # ── Estrategia: páginas de listado con paginación ───────────────────────

    def _scrape_list_section(self, section: dict) -> list[DocumentRecord]:
        """Raspa secciones con listados de documentos + paginación."""
        records: list[DocumentRecord] = []
        page = 1

        while page <= SEC_MAX_PAGES:
            url = self._paginate_url(section["url"], page)
            resp = rate_limited_get(self.session, url)
            if resp is None:
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            doc_links = self._extract_document_links(soup, section)

            if not doc_links:
                logger.debug(f"No más enlaces en {url} (página {page})")
                break

            for link in doc_links:
                if link["url"] in self._seen_urls:
                    continue
                self._seen_urls.add(link["url"])
                record = self._fetch_document(link, section)
                if record:
                    records.append(record)

            # Verificar si hay siguiente página
            if not self._has_next_page(soup):
                break
            page += 1

        return records

    def _paginate_url(self, base_url: str, page: int) -> str:
        """Genera URL paginada. SEC usa ?page=N o /page/N."""
        if page == 1:
            return base_url
        # Intentar formato WordPress: /page/N/
        parsed = urlparse(base_url)
        path = parsed.path.rstrip("/")
        return base_url.replace(parsed.path, f"{path}/page/{page}/")

    def _has_next_page(self, soup: BeautifulSoup) -> bool:
        """Detecta enlace 'siguiente' en paginación."""
        for tag in soup.find_all(["a", "link"]):
            text = tag.get_text(strip=True).lower()
            rel = tag.get("rel", [])
            if "next" in rel or text in ("siguiente", "›", "»", "next", ">"):
                return True
        return False

    def _extract_document_links(
        self, soup: BeautifulSoup, section: dict
    ) -> list[dict]:
        """
        Extrae enlaces a documentos individuales de una página de listado.
        Prioriza PDFs y páginas internas de SEC.
        """
        candidates = []
        base_url = section["url"]

        for a in soup.find_all("a", href=True):
            href: str = a["href"].strip()
            if href.startswith("javascript:") or href == "#":
                continue
            absolute = urljoin(base_url, href)
            if not is_same_domain(absolute):
                continue
            text = a.get_text(strip=True)
            if not text:
                continue
            candidates.append({"url": absolute, "text": text})

        # Deduplicar por URL
        seen = set()
        unique = []
        for c in candidates:
            if c["url"] not in seen:
                seen.add(c["url"])
                unique.append(c)

        return unique

    # ── Estrategia: página informativa simple ───────────────────────────────

    def _scrape_info_page(self, section: dict) -> list[DocumentRecord]:
        """Raspa una página informativa completa como un solo documento."""
        records = []
        resp = rate_limited_get(self.session, section["url"])
        if resp is None:
            return records

        soup = BeautifulSoup(resp.text, "html.parser")
        title = self._extract_title(soup) or section["label"]
        body_text = html_to_clean_text(resp.text)
        pdf_links = extract_pdf_links(soup, section["url"])
        date_str = extract_date(body_text)
        relevance = bess_relevance_score(body_text + " " + title)

        record = make_record(
            doc_type=section["type"],
            section_key=section["key"],
            title=title,
            url=section["url"],
            date=date_str,
            body_text=body_text,
            pdf_links=pdf_links,
            metadata=extract_meta(soup),
            bess_relevant=is_bess_relevant(body_text + " " + title),
            relevance_score=relevance,
        )
        records.append(record)

        # También extraer y visitar sub-enlaces internos relevantes
        links = extract_links(soup, section["url"])
        for link in links[:20]:
            if not is_same_domain(link["url"]) or link["url"] in self._seen_urls:
                continue
            if not self._is_content_url(link["url"]):
                continue
            self._seen_urls.add(link["url"])
            sub_record = self._fetch_document(link, section)
            if sub_record:
                records.append(sub_record)

        return records

    # ── Estrategia: noticias ───────────────────────────────────────────────

    def _scrape_news_section(self, section: dict) -> list[DocumentRecord]:
        """Raspa sección de noticias buscando artículos relevantes a BESS."""
        all_records = self._scrape_list_section(section)
        # Filtrar solo las relevantes a BESS (para no saturar)
        return [r for r in all_records if r["bess_relevant"]]

    # ── Fetch de documento individual ──────────────────────────────────────

    def _fetch_document(
        self, link: dict, section: dict
    ) -> DocumentRecord | None:
        """Visita un enlace individual y extrae su contenido."""
        url = link["url"]
        title_hint = link.get("text", "")

        # PDFs: solo registrar referencia, sin descargar
        if url.lower().endswith(".pdf"):
            combined = title_hint
            return make_record(
                doc_type=section["type"] + "_pdf",
                section_key=section["key"],
                title=title_hint or url.split("/")[-1],
                url=url,
                bess_relevant=is_bess_relevant(combined),
                relevance_score=bess_relevance_score(combined),
            )

        resp = rate_limited_get(self.session, url, delay=SEC_REQUEST_DELAY)
        if resp is None:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        title = self._extract_title(soup) or title_hint or url
        body_text = self._extract_main_content(soup)
        pdf_links = extract_pdf_links(soup, url)
        date_str = extract_date(body_text + " " + title)
        number = self._extract_document_number(title + " " + body_text)
        combined = body_text + " " + title

        return make_record(
            doc_type=section["type"],
            section_key=section["key"],
            title=title,
            url=url,
            date=date_str,
            number=number,
            body_text=body_text,
            pdf_links=pdf_links,
            metadata=extract_meta(soup),
            bess_relevant=is_bess_relevant(combined),
            relevance_score=bess_relevance_score(combined),
        )

    # ── Helpers ────────────────────────────────────────────────────────────

    def _extract_title(self, soup: BeautifulSoup) -> str | None:
        for tag in ("h1", "h2", "title"):
            el = soup.find(tag)
            if el:
                return el.get_text(strip=True)
        return None

    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """Extrae el contenido principal (article > main > div.entry-content)."""
        for selector in (
            "article",
            "main",
            '[class*="entry-content"]',
            '[class*="content"]',
            '[class*="post-body"]',
            "section",
        ):
            el = soup.select_one(selector)
            if el:
                return html_to_clean_text(str(el))
        return html_to_clean_text(soup.get_text())

    _NUMBER_RE = re.compile(
        r"\b(?:N[°º.]?\s*)?(\d{2,6})\b"
        r"(?:\s*/\s*(\d{4}))?"
    )

    def _extract_document_number(self, text: str) -> str | None:
        m = self._NUMBER_RE.search(text[:500])
        if m:
            num = m.group(1)
            year = m.group(2)
            return f"{num}/{year}" if year else num
        return None

    def _is_content_url(self, url: str) -> bool:
        """Filtra URLs que probablemente tengan contenido real."""
        excluded = ("/wp-admin/", "/wp-login.", "/feed/", ".xml", ".rss",
                    ".css", ".js", ".png", ".jpg", ".gif", ".ico")
        return not any(ex in url.lower() for ex in excluded)

    # ── Persistencia ───────────────────────────────────────────────────────

    def save(self, records: list[DocumentRecord], suffix: str = "") -> str:
        """Guarda los records en JSON y retorna la ruta del archivo."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"sec_{ts}{('_' + suffix) if suffix else ''}.json"
        output_path = RAW_DIR / filename

        payload = {
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "total_records": len(records),
            "bess_relevant_count": sum(1 for r in records if r["bess_relevant"]),
            "sections_scraped": list({r["section"] for r in records}),
            "records": records,
        }

        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(f"💾 Guardado: {output_path} ({len(records)} registros)")
        return str(output_path)

    @staticmethod
    def load_latest() -> dict | None:
        """Carga el archivo JSON más reciente de data/raw/."""
        files = sorted(RAW_DIR.glob("sec_*.json"), reverse=True)
        if not files:
            return None
        data = json.loads(files[0].read_text(encoding="utf-8"))
        logger.info(f"📂 Cargado: {files[0].name} ({data['total_records']} registros)")
        return data

    @staticmethod
    def load_file(path: str) -> dict:
        """Carga un archivo JSON específico."""
        import pathlib
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
