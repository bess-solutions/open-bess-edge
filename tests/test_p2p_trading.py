"""
tests/test_p2p_trading.py
==========================
Unit tests for P2PEnergyTrader and EnergyCredit.
"""

from __future__ import annotations

import json

import pytest
from src.interfaces.p2p_trading import EnergyCredit, LedgerResult, P2PEnergyTrader


class TestEnergyCredit:

    def test_credit_has_unique_id(self):
        c1 = EnergyCredit(site_id="A", kwh=5.0)
        c2 = EnergyCredit(site_id="A", kwh=5.0)
        assert c1.credit_id != c2.credit_id

    def test_hash_is_hex_string(self):
        credit = EnergyCredit(site_id="CL-001", kwh=10.0)
        assert len(credit.hash) == 64  # SHA-256 = 64 hex chars
        assert all(c in "0123456789abcdef" for c in credit.hash)

    def test_to_dict_contains_required_keys(self):
        credit = EnergyCredit(site_id="CL-001", kwh=10.0)
        d = credit.to_dict()
        for key in ("credit_id", "site_id", "kwh", "hash", "timestamp"):
            assert key in d

    def test_to_json_parseable(self):
        credit = EnergyCredit(site_id="CL-001", kwh=10.0)
        data = json.loads(credit.to_json())
        assert data["kwh"] == pytest.approx(10.0)

    def test_published_defaults_false(self):
        c = EnergyCredit(kwh=1.0)
        assert c.published is False


class TestP2PEnergyTrader:

    def _trader(self, site_id: str = "test-site") -> P2PEnergyTrader:
        return P2PEnergyTrader(site_id=site_id, dry_run=True)

    def test_mint_creates_credit(self):
        trader = self._trader()
        credit = trader.mint_credit(discharged_kwh=10.0, co2_avoided_kg=3.5)
        assert isinstance(credit, EnergyCredit)
        assert credit.kwh == pytest.approx(10.0)
        assert credit.co2_avoided_kg == pytest.approx(3.5)

    def test_mint_zero_kwh_raises(self):
        trader = self._trader()
        with pytest.raises(ValueError):
            trader.mint_credit(discharged_kwh=0.0)

    def test_mint_negative_kwh_raises(self):
        trader = self._trader()
        with pytest.raises(ValueError):
            trader.mint_credit(discharged_kwh=-5.0)

    def test_publish_dry_run_succeeds(self):
        trader = self._trader()
        credit = trader.mint_credit(discharged_kwh=5.0)
        result = trader.publish_to_ledger(credit)
        assert isinstance(result, LedgerResult)
        assert result.success is True
        assert result.tx_id is not None

    def test_publish_marks_credit_published(self):
        trader = self._trader()
        credit = trader.mint_credit(discharged_kwh=5.0)
        trader.publish_to_ledger(credit)
        assert credit.published is True

    def test_published_count_increments(self):
        trader = self._trader()
        for _ in range(3):
            c = trader.mint_credit(discharged_kwh=1.0)
            trader.publish_to_ledger(c)
        assert trader.published_count == 3

    def test_total_kwh_published_accumulates(self):
        trader = self._trader()
        for kwh in [5.0, 10.0, 7.5]:
            c = trader.mint_credit(discharged_kwh=kwh)
            trader.publish_to_ledger(c)
        assert trader.total_kwh_published == pytest.approx(22.5)

    def test_flush_pending_publishes_all(self):
        trader = self._trader()
        for _ in range(3):
            trader.mint_credit(discharged_kwh=2.0)
        assert trader.pending_count == 3
        results = trader.flush_pending()
        assert len(results) == 3
        assert trader.pending_count == 0
