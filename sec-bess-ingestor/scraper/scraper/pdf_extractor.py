"""
scraper/pdf_extractor.py — Extrae texto de documentos PDF normativos SEC
──────────────────────────────────────────────────────────────────────────
Descarga y procesa los PDFs referenciados en los documentos scrapeados.
Usa pypdf (puro Python, sin dependencias externas) con fallback a pdfminer.

Instalación:
    pip install pypdf          # recomendado
    pip install pdfminer.six   # fallback / más robusto para PDFs complejos

Uso:
    extractor = PDFExtractor()
    text = extractor.extract_url("https://www.sec.cl/normativa/doc.pdf")
    batch = extractor.extract_batch(records)  # procesa lista de DocumentRecords
"""

from __future__ import annotations

import io
import logging
import hashlib
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

import requests

from config import (
    RAW_DIR, SEC_REQUEST_TIMEOUT, SEC_USER_AGENT,
    BESS_KEYWORDS,
)
from scraper.utils import bess_relevance_score, is_bess_relevant

logger = logging.getLogger(__name__)

# ─── Disponibilidad de backends ─────────────────────────────────────────────

def _try_pypdf():
    try:
        import pypdf
        return pypdf
    except ImportError:
        return None

def _try_pdfminer():
    try:
        from pdfminer.high_level import extract_text_to_fp
        from pdfminer.layout import LAParams
        return (extract_text_to_fp, LAParams)
    except ImportError:
        return None

PDF_CACHE_DIR = RAW_DIR / "pdf_cache"
PDF_CACHE_DIR.mkdir(parents=True, exist_ok=True)


class PDFExtractor:
    """
    Descarga y extrae texto de PDFs normativos de la SEC.
    Cachea los PDFs localmente para no re-descargar.
    """

    def __init__(self, cache: bool = True, max_pages: int = 50):
        self.cache = cache
        self.max_pages = max_pages
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": SEC_USER_AGENT})
        self._pypdf = _try_pypdf()
        self._pdfminer = _try_pdfminer()

        if self._pypdf:
            logger.info("PDFExtractor: usando pypdf")
        elif self._pdfminer:
            logger.info("PDFExtractor: usando pdfminer.six")
        else:
            logger.warning(
                "PDFExtractor: ningún backend PDF disponible. "
                "Instala: pip install pypdf"
            )

    def is_available(self) -> bool:
        return self._pypdf is not None or self._pdfminer is not None

    # ── Extracción por URL ───────────────────────────────────────────────────

    def extract_url(self, url: str) -> Optional[str]:
        """
        Descarga el PDF de la URL y extrae su texto completo.
        Retorna el texto extraído o None si falla.
        """
        if not self.is_available():
            return None

        # Cache check
        cache_key = hashlib.md5(url.encode()).hexdigest()
        cache_file = PDF_CACHE_DIR / f"{cache_key}.txt"
        if self.cache and cache_file.exists():
            logger.debug(f"Cache hit: {url}")
            return cache_file.read_text(encoding="utf-8", errors="replace")

        # Download
        pdf_bytes = self._download(url)
        if not pdf_bytes:
            return None

        # Extract
        text = self._extract_bytes(pdf_bytes)
        if text is None:
            return None

        # Truncate if very large
        if len(text) > 200_000:
            text = text[:200_000] + "\n\n[... documento truncado ...]"

        # Cache result
        if self.cache:
            cache_file.write_text(text, encoding="utf-8", errors="replace")

        logger.info(f"PDF extraído: {url} ({len(text):,} chars)")
        return text

    # ── Extracción en batch sobre records ────────────────────────────────────

    def extract_batch(self, records: list[dict]) -> list[dict]:
        """
        Para cada record que tenga pdf_links, extrae el texto del primer PDF
        y lo agrega a record['pdf_text'] y actualiza 'body_text' si estaba vacío.
        Retorna la lista de records enriquecida.
        """
        enriched = 0
        for record in records:
            pdf_links = record.get("pdf_links", [])
            if not pdf_links:
                continue

            # Intentar con el primer PDF de la lista
            primary_pdf = pdf_links[0]["url"]
            logger.debug(f"Extrayendo PDF: {primary_pdf}")
            text = self.extract_url(primary_pdf)
            if text:
                record["pdf_text"] = text[:50_000]
                # Si el body_text estaba vacío, usar el PDF
                if not record.get("body_text"):
                    record["body_text"] = text[:8_000]
                # Recalcular relevancia con el texto del PDF
                combined = record.get("body_text", "") + " " + text[:5_000]
                record["bess_relevant"] = is_bess_relevant(combined)
                record["relevance_score"] = bess_relevance_score(combined)
                enriched += 1

        logger.info(f"PDFs extraídos: {enriched}/{len(records)} records enriquecidos")
        return records

    def extract_bess_relevant_only(self, records: list[dict]) -> list[dict]:
        """
        Solo extrae PDFs de records marcados como BESS relevantes.
        Más eficiente para grandes volúmenes.
        """
        bess_records = [r for r in records if r.get("bess_relevant")]
        logger.info(f"Extrayendo PDFs de {len(bess_records)} records BESS relevantes...")
        self.extract_batch(bess_records)
        return records

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _download(self, url: str) -> Optional[bytes]:
        """Descarga el PDF y retorna bytes."""
        try:
            resp = self._session.get(
                url, timeout=SEC_REQUEST_TIMEOUT, stream=True
            )
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            if "pdf" not in content_type.lower() and not url.lower().endswith(".pdf"):
                logger.debug(f"No es PDF ({content_type}): {url}")
                return None
            data = resp.content
            if len(data) < 100:
                return None
            return data
        except Exception as exc:
            logger.warning(f"No se pudo descargar PDF {url}: {exc}")
            return None

    def _extract_bytes(self, pdf_bytes: bytes) -> Optional[str]:
        """Extrae texto de bytes PDF usando el backend disponible."""
        if self._pypdf:
            return self._extract_pypdf(pdf_bytes)
        elif self._pdfminer:
            return self._extract_pdfminer(pdf_bytes)
        return None

    def _extract_pypdf(self, pdf_bytes: bytes) -> Optional[str]:
        try:
            reader = self._pypdf.PdfReader(io.BytesIO(pdf_bytes))
            texts = []
            for i, page in enumerate(reader.pages):
                if i >= self.max_pages:
                    texts.append(f"\n[... {len(reader.pages) - i} páginas adicionales omitidas ...]")
                    break
                try:
                    texts.append(page.extract_text() or "")
                except Exception:
                    texts.append("")
            return "\n\n".join(t for t in texts if t.strip())
        except Exception as exc:
            logger.debug(f"pypdf error: {exc}")
            return None

    def _extract_pdfminer(self, pdf_bytes: bytes) -> Optional[str]:
        extract_fn, LAParams = self._pdfminer
        try:
            output = io.StringIO()
            extract_fn(
                io.BytesIO(pdf_bytes),
                output,
                laparams=LAParams(),
            )
            return output.getvalue()
        except Exception as exc:
            logger.debug(f"pdfminer error: {exc}")
            return None


# ─── Extractor de texto de normativas específicas ───────────────────────────

PRIORITY_PDF_URLS = [
    # NTSyCS — norma técnica más importante para BESS
    "https://www.coordinador.cl/wp-content/uploads/2022/06/NTSyCS-2022.pdf",
    # Decreto 88 PMGD
    "https://www.bcn.cl/leychile/navegar?idNorma=1159484&idParte=&idVersion=",
    # Ley 21.185
    "https://www.bcn.cl/leychile/navegar?idNorma=1148107",
]


def extract_priority_normativas() -> dict[str, str]:
    """
    Extrae texto de los documentos normativos más importantes
    independientemente del scraping general.
    """
    extractor = PDFExtractor()
    results: dict[str, str] = {}
    for url in PRIORITY_PDF_URLS:
        text = extractor.extract_url(url)
        if text:
            results[url] = text
            logger.info(f"✅ Normativa extraída: {url[:60]}…")
    return results
