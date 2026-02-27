"""
tests/test_gap_analyzer.py — Tests unitarios para analysis/gap_analyzer.py
"""

import json
import pytest
from pathlib import Path

from analysis.gap_analyzer import GapAnalyzer, GapItem, REGULATORY_RULES


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_sec_data():
    return json.loads((FIXTURES_DIR / "sample_sec_data.json").read_text(encoding="utf-8"))


@pytest.fixture
def analyzer():
    return GapAnalyzer()


class TestGapAnalyzer:
    def test_analyze_returns_gaps(self, analyzer, sample_sec_data):
        gaps = analyzer.analyze(sample_sec_data)
        assert isinstance(gaps, list)
        assert len(gaps) > 0

    def test_all_gaps_have_required_fields(self, analyzer, sample_sec_data):
        gaps = analyzer.analyze(sample_sec_data)
        for g in gaps:
            assert isinstance(g, GapItem)
            assert g.gap_id
            assert g.norm_ref
            assert g.description
            assert g.priority in ("critical", "medium", "low", "info")
            assert g.bess_implementation_status in (
                "implemented", "partial", "planned", "missing"
            )

    def test_gaps_sorted_by_priority(self, analyzer, sample_sec_data):
        gaps = analyzer.analyze(sample_sec_data)
        priority_order = {"critical": 0, "medium": 1, "low": 2, "info": 3}
        priorities = [priority_order[g.priority] for g in gaps]
        assert priorities == sorted(priorities)

    def test_known_critical_gaps_detected(self, analyzer, sample_sec_data):
        gaps = analyzer.analyze(sample_sec_data)
        gap_ids = {g.gap_id for g in gaps}
        # Brechas críticas conocidas deben siempre aparecer
        assert "GAP-001" in gap_ids  # Ramp rate
        assert "GAP-002" in gap_ids  # PFR droop
        assert "GAP-003" in gap_ids  # Telemetría CEN
        assert "GAP-004" in gap_ids  # IEC 60870-5-104

    def test_ntscys_triggers_detected(self, analyzer, sample_sec_data):
        """El fixture contiene 'rampa' y 'IEC 60870-5-104' → deben dispararse."""
        gaps = analyzer.analyze(sample_sec_data)
        gap_ids = {g.gap_id for g in gaps}
        # El fixture menciona rampa de potencia → GAP-001
        assert "GAP-001" in gap_ids
        # El fixture menciona IEC 60870-5-104 → GAP-004
        assert "GAP-004" in gap_ids

    def test_summary_stats(self, analyzer, sample_sec_data):
        gaps = analyzer.analyze(sample_sec_data)
        stats = analyzer.summary_stats(gaps)
        assert "total" in stats
        assert "by_priority" in stats
        assert "by_status" in stats
        assert stats["total"] == len(gaps)
        assert stats["by_priority"]["critical"] >= 0

    def test_no_duplicate_gap_ids(self, analyzer, sample_sec_data):
        gaps = analyzer.analyze(sample_sec_data)
        gap_ids = [g.gap_id for g in gaps]
        assert len(gap_ids) == len(set(gap_ids))

    def test_empty_sec_data_still_produces_known_gaps(self, analyzer):
        empty_data = {"records": [], "total_records": 0}
        gaps = analyzer.analyze(empty_data)
        # Incluso sin datos SEC, las brechas estructurales conocidas deben aparecer
        assert len(gaps) == len(REGULATORY_RULES)


class TestGapItem:
    def test_priority_label(self):
        gap = GapItem(
            gap_id="TEST-001", norm_ref="Ref", sec_document_title="Doc",
            sec_document_url="http://test.cl", description="desc",
            bess_current_state="none", bess_code_ref="N/A",
            bess_implementation_status="missing", priority="critical",
            technical_action="fix it", estimated_effort="1 day",
        )
        assert "Crítico" in gap.priority_label
        assert "🔴" in gap.priority_label

    def test_status_label(self):
        gap = GapItem(
            gap_id="TEST-002", norm_ref="Ref", sec_document_title="Doc",
            sec_document_url="http://test.cl", description="desc",
            bess_current_state="partial impl", bess_code_ref="src/",
            bess_implementation_status="partial", priority="medium",
            technical_action="complete it", estimated_effort="3 days",
        )
        assert "⚠️" in gap.status_label
        assert "Parcial" in gap.status_label
