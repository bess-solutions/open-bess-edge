"""
scraper/utils.py — Utilidades de scraping respetuoso para sec.cl
──────────────────────────────────────────────────────────────────
• Rate-limiting configurable
• Manejo de robots.txt
• Limpieza HTML→texto legible
• Logging estructurado
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from typing import Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup, Tag

from config import (
    BESS_KEYWORDS, SEC_BASE_URL, SEC_MAX_RETRIES,
    SEC_REQUEST_DELAY, SEC_REQUEST_TIMEOUT, SEC_USER_AGENT,
)

logger = logging.getLogger(__name__)

# ─── robots.txt ──────────────────────────────────────────────────────────────

_rp: Optional[RobotFileParser] = None


def get_robots_parser() -> RobotFileParser:
    global _rp
    if _rp is None:
        _rp = RobotFileParser()
        _rp.set_url(f"{SEC_BASE_URL}/robots.txt")
        try:
            _rp.read()
            logger.debug("robots.txt leído correctamente")
        except Exception as exc:
            logger.warning(f"No se pudo leer robots.txt: {exc}")
    return _rp


def can_fetch(url: str) -> bool:
    """Verifica si robots.txt permite la URL."""
    try:
        return get_robots_parser().can_fetch(SEC_USER_AGENT, url)
    except Exception:
        return True  # Si hay error, asumir permitido


# ─── Sesión HTTP ─────────────────────────────────────────────────────────────

def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": SEC_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    })
    return session


_last_request_time: float = 0.0


def rate_limited_get(
    session: requests.Session,
    url: str,
    delay: float = SEC_REQUEST_DELAY,
    timeout: int = SEC_REQUEST_TIMEOUT,
) -> Optional[requests.Response]:
    """GET con rate-limiting y reintentos exponenciales."""
    global _last_request_time

    if not can_fetch(url):
        logger.warning(f"robots.txt bloquea: {url}")
        return None

    elapsed = time.time() - _last_request_time
    if elapsed < delay:
        time.sleep(delay - elapsed)

    for attempt in range(1, SEC_MAX_RETRIES + 1):
        try:
            logger.debug(f"GET {url} (intento {attempt})")
            resp = session.get(url, timeout=timeout)
            resp.raise_for_status()
            _last_request_time = time.time()
            return resp
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                logger.info(f"404 – {url}")
                return None
            logger.warning(f"HTTP {exc} – intento {attempt}/{SEC_MAX_RETRIES}")
        except requests.RequestException as exc:
            logger.warning(f"Error de red: {exc} – intento {attempt}/{SEC_MAX_RETRIES}")
        if attempt < SEC_MAX_RETRIES:
            time.sleep(delay * (2 ** attempt))  # backoff exponencial

    logger.error(f"Falló tras {SEC_MAX_RETRIES} intentos: {url}")
    return None


# ─── Limpieza de HTML ────────────────────────────────────────────────────────

_NOISE_TAGS = {
    "script", "style", "nav", "header", "footer",
    "aside", "form", "button", "input", "select",
    "iframe", "noscript", "svg", "path",
}

_WHITESPACE_RE = re.compile(r"\s{3,}")
_BLANK_LINES_RE = re.compile(r"\n{4,}")


def html_to_clean_text(html: str) -> str:
    """Convierte HTML crudo a texto plano limpio."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(_NOISE_TAGS):
        tag.decompose()
    text = soup.get_text(separator="\n")
    text = _WHITESPACE_RE.sub("  ", text)
    text = _BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()


def extract_meta(soup: BeautifulSoup) -> dict:
    """Extrae metadatos de Open Graph y meta básicos."""
    meta = {}
    for m in soup.find_all("meta"):
        prop = m.get("property") or m.get("name", "")
        content = m.get("content", "")
        if prop and content:
            meta[prop] = content
    return meta


def extract_links(soup: BeautifulSoup, base_url: str) -> list[dict]:
    """Extrae todos los enlaces <a> de una página, resueltos a URL absoluta."""
    links = []
    for a in soup.find_all("a", href=True):
        href: str = a["href"].strip()
        if href.startswith("javascript:") or href == "#":
            continue
        absolute = urljoin(base_url, href)
        text = a.get_text(strip=True)
        links.append({"url": absolute, "text": text})
    return links


def extract_pdf_links(soup: BeautifulSoup, base_url: str) -> list[dict]:
    """Extrae enlaces a PDFs."""
    return [
        lnk for lnk in extract_links(soup, base_url)
        if lnk["url"].lower().endswith(".pdf")
    ]


def is_same_domain(url: str, base: str = SEC_BASE_URL) -> bool:
    return urlparse(url).netloc == urlparse(base).netloc


# ─── Relevancia BESS ─────────────────────────────────────────────────────────

def is_bess_relevant(text: str) -> bool:
    """Retorna True si el texto contiene al menos una keyword BESS relevante."""
    lower = text.lower()
    return any(kw in lower for kw in BESS_KEYWORDS)


def bess_relevance_score(text: str) -> int:
    """Cuenta cuántas keywords BESS aparecen (como puntaje de relevancia)."""
    lower = text.lower()
    return sum(1 for kw in BESS_KEYWORDS if kw in lower)


# ─── Hashing para deduplicación ──────────────────────────────────────────────

def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ─── Extracción de fecha ──────────────────────────────────────────────────────

_DATE_PATTERNS = [
    # DD/MM/YYYY
    re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b"),
    # YYYY-MM-DD
    re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"),
    # "12 de enero de 2024"
    re.compile(
        r"\b(\d{1,2})\s+de\s+"
        r"(enero|febrero|marzo|abril|mayo|junio|"
        r"julio|agosto|septiembre|octubre|noviembre|diciembre)"
        r"\s+de\s+(\d{4})\b",
        re.IGNORECASE,
    ),
]

_MONTH_MAP = {
    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
    "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
    "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12",
}


def extract_date(text: str) -> Optional[str]:
    """Extrae la primera fecha encontrada en el texto (formato ISO 8601)."""
    for pattern in _DATE_PATTERNS:
        m = pattern.search(text)
        if m:
            groups = m.groups()
            if len(groups) == 3 and not any(g.isalpha() for g in groups):
                # DD/MM/YYYY o YYYY-MM-DD
                if len(groups[0]) == 4:
                    return f"{groups[0]}-{groups[1].zfill(2)}-{groups[2].zfill(2)}"
                return f"{groups[2]}-{groups[1].zfill(2)}-{groups[0].zfill(2)}"
            elif len(groups) == 3:
                day, month_str, year = groups
                month = _MONTH_MAP.get(month_str.lower(), "00")
                return f"{year}-{month}-{day.zfill(2)}"
    return None
