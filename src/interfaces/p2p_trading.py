"""
src/interfaces/p2p_trading.py
==============================
BESSAI Edge Gateway — Peer-to-Peer Energy Trading (Hyperledger Fabric stub).

Implements energy credit minting and ledger publication for P2P electricity
markets. Each discharged kWh earns an EnergyCredit on the distributed ledger.

Architecture (production):
  - Hyperledger Fabric Orderer REST API (Fabric Gateway v2.x)
  - Chaincode: EnergyCredit token (ERC-1155 style on Fabric)
  - Private data collections (PDC) for commercial data privacy
  - Off-chain settlement via energy exchange (e.g., MISO, ERCOT, SING)

This module provides a full stub:
  - EnergyCredit dataclass (auditable, immutable-intent)
  - P2PEnergyTrader class: mint + publish lifecycle
  - Graceful offline mode: credits buffered when ledger unreachable
  - Prometheus metrics: credits minted, kWh traded

Usage::

    trader = P2PEnergyTrader(site_id="CL-001")
    credit = trader.mint_credit(discharged_kwh=10.5, co2_avoided_kg=3.5)
    result = trader.publish_to_ledger(credit)
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field

import structlog

from .metrics import ENERGY_CREDITS_KWH, ENERGY_CREDITS_MINTED_TOTAL

__all__ = ["P2PEnergyTrader", "EnergyCredit", "LedgerResult"]

log = structlog.get_logger(__name__)


@dataclass
class EnergyCredit:
    """Represents one auditable energy credit issued for BESS discharge.

    Attributes:
        credit_id:          Unique UUID for the credit.
        site_id:            Issuing BESSAI edge site.
        kwh:                Energy discharged (kWh).
        co2_avoided_kg:     CO₂ avoided by this discharge (kg).
        price_eur_kwh:      Optional spot price at time of dispatch (EUR/kWh).
        timestamp:          UTC Unix timestamp of the discharge event.
        hash:               SHA-256 of credit payload (integrity check).
        published:          Whether credit has been published to ledger.
    """
    credit_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    site_id: str = "unknown"
    kwh: float = 0.0
    co2_avoided_kg: float = 0.0
    price_eur_kwh: float = 0.0
    timestamp: float = field(default_factory=time.time)
    hash: str = field(init=False, default="")
    published: bool = False

    def __post_init__(self) -> None:
        self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute SHA-256 of stable credit fields (excluding hash itself)."""
        payload = json.dumps({
            "credit_id": self.credit_id,
            "site_id": self.site_id,
            "kwh": round(self.kwh, 6),
            "co2_avoided_kg": round(self.co2_avoided_kg, 6),
            "timestamp": self.timestamp,
        }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class LedgerResult:
    """Result of a ledger publication attempt."""
    success: bool
    credit_id: str
    tx_id: str | None = None         # Fabric transaction ID
    block_number: int | None = None  # Block height on the channel
    error: str | None = None
    latency_ms: float = 0.0


class P2PEnergyTrader:
    """P2P energy trading interface for BESSAI edge sites.

    Parameters:
        site_id:            Unique site identifier.
        ledger_endpoint:    Fabric Orderer REST endpoint (stub in dev mode).
        channel_name:       Fabric channel to invoke chaincode on.
        buffer_size:        Max credits buffered offline before dropping oldest.
        dry_run:            If True, never attempt real ledger connection.
    """

    def __init__(
        self,
        site_id: str = "edge-001",
        ledger_endpoint: str = "http://localhost:7050/api/v1/invoke",
        channel_name: str = "bessai-channel",
        buffer_size: int = 1_000,
        dry_run: bool = True,
    ) -> None:
        self.site_id = site_id
        self.ledger_endpoint = ledger_endpoint
        self.channel_name = channel_name
        self.dry_run = dry_run
        self._pending: deque[EnergyCredit] = deque(maxlen=buffer_size)
        self._published_count: int = 0
        self._total_kwh_published: float = 0.0

    # ------------------------------------------------------------------
    # Credit lifecycle
    # ------------------------------------------------------------------

    def mint_credit(
        self,
        discharged_kwh: float,
        co2_avoided_kg: float = 0.0,
        price_eur_kwh: float = 0.0,
    ) -> EnergyCredit:
        """Create an energy credit for a discharge event.

        Args:
            discharged_kwh:   Positive energy discharged to grid (kWh).
            co2_avoided_kg:   CO₂ kg avoided (from LCAEngine.update()).
            price_eur_kwh:    Spot market price at dispatch (EUR/kWh).

        Returns:
            EnergyCredit with a unique ID and integrity hash.
        """
        if discharged_kwh <= 0:
            raise ValueError(f"discharged_kwh must be > 0, got {discharged_kwh}")

        credit = EnergyCredit(
            site_id=self.site_id,
            kwh=round(discharged_kwh, 6),
            co2_avoided_kg=round(co2_avoided_kg, 6),
            price_eur_kwh=round(price_eur_kwh, 6),
        )

        # Update Prometheus
        ENERGY_CREDITS_MINTED_TOTAL.labels(site_id=self.site_id).inc()
        ENERGY_CREDITS_KWH.labels(site_id=self.site_id).inc(discharged_kwh)

        self._pending.append(credit)

        log.info(
            "p2p.credit_minted",
            credit_id=credit.credit_id[:8],
            kwh=round(discharged_kwh, 3),
            co2_kg=round(co2_avoided_kg, 3),
            pending_count=len(self._pending),
        )
        return credit

    def publish_to_ledger(self, credit: EnergyCredit) -> LedgerResult:
        """Publish a credit to the Hyperledger Fabric ledger.

        In dry_run mode (default), returns a mock success without network call.
        In production mode, invokes the Fabric Gateway REST endpoint.

        Args:
            credit: EnergyCredit to publish.

        Returns:
            LedgerResult with tx_id and block_number from the ledger.
        """
        t0 = time.perf_counter()

        if self.dry_run:
            result = LedgerResult(
                success=True,
                credit_id=credit.credit_id,
                tx_id=f"stub-tx-{credit.credit_id[:8]}",
                block_number=self._published_count + 1,
                latency_ms=(time.perf_counter() - t0) * 1000,
            )
        else:
            result = self._publish_remote(credit, t0)

        if result.success:
            credit.published = True
            self._published_count += 1
            self._total_kwh_published += credit.kwh
            # Remove from pending buffer
            try:
                self._pending.remove(credit)
            except ValueError:
                pass

        log.info(
            "p2p.credit_published",
            credit_id=credit.credit_id[:8],
            txid=result.tx_id,
            block=result.block_number,
            success=result.success,
            latency_ms=round(result.latency_ms, 2),
        )
        return result

    def flush_pending(self) -> list[LedgerResult]:
        """Attempt to publish all buffered (unpublished) credits.

        Returns:
            List of LedgerResult, one per buffered credit.
        """
        if not self._pending:
            return []
        credits = list(self._pending)  # snapshot
        results = [self.publish_to_ledger(c) for c in credits]
        log.info("p2p.flush", attempted=len(credits))
        return results

    def _publish_remote(self, credit: EnergyCredit, t0: float) -> LedgerResult:
        """Call Fabric Orderer REST endpoint (production path).

        This method is intentionally left as a clear stub: in production,
        replace the body with an httpx or aiohttp POST to the Fabric Gateway.
        """
        latency_ms = (time.perf_counter() - t0) * 1000
        log.warning(
            "p2p.remote_stub",
            msg="Remote ledger publish not yet implemented. "
                "Replace _publish_remote with Fabric Gateway call.",
            endpoint=self.ledger_endpoint,
        )
        return LedgerResult(
            success=False,
            credit_id=credit.credit_id,
            error="Remote publish stub — implement _publish_remote for production",
            latency_ms=latency_ms,
        )

    @property
    def published_count(self) -> int:
        return self._published_count

    @property
    def total_kwh_published(self) -> float:
        return self._total_kwh_published

    @property
    def pending_count(self) -> int:
        return len(self._pending)
