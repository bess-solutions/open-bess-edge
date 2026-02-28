#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
tests/test_cen_sc_bidder.py
Tests for the CEN SC auto-bidder — BEP-0200 Phase 3.
"""

from __future__ import annotations

import asyncio

import pytest

from src.core.cen_sc_bidder import (
    CENSCBidder,
    SCBid,
    SCType,
    BidResult,
)


@pytest.fixture
def bidder() -> CENSCBidder:
    return CENSCBidder(
        site_id="SITE-CL-TEST",
        p_nom_kw=1000.0,
        dry_run=True,
    )


# ---------------------------------------------------------------------------
# Eligibility tests
# ---------------------------------------------------------------------------

class TestEligibility:
    def test_normal_soc_eligible(self, bidder: CENSCBidder) -> None:
        ok, reason = bidder.check_eligibility(60.0, SCType.PFR)
        assert ok
        assert reason == ""

    def test_low_soc_ineligible(self, bidder: CENSCBidder) -> None:
        ok, reason = bidder.check_eligibility(15.0, SCType.PFR)
        assert not ok
        assert "SOC" in reason

    def test_high_soc_ineligible_for_pfr(self, bidder: CENSCBidder) -> None:
        ok, reason = bidder.check_eligibility(98.0, SCType.PFR)
        assert not ok

    def test_small_bess_ineligible(self) -> None:
        small = CENSCBidder(site_id="TEST", p_nom_kw=30.0, dry_run=True)
        ok, reason = small.check_eligibility(60.0, SCType.PFR)
        assert not ok
        assert "50kW" in reason

    def test_high_soc_ok_for_creg(self, bidder: CENSCBidder) -> None:
        # CREG (voltage regulation) doesn't have max SOC restriction
        ok, _ = bidder.check_eligibility(98.0, SCType.CREG)
        assert ok


# ---------------------------------------------------------------------------
# Bid construction tests
# ---------------------------------------------------------------------------

class TestBidConstruction:
    def test_pfr_bid_capacity_reasonable(self, bidder: CENSCBidder) -> None:
        bid = bidder.build_pfr_bid(soc_pct=70.0)
        assert isinstance(bid, SCBid)
        assert bid.sc_type == SCType.PFR
        assert 0 < bid.capacity_kw <= 1000.0 * 0.20
        assert bid.price_usd_mwh > 0

    def test_creg_bid_capacity_15pct(self, bidder: CENSCBidder) -> None:
        bid = bidder.build_creg_bid(soc_pct=60.0)
        assert bid.sc_type == SCType.CREG
        assert bid.capacity_kw == pytest.approx(1000.0 * 0.15, rel=0.01)

    def test_bid_payload_has_required_fields(self, bidder: CENSCBidder) -> None:
        bid = bidder.build_pfr_bid(70.0)
        payload = bid.to_cen_payload()
        for key in ("serviceType", "siteId", "offeredCapacityKW", "priceUSDMWh",
                    "windowStartUTC", "technology", "responseTimeSeconds"):
            assert key in payload
        assert payload["technology"] == "BESS"
        assert payload["responseTimeSeconds"] <= 2.0  # NTSyCS requirement


# ---------------------------------------------------------------------------
# Submission tests (dry-run)
# ---------------------------------------------------------------------------

class TestBidSubmission:
    def test_dry_run_submission_returns_result(self, bidder: CENSCBidder) -> None:
        bid = bidder.build_pfr_bid(60.0)
        result = asyncio.get_event_loop().run_until_complete(bidder.submit_bid(bid))
        assert isinstance(result, BidResult)
        assert result.bid is bid

    def test_stats_update_on_submission(self, bidder: CENSCBidder) -> None:
        bid = bidder.build_pfr_bid(60.0)
        asyncio.get_event_loop().run_until_complete(bidder.submit_bid(bid))
        assert bidder.stats["bids_submitted"] == 1

    def test_revenue_accrues_on_won_bid(self, bidder: CENSCBidder) -> None:
        """Force a win by submitting many bids — statistically some will win."""
        wins = 0
        for i in range(20):
            bid = SCBid(
                sc_type=SCType.PFR,
                site_id="SITE-CL-TEST",
                capacity_kw=200.0,
                price_usd_mwh=1.5,
                window_start=float(1_700_000_000 + i * 900),
                soc_pct=60.0,
            )
            result = asyncio.get_event_loop().run_until_complete(bidder.submit_bid(bid))
            if result.won:
                wins += 1
        # With 85% dry-run acceptance rate, should win at least a few
        assert wins > 5
        assert bidder.stats["total_revenue_usd"] > 0.0
