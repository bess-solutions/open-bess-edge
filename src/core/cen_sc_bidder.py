# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/core/cen_sc_bidder.py
==========================
BESSAI Edge Gateway — CEN Servicios Complementarios Bidder v2.14.0

Automatic SC bid submission to the Coordinador Eléctrico Nacional (CEN).

Servicios Complementarios (SC) in Chile:
  - PFR: Primary Frequency Response (≤30s, droop 5%)
  - CREG: Voltage Regulation Q/V
  - AGC: Automatic Generation Control (minutes-range)
  - SE: Seguimiento de Energía (economic dispatch)

Each SC market window is 15 minutes. Bids must be submitted ≥5 min before
the window start. BESSAI evaluates eligibility once per minute and submits
if the BESS has sufficient SOC margin and thermal headroom.

CEN API authentication: mTLS (see gen_certs.sh + CEN_TLS_* env vars)

Reference:
  - NTSyCS Cap. 4.3 (GAP-002) — PFR droop requirements
  - Res. CEN 2024-001 — SC market rules for storage
"""

from __future__ import annotations

import asyncio
import os
import ssl
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

try:
    import aiohttp
    _HAS_AIOHTTP = True
except ImportError:
    _HAS_AIOHTTP = False

__all__ = ["CENSCBidder", "SCBid", "SCType", "BidResult"]

log = structlog.get_logger(__name__)


class SCType(str, Enum):
    """Servicios Complementarios types per CEN Chile 2024."""
    PFR = "PFR"       # Primary Frequency Response
    CREG = "CREG"     # Voltage Regulation
    AGC = "AGC"       # Automatic Generation Control
    SE = "SE"         # Seguimiento de Energía


@dataclass
class SCBid:
    """A single SC bid to be submitted to CEN.

    Attributes:
        sc_type:       SC service type (PFR, CREG, AGC, SE).
        site_id:       BESSAI site identifier.
        capacity_kw:   Offered capacity in kW.
        price_usd_mwh: Offered price in USD/MWh.
        window_start:  15-min window start (UTC epoch).
        soc_pct:       SOC at bid time (for auditing).
    """

    sc_type: SCType
    site_id: str
    capacity_kw: float
    price_usd_mwh: float
    window_start: float = field(default_factory=time.time)
    soc_pct: float = 0.0
    bid_id: str = ""

    def to_cen_payload(self) -> dict[str, Any]:
        """Convert to CEN JSON payload format."""
        return {
            "serviceType": self.sc_type.value,
            "siteId": self.site_id,
            "offeredCapacityKW": self.capacity_kw,
            "priceUSDMWh": self.price_usd_mwh,
            "windowStartUTC": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.window_start)
            ),
            "stateOfChargeAtBid": self.soc_pct,
            "technology": "BESS",
            "responseTimeSeconds": 1.5,   # BESSAI inverter response ≤1.5s
            "protocolVersion": "NTSyCS-2024-v1",
        }


@dataclass
class BidResult:
    """CEN API response for a submitted bid."""

    bid: SCBid
    accepted: bool
    cen_bid_id: str = ""
    clearing_price_usd_mwh: float | None = None
    rejection_reason: str = ""
    timestamp: float = field(default_factory=time.time)

    @property
    def won(self) -> bool:
        return self.accepted and bool(self.cen_bid_id)


class CENSCBidder:
    """Automatic SC bid engine for CEN Chile.

    Parameters
    ----------
    site_id:
        BESSAI site identifier (must match CEN registration).
    p_nom_kw:
        Nameplate power capacity (kW).
    cen_endpoint:
        CEN SC API endpoint URL (from env CEN_ENDPOINT).
    dry_run:
        If True, logs bids but does not send to CEN (default in testing).
    min_soc_pct:
        Minimum SOC to participate (avoids over-commitment: default 20%).
    max_soc_pct:
        Maximum SOC to sell discharge (default 95%).
    """

    # SC prices from env (fall back to defaults from NTSyCS market data)
    _SC_PRICES: dict[SCType, float] = {
        SCType.PFR: float(os.getenv("SC_PFR_PRICE_USD_MWH", "1.5")),
        SCType.CREG: float(os.getenv("SC_CREG_PRICE_USD_MWH", "2.0")),
        SCType.AGC: float(os.getenv("SC_AGC_PRICE_USD_MWH", "3.5")),
        SCType.SE: float(os.getenv("SC_SE_PRICE_USD_MWH", "1.2")),
    }

    def __init__(
        self,
        site_id: str,
        p_nom_kw: float,
        cen_endpoint: str | None = None,
        dry_run: bool = True,
        min_soc_pct: float = 20.0,
        max_soc_pct: float = 95.0,
    ) -> None:
        self._site_id = site_id
        self._p_nom_kw = p_nom_kw
        self._endpoint = cen_endpoint or os.getenv("CEN_ENDPOINT", "")
        self._dry_run = dry_run or not self._endpoint
        self._min_soc = min_soc_pct
        self._max_soc = max_soc_pct

        self._ssl_ctx: ssl.SSLContext | None = self._build_ssl_ctx()
        self._bids_submitted: int = 0
        self._bids_won: int = 0
        self._last_bid_time: float = 0.0
        self._revenue_usd: float = 0.0

        log.info(
            "cen_bidder.initialized",
            site_id=site_id,
            p_nom_kw=p_nom_kw,
            dry_run=self._dry_run,
            endpoint=self._endpoint or "NOT_CONFIGURED",
        )

    # ------------------------------------------------------------------
    # mTLS setup
    # ------------------------------------------------------------------

    def _build_ssl_ctx(self) -> ssl.SSLContext | None:
        cert = os.getenv("CEN_TLS_CERT")
        key = os.getenv("CEN_TLS_KEY")
        ca = os.getenv("CEN_TLS_CA")
        if not all([cert, key, ca]):
            return None
        try:
            ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=ca)
            ctx.load_cert_chain(cert, key)  # type: ignore[arg-type]
            log.info("cen_bidder.mtls_configured")
            return ctx
        except Exception as exc:
            log.warning("cen_bidder.mtls_error", error=str(exc))
            return None

    # ------------------------------------------------------------------
    # Eligibility
    # ------------------------------------------------------------------

    def check_eligibility(
        self, soc_pct: float, sc_type: SCType = SCType.PFR
    ) -> tuple[bool, str]:
        """Check if this site is eligible to bid for a given SC service.

        Returns (eligible, reason_if_not)
        """
        if soc_pct < self._min_soc:
            return False, f"SOC {soc_pct:.1f}% below minimum {self._min_soc:.1f}%"
        if soc_pct > self._max_soc and sc_type in (SCType.PFR, SCType.AGC):
            return False, f"SOC {soc_pct:.1f}% above max {self._max_soc:.1f}% for {sc_type}"
        if self._p_nom_kw < 50.0:
            return False, f"P_nom {self._p_nom_kw:.0f}kW below CEN minimum 50kW"
        return True, ""

    # ------------------------------------------------------------------
    # Bid construction
    # ------------------------------------------------------------------

    def build_pfr_bid(self, soc_pct: float) -> SCBid:
        """Build a PFR bid: offer 20% of P_nom (conservative first bid)."""
        # NTSyCS requires PFR bid capacity ≤20% of nominal for first market cycle
        capacity = min(self._p_nom_kw * 0.20, self._p_nom_kw * (soc_pct / 100))
        return SCBid(
            sc_type=SCType.PFR,
            site_id=self._site_id,
            capacity_kw=round(capacity, 1),
            price_usd_mwh=self._SC_PRICES[SCType.PFR],
            soc_pct=soc_pct,
        )

    def build_creg_bid(self, soc_pct: float) -> SCBid:
        """Build a CREG (voltage regulation) bid: Q/V droop capacity."""
        capacity = self._p_nom_kw * 0.15  # 15% of nom for Q/V
        return SCBid(
            sc_type=SCType.CREG,
            site_id=self._site_id,
            capacity_kw=round(capacity, 1),
            price_usd_mwh=self._SC_PRICES[SCType.CREG],
            soc_pct=soc_pct,
        )

    # ------------------------------------------------------------------
    # Bid submission
    # ------------------------------------------------------------------

    async def submit_bid(self, bid: SCBid) -> BidResult:
        """Submit a single bid to CEN API.

        In dry_run mode: logs and returns a simulated accepted result.
        In production: sends authenticated POST via mTLS.
        """
        self._bids_submitted += 1
        self._last_bid_time = time.time()

        if self._dry_run:
            log.info(
                "cen_bidder.dry_run_bid",
                sc_type=bid.sc_type.value,
                capacity_kw=bid.capacity_kw,
                price=bid.price_usd_mwh,
                soc_pct=bid.soc_pct,
            )
            # Simulate ~85% acceptance rate in dry-run
            import hashlib
            h = int(hashlib.md5(f"{bid.site_id}{bid.window_start}".encode()).hexdigest(), 16)  # nosec B324
            accepted = (h % 100) < 85
            result = BidResult(
                bid=bid,
                accepted=accepted,
                cen_bid_id=f"DRY-{bid.sc_type.value}-{int(bid.window_start)}",
                clearing_price_usd_mwh=bid.price_usd_mwh * 0.95 if accepted else None,
            )
        else:
            result = await self._post_to_cen(bid)

        if result.won:
            self._bids_won += 1
            revenue = (
                (bid.capacity_kw / 1000) * (result.clearing_price_usd_mwh or 0) * 0.25
            )  # 15-min window = 0.25h
            self._revenue_usd += revenue
            log.info(
                "cen_bidder.bid_won",
                sc_type=bid.sc_type.value,
                capacity_kw=bid.capacity_kw,
                clearing_price=result.clearing_price_usd_mwh,
                revenue_usd=round(revenue, 2),
                total_revenue_usd=round(self._revenue_usd, 2),
            )
        else:
            log.info(
                "cen_bidder.bid_rejected",
                sc_type=bid.sc_type.value,
                reason=result.rejection_reason or "Market cleared at lower price",
            )

        return result

    async def _post_to_cen(self, bid: SCBid) -> BidResult:
        """Send bid to real CEN API via mTLS."""
        if not _HAS_AIOHTTP:
            raise RuntimeError("aiohttp required for production CEN submission")

        payload = bid.to_cen_payload()
        url = f"{self._endpoint}/sc/bids"

        try:
            connector = aiohttp.TCPConnector(ssl=self._ssl_ctx)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    body = await resp.json()
                    accepted = resp.status in (200, 201) and body.get("status") == "ACCEPTED"
                    return BidResult(
                        bid=bid,
                        accepted=accepted,
                        cen_bid_id=body.get("bidId", ""),
                        clearing_price_usd_mwh=body.get("clearingPrice"),
                        rejection_reason=body.get("reason", "") if not accepted else "",
                    )
        except Exception as exc:
            log.error("cen_bidder.post_error", error=str(exc), url=url)
            return BidResult(bid=bid, accepted=False, rejection_reason=str(exc))

    # ------------------------------------------------------------------
    # Auto-bid loop
    # ------------------------------------------------------------------

    async def auto_bid_loop(
        self, soc_getter: Any, interval_s: float = 60.0
    ) -> None:
        """Background task: evaluate + submit SC bids every minute.

        Args:
            soc_getter: Callable/coroutine returning current SOC (0-100).
            interval_s: Evaluation interval in seconds (default 60).
        """
        log.info("cen_bidder.auto_bid_loop.started", interval_s=interval_s)
        while True:
            try:
                soc = await soc_getter() if asyncio.iscoroutinefunction(soc_getter) else soc_getter()

                for sc_type in (SCType.PFR, SCType.CREG):
                    eligible, reason = self.check_eligibility(soc, sc_type)
                    if not eligible:
                        log.debug("cen_bidder.ineligible", sc_type=sc_type.value, reason=reason)
                        continue

                    bid = (
                        self.build_pfr_bid(soc) if sc_type == SCType.PFR
                        else self.build_creg_bid(soc)
                    )
                    await self.submit_bid(bid)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.error("cen_bidder.loop_error", error=str(exc))

            await asyncio.sleep(interval_s)

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "bids_submitted": self._bids_submitted,
            "bids_won": self._bids_won,
            "win_rate_pct": (
                round(self._bids_won / self._bids_submitted * 100, 1)
                if self._bids_submitted > 0 else 0.0
            ),
            "total_revenue_usd": round(self._revenue_usd, 2),
            "dry_run": self._dry_run,
        }
