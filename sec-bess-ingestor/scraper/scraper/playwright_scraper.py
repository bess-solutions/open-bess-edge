"""
scraper/playwright_scraper.py — Fallback scraper para páginas con JavaScript
──────────────────────────────────────────────────────────────────────────────
Usa Playwright para renderizar páginas que requieren JS (ej. buscadores SEC,
listados dinámicos, PDFs embebidos).

Instalación (solo si se necesita este módulo):
    python -m playwright install chromium --with-deps

NOTA: Este módulo es OPCIONAL. sec_scraper.py lo usa solo como fallback
cuando requests+BeautifulSoup retorna contenido vacío o insuficiente.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from config import SEC_REQUEST_DELAY, SEC_USER_AGENT

logger = logging.getLogger(__name__)

_playwright_available: Optional[bool] = None


def is_playwright_available() -> bool:
    """Verifica si playwright está instalado sin importarlo si no lo está."""
    global _playwright_available
    if _playwright_available is None:
        try:
            import playwright  # noqa: F401
            _playwright_available = True
        except ImportError:
            _playwright_available = False
            logger.info(
                "playwright no disponible. Usando solo requests como scraper. "
                "Para instalar: pip install playwright && python -m playwright install chromium"
            )
    return _playwright_available


def fetch_with_playwright(url: str, wait_for: str = "networkidle") -> Optional[str]:
    """
    Renderiza una página con Playwright (Chromium headless) y retorna el HTML
    final después de que el JS termina de ejecutar.

    Args:
        url: URL a renderizar
        wait_for: Evento de espera ("networkidle" | "load" | "domcontentloaded")

    Returns:
        HTML completo de la página, o None si falla.
    """
    if not is_playwright_available():
        return None

    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=SEC_USER_AGENT,
                locale="es-CL",
                timezone_id="America/Santiago",
            )
            page = context.new_page()

            # Bloquear recursos innecesarios para ir más rápido
            page.route(
                "**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,mp4,mp3}",
                lambda route: route.abort(),
            )

            logger.debug(f"Playwright GET: {url}")
            try:
                page.goto(url, wait_until=wait_for, timeout=30_000)
                time.sleep(SEC_REQUEST_DELAY)
                html = page.content()
                logger.debug(f"Playwright OK: {url} ({len(html)} chars)")
            except PWTimeout:
                logger.warning(f"Playwright timeout: {url}")
                html = page.content()  # Tomar lo que hay

            browser.close()
            return html

    except Exception as exc:
        logger.error(f"Playwright error en {url}: {exc}")
        return None


def scrape_sec_search(query: str) -> list[dict]:
    """
    Busca en el buscador de SEC Chile usando Playwright.
    Retorna lista de resultados {title, url, snippet}.
    """
    if not is_playwright_available():
        logger.warning("Playwright no disponible. No se puede usar el buscador SEC.")
        return []

    search_url = f"https://www.sec.cl/?s={query.replace(' ', '+')}"
    html = fetch_with_playwright(search_url, wait_for="load")
    if not html:
        return []

    from bs4 import BeautifulSoup
    from scraper.utils import extract_links, is_bess_relevant

    soup = BeautifulSoup(html, "html.parser")
    results = []

    # WordPress search results structure
    for article in soup.find_all(["article", "li", "div"], class_=lambda c: c and "result" in c.lower()):
        a = article.find("a", href=True)
        if not a:
            continue
        title = a.get_text(strip=True)
        url = a["href"]
        snippet = article.get_text(strip=True)[:300]
        if title and url:
            results.append({
                "title": title,
                "url": url,
                "snippet": snippet,
                "bess_relevant": is_bess_relevant(snippet + title),
            })

    logger.info(f"Playwright búsqueda '{query}': {len(results)} resultados")
    return results


def scrape_dynamic_listing(url: str) -> str:
    """
    Raspa un listado dinámico que requiere JS para renderizarse.
    Retorna el HTML completo post-render.
    """
    html = fetch_with_playwright(url, wait_for="networkidle")
    return html or ""
