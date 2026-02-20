"""
src/interfaces/datalake_publisher.py
=====================================
BESSAI Edge Gateway — BigQuery DataLake Publisher.

Publishes BESS telemetry to a BigQuery table via streaming inserts.
Acts as the edge-to-cloud data pipeline for the BESSAI Data Lakehouse.

Schema (bessai_telemetry table):
  site_id:          STRING (required)
  timestamp:        TIMESTAMP (required, UTC)
  soc_pct:          FLOAT64
  power_kw:         FLOAT64
  temp_c:           FLOAT64
  anomaly_score:    FLOAT64 (AI-IDS score 0-1)
  co2_avoided_kg:   FLOAT64 (cumulative, from LCAEngine)
  dispatch_kw:      FLOAT64 (ONNX dispatcher output)
  event_type:       STRING  ('nominal', 'alarm', 'vpp_event')

Fallback strategy:
  - Primary: BigQuery streaming insert (prod)
  - Secondary: Local JSONL file buffer (edge offline mode)
  - Tertiary: Skip with log warning (buffer full)

Usage::

    async with DataLakePublisher(project_id="my-project") as publisher:
        await publisher.publish(row)
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path

import structlog

from .metrics import DATALAKE_ROWS_PUBLISHED_TOTAL

__all__ = ["DataLakePublisher", "TelemetryRow"]

log = structlog.get_logger(__name__)

try:
    from google.cloud import bigquery  # type: ignore[import-untyped]
    _BQ_AVAILABLE = True
except ImportError:
    _BQ_AVAILABLE = False


@dataclass
class TelemetryRow:
    """One telemetry row to be published to the DataLake.

    All float fields default to 0.0 (not None) to avoid type errors.
    """
    site_id: str
    timestamp: float = field(default_factory=time.time)
    soc_pct: float = 0.0
    power_kw: float = 0.0
    temp_c: float = 25.0
    anomaly_score: float = 0.0
    co2_avoided_kg: float = 0.0
    dispatch_kw: float = 0.0
    event_type: str = "nominal"

    def to_bq_row(self) -> dict:
        """Convert to BigQuery-compatible row dict."""
        import datetime
        d = asdict(self)
        # Convert Unix timestamp → ISO 8601 string for BQ TIMESTAMP
        d["timestamp"] = datetime.datetime.fromtimestamp(
            self.timestamp, tz=datetime.timezone.utc
        ).isoformat().replace("+00:00", "Z")
        return d

    def to_jsonl(self) -> str:
        """Serialize for JSONL local buffer."""
        return json.dumps(asdict(self))


class DataLakePublisher:
    """Async BigQuery telemetry publisher with local fallback buffering.

    Parameters:
        project_id:     GCP project ID.
        dataset:        BigQuery dataset name.
        table:          BigQuery table name.
        buffer_size:    Max rows buffered offline.
        batch_size:     Rows per BigQuery streaming insert batch.
        local_buffer_path: Path for the local JSONL fallback file.
    """

    def __init__(
        self,
        project_id: str = "",
        dataset: str = "bessai_telemetry",
        table: str = "edge_readings",
        buffer_size: int = 10_000,
        batch_size: int = 100,
        local_buffer_path: str = "/tmp/bessai_datalake_buffer.jsonl",
    ) -> None:
        self.project_id = project_id
        self.dataset = dataset
        self.table = table
        self.batch_size = batch_size
        self._buffer: deque[TelemetryRow] = deque(maxlen=buffer_size)
        self._local_path = Path(local_buffer_path)
        self._client: object | None = None   # bigquery.Client when available
        self._published_total: int = 0

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> DataLakePublisher:
        if _BQ_AVAILABLE and self.project_id:
            try:
                self._client = bigquery.Client(project=self.project_id)
                log.info("datalake.bq_connected", project=self.project_id)
            except Exception as exc:
                log.warning("datalake.bq_init_failed", error=str(exc))
        else:
            log.info(
                "datalake.local_mode",
                reason="bigquery not installed or project_id empty",
                buffer_path=str(self._local_path),
            )
        return self

    async def __aexit__(self, *_) -> None:
        # Flush remaining buffer
        if self._buffer:
            await self._flush()
        if self._client is not None and hasattr(self._client, "close"):
            self._client.close()  # type: ignore[union-attr]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def publish(self, row: TelemetryRow) -> bool:
        """Queue a row for publishing.

        Triggers a batch flush when buffer reaches batch_size.

        Args:
            row: TelemetryRow to publish.

        Returns:
            True if row was accepted into buffer.
        """
        self._buffer.append(row)
        if len(self._buffer) >= self.batch_size:
            await self._flush()
        return True

    async def publish_many(self, rows: list[TelemetryRow]) -> int:
        """Publish a list of rows, returns count successfully buffered."""
        for row in rows:
            self._buffer.append(row)
        if len(self._buffer) >= self.batch_size:
            await self._flush()
        return len(rows)

    # ------------------------------------------------------------------
    # Internal flush logic
    # ------------------------------------------------------------------

    async def _flush(self) -> None:
        """Flush buffered rows to BigQuery or local fallback."""
        if not self._buffer:
            return

        batch = [self._buffer.popleft() for _ in range(min(self.batch_size, len(self._buffer)))]

        if self._client is not None:
            await self._flush_to_bq(batch)
        else:
            await self._flush_to_local(batch)

    async def _flush_to_bq(self, batch: list[TelemetryRow]) -> None:
        """Stream insert batch to BigQuery."""
        table_ref = f"{self.project_id}.{self.dataset}.{self.table}"
        rows = [r.to_bq_row() for r in batch]
        try:
            # Run blocking BQ call in thread pool
            errors = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._client.insert_rows_json(table_ref, rows),  # type: ignore
            )
            if errors:
                log.error("datalake.bq_insert_errors", errors=errors[:3])
                # Fall back to local
                await self._flush_to_local(batch)
            else:
                n = len(batch)
                self._published_total += n
                DATALAKE_ROWS_PUBLISHED_TOTAL.labels(
                    site_id=batch[0].site_id if batch else "unknown"
                ).inc(n)
                log.debug("datalake.bq_flushed", n=n)
        except Exception as exc:
            log.error("datalake.bq_flush_error", error=str(exc))
            await self._flush_to_local(batch)

    async def _flush_to_local(self, batch: list[TelemetryRow]) -> None:
        """Write batch to local JSONL file (offline fallback)."""
        try:
            with self._local_path.open("a", encoding="utf-8") as f:
                for row in batch:
                    f.write(row.to_jsonl() + "\n")
            n = len(batch)
            self._published_total += n
            DATALAKE_ROWS_PUBLISHED_TOTAL.labels(
                site_id=batch[0].site_id if batch else "unknown"
            ).inc(n)
            log.debug("datalake.local_flushed", n=n, path=str(self._local_path))
        except Exception as exc:
            log.error("datalake.local_flush_error", error=str(exc))

    @property
    def published_total(self) -> int:
        return self._published_total

    @property
    def buffer_size(self) -> int:
        return len(self._buffer)
