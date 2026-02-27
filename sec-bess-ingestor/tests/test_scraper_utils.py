"""
tests/test_scraper_utils.py — Tests unitarios para scraper/utils.py
"""

import pytest
from scraper.utils import (
    bess_relevance_score,
    content_hash,
    extract_date,
    html_to_clean_text,
    is_bess_relevant,
    is_same_domain,
)


class TestBessRelevance:
    def test_relevant_bess_text(self):
        text = "Norma para sistemas de almacenamiento BESS conectados al SEN"
        assert is_bess_relevant(text) is True

    def test_relevant_ernc_text(self):
        text = "Reglamento PMGD para generación distribuida renovable"
        assert is_bess_relevant(text) is True

    def test_irrelevant_text(self):
        text = "Reglamento de distribución de gas licuado de petróleo"
        assert is_bess_relevant(text) is False

    def test_relevance_score(self):
        text = "BESS almacenamiento batería fotovoltaico solar renovable PMGD"
        score = bess_relevance_score(text)
        assert score >= 5

    def test_relevance_score_zero(self):
        text = "Instalación de medidor eléctrico domiciliario"
        score = bess_relevance_score(text)
        assert score == 0


class TestExtractDate:
    def test_iso_date(self):
        assert extract_date("Fecha: 2024-06-15") == "2024-06-15"

    def test_chilean_date_format(self):
        result = extract_date("Emitido el 20/03/2024")
        assert result == "2024-03-20"

    def test_spanish_date_format(self):
        result = extract_date("15 de enero de 2024")
        assert result == "2024-01-15"

    def test_no_date(self):
        assert extract_date("Sin fecha en este texto") is None


class TestHtmlToCleanText:
    def test_removes_scripts(self):
        html = "<html><script>alert('bad')</script><p>Contenido útil</p></html>"
        text = html_to_clean_text(html)
        assert "alert" not in text
        assert "Contenido útil" in text

    def test_removes_nav(self):
        html = "<nav>Menu</nav><article>Contenido principal</article>"
        text = html_to_clean_text(html)
        assert "Contenido principal" in text

    def test_clean_whitespace(self):
        html = "<p>Texto   con    muchos    espacios</p>"
        text = html_to_clean_text(html)
        assert "   " not in text


class TestDomainCheck:
    def test_same_domain(self):
        assert is_same_domain("https://www.sec.cl/normativa/") is True

    def test_different_domain(self):
        assert is_same_domain("https://www.google.com") is False


class TestContentHash:
    def test_deterministic(self):
        text = "Mismo texto siempre mismo hash"
        assert content_hash(text) == content_hash(text)

    def test_different_texts(self):
        assert content_hash("texto A") != content_hash("texto B")

    def test_length(self):
        assert len(content_hash("test")) == 16
