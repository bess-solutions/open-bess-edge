# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/core/sen_market_feed.py
============================
BESSAI Edge Gateway — SEN Market Feed Bridge (BEP-0500 Phase 2).

Connects the SENAdapter (real CEN DuckDB + HTTP) to VPPFleetManager
via the ``market_price_fn`` callback interface.

This module provides the missing link between:
  - MarketAdapterRegistry (7 global markets, Sprint C)
  - VPPFleetManager.set_market_price_fn() (BEP-0500, Sprint E/F)

Usage::

    from src.core.sen_market_feed import SENMarketFeed
    from src.core.vpp_fleet_manager import VPPFleetManager

    feed = SENMarketFeed(node="Lo_Aguirre")
    mgr = VPPFleetManager()
    mgr.set_market_price_fn(feed)         # feed is callable
    mgr.add_site("CL-001", proxy)
    result = mgr.run_cycle()              # price comes from SEN DuckDB
    print(result.market_price_usd_mwh)   # real CEN price
"""

from __future__ import annotations

import datetime

import structlog

log = structlog.get_logger(__name__)

__all__ = ["SENMarketFeed"]

# Default SEN conversion factor: 1 CLP/MWh → USD at ~0.001085 (approx)
_CLP_TO_USD = 0.001085


class SENMarketFeed:
    """Callable adapter that fetches the current SEN spot price for ``run_cycle()``.

    This is the canonical way to wire a live market price to VPPFleetManager:

    .. code-block:: python

        feed = SENMarketFeed(node="Maitencillo")
        mgr.set_market_price_fn(feed)
        result = mgr.run_cycle()  # price resolved from SEN

    Parameters:
        node:           CEN market node (default: "Lo_Aguirre").
        use_duckdb:     If True, read from local DuckDB first; fallback to HTTP.
        clp_to_usd:     Conversion factor (CLP/MWh → USD/MWh).
        db_path:        Optional DuckDB database path override.
    """

    def __init__(
        self,
        node: str = "Lo_Aguirre",
        use_duckdb: bool = True,
        clp_to_usd: float = _CLP_TO_USD,
        db_path: str | None = None,
    ) -> None:
        self.node = node
        self.use_duckdb = use_duckdb
        self.clp_to_usd = clp_to_usd
        self._db_path = db_path
        self._last_price_usd: float | None = None
        self._last_fetched: datetime.datetime | None = None
        self._cache_ttl_minutes: int = 15  # refresh at most every 15 min

    def __call__(self) -> float:
        """Return current SEN spot price in USD/MWh for the configured node.

        Caches the result for ``_cache_ttl_minutes`` to avoid hammering the DB
        on every dispatch cycle.

        Returns:
            Spot price in USD/MWh. Falls back to a physics-based Duck Curve
            estimate if neither DuckDB nor HTTP are available.
        """
        now = datetime.datetime.now()
        if (
            self._last_price_usd is not None
            and self._last_fetched is not None
            and (now - self._last_fetched).total_seconds() / 60 < self._cache_ttl_minutes
        ):
            return self._last_price_usd

        price_usd = self._fetch()
        self._last_price_usd = price_usd
        self._last_fetched = now
        log.info(
            "sen_feed.price_fetched",
            node=self.node,
            price_usd_mwh=round(price_usd, 2),
            source="duckdb" if self.use_duckdb else "http",
        )
        return price_usd

    def _fetch(self) -> float:
        """Attempt DuckDB fetch, fallback to SENAdapter HTTP, then duck-curve."""
        if self.use_duckdb:
            try:
                price = self._fetch_duckdb()
                if price is not None:
                    return price * self.clp_to_usd
            except Exception as exc:  # noqa: BLE001
                log.warning("sen_feed.duckdb_error", error=str(exc))

        # Fallback: SENAdapter (may itself fallback to duck-curve)
        return self._fetch_adapter()

    def _fetch_duckdb(self) -> float | None:
        """Read latest CMg from bessai-cen-data DuckDB.

        Returns price in CLP/MWh or None if unavailable.
        """
        try:
            import duckdb  # noqa: PLC0415
        except ImportError:
            log.debug("sen_feed.duckdb_not_installed")
            return None

        db_path = self._db_path or self._default_db_path()
        try:
            con = duckdb.connect(str(db_path), read_only=True)
            # Query latest hour for this node
            row = con.execute(
                """
                SELECT cmg_clp_mwh
                FROM   cmg_prices
                WHERE  node = ?
                ORDER  BY timestamp DESC
                LIMIT  1
                """,
                [self.node],
            ).fetchone()
            con.close()
            if row:
                return float(row[0])
        except Exception as exc:  # noqa: BLE001
            log.warning("sen_feed.duckdb_query_error", error=str(exc), db=str(db_path))
        return None

    def _fetch_adapter(self) -> float:
        """Use SENAdapter (HTTP + fallback) to get current price."""
        try:
            from src.core.market_adapter import SENAdapter  # noqa: PLC0415

            adapter = SENAdapter()
            today = datetime.date.today().isoformat()
            prices = adapter.get_spot_prices(date=today)
            current_hour = datetime.datetime.now().hour
            for p in prices:
                if p.hour == current_hour:
                    return p.price_usd_mwh
            if prices:
                return sum(p.price_usd_mwh for p in prices) / len(prices)
        except Exception as exc:  # noqa: BLE001
            log.warning("sen_feed.adapter_error", error=str(exc))

        # Ultimate fallback: duck curve at current hour
        return self._duck_curve_usd()

    def _duck_curve_usd(self) -> float:
        """Physics-based Duck Curve price estimate (USD/MWh) for current hour."""
        import math  # noqa: PLC0415

        h = datetime.datetime.now().hour
        # Peaks at 19:00 (evening demand) and 09:00 (industrial) — simplified
        peak = 80.0 + 20.0 * math.sin(math.pi * (h - 7) / 12)
        valley = 40.0 - 10.0 * math.exp(-((h - 13) ** 2) / 10.0)
        return round(max(30.0, peak if h >= 17 or h <= 8 else valley), 2)

    def _default_db_path(self) -> str:
        """Resolve default DuckDB path relative to the repository structure."""
        import pathlib  # noqa: PLC0415

        # Look for bessai-cen-data relative to this file
        base = pathlib.Path(__file__).parent.parent.parent.parent
        return str(base / "bessai-cen-data" / "db" / "cmg_prices.duckdb")

    @property
    def last_price(self) -> float | None:
        """Last fetched price in USD/MWh (None if never called)."""
        return self._last_price_usd

    def __repr__(self) -> str:
        return f"SENMarketFeed(node={self.node!r}, last_price={self._last_price_usd})"
