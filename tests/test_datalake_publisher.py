"""
tests/test_datalake_publisher.py
==================================
Unit tests for DataLakePublisher and TelemetryRow.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from src.interfaces.datalake_publisher import DataLakePublisher, TelemetryRow


def _row(soc: float = 70.0, site_id: str = "test-001") -> TelemetryRow:
    return TelemetryRow(site_id=site_id, soc_pct=soc, power_kw=10.0, temp_c=28.0)


class TestTelemetryRow:
    def test_to_bq_row_has_iso_timestamp(self):
        row = _row()
        bq = row.to_bq_row()
        assert bq["timestamp"].endswith("Z")
        assert "T" in bq["timestamp"]

    def test_to_jsonl_parseable(self):
        row = _row(soc=80.0)
        data = json.loads(row.to_jsonl())
        assert data["soc_pct"] == pytest.approx(80.0)

    def test_event_type_default_nominal(self):
        row = _row()
        assert row.event_type == "nominal"

    def test_custom_event_type(self):
        row = TelemetryRow(site_id="X", event_type="alarm")
        assert row.event_type == "alarm"

    def test_to_bq_row_contains_all_fields(self):
        row = _row()
        bq = row.to_bq_row()
        for field in [
            "site_id",
            "soc_pct",
            "power_kw",
            "temp_c",
            "anomaly_score",
            "co2_avoided_kg",
            "dispatch_kw",
            "event_type",
        ]:
            assert field in bq


class TestDataLakePublisher:
    def test_publish_buffers_row(self):
        with tempfile.TemporaryDirectory() as d:
            pub = DataLakePublisher(
                project_id="",
                batch_size=3,
                local_buffer_path=d + "/test_buffer.jsonl",
            )

            async def go():
                async with pub:
                    await pub.publish(_row())
                    # batch of 3 not reached yet; 1 row should be in buffer
                    assert pub.buffer_size == 1

            asyncio.run(go())

    def test_batch_flush_writes_to_local_file(self):
        with tempfile.TemporaryDirectory() as d:
            pub = DataLakePublisher(
                project_id="",
                batch_size=3,
                local_buffer_path=d + "/test_buffer.jsonl",
            )

            async def go():
                async with pub:
                    for _ in range(3):
                        await pub.publish(_row())
                return pub.published_total

            total = asyncio.run(go())
            assert total >= 3

    def test_local_file_contains_valid_jsonl(self):
        with tempfile.TemporaryDirectory() as d:
            path = d + "/buf.jsonl"
            pub = DataLakePublisher(project_id="", batch_size=2, local_buffer_path=path)

            async def go():
                async with pub:
                    await pub.publish_many([_row(soc=50.0), _row(soc=60.0)])

            asyncio.run(go())
            lines = Path(path).read_text().strip().splitlines()
            assert len(lines) >= 2
            for line in lines:
                data = json.loads(line)
                assert "site_id" in data

    def test_publish_many_returns_count(self):
        with tempfile.TemporaryDirectory() as d:
            pub = DataLakePublisher(
                project_id="", batch_size=10, local_buffer_path=d + "/buf2.jsonl"
            )

            async def go():
                async with pub:
                    n = await pub.publish_many([_row(), _row()])
                    return n

            n = asyncio.run(go())
            assert n == 2

    def test_aexit_flushes_remaining(self):
        with tempfile.TemporaryDirectory() as d:
            path = d + "/flush_test.jsonl"
            pub = DataLakePublisher(project_id="", batch_size=10, local_buffer_path=path)

            async def go():
                async with pub:
                    # Only 2 rows — below batch_size=10, but flushed on __aexit__
                    await pub.publish(_row())
                    await pub.publish(_row())

            asyncio.run(go())
            # File should exist and contain 2 rows
            content = Path(path).read_text().strip()
            lines = content.splitlines()
            assert len(lines) == 2

    def test_published_total_zero_initially(self):
        pub = DataLakePublisher()
        assert pub.published_total == 0

    def test_buffer_size_zero_initially(self):
        pub = DataLakePublisher()
        assert pub.buffer_size == 0


# ── BQ mode tests (mocked bigquery) ────────────────────────────────────────


class TestBigQueryMode:
    """Tests that exercise the BigQuery code path (lines 51, 127-131, 193-214)."""

    def test_aenter_bq_connected(self):
        """Lines 127-130: if _BQ_AVAILABLE + project_id → client created."""
        mock_bq_client = MagicMock()
        mock_bq = MagicMock()
        mock_bq.Client.return_value = mock_bq_client

        with tempfile.TemporaryDirectory() as d:
            pub = DataLakePublisher(
                project_id="my-project",
                local_buffer_path=d + "/buf.jsonl",
            )

            async def go():
                with (
                    patch("src.interfaces.datalake_publisher._BQ_AVAILABLE", True),
                    patch("src.interfaces.datalake_publisher.bigquery", mock_bq, create=True),
                ):
                    async with pub as p:
                        return p._client

            client = asyncio.run(go())
            assert client is mock_bq_client

    def test_aenter_bq_init_exception_falls_back_to_local(self):
        """Line 131: if Client() raises → client stays None."""
        mock_bq = MagicMock()
        mock_bq.Client.side_effect = Exception("auth error")

        with tempfile.TemporaryDirectory() as d:
            pub = DataLakePublisher(
                project_id="bad-project",
                local_buffer_path=d + "/buf.jsonl",
            )

            async def go():
                with (
                    patch("src.interfaces.datalake_publisher._BQ_AVAILABLE", True),
                    patch("src.interfaces.datalake_publisher.bigquery", mock_bq, create=True),
                ):
                    async with pub as p:
                        return p._client

            client = asyncio.run(go())
            assert client is None

    def test_bq_flush_success_increments_total(self):
        """Lines 205-211: no errors → published_total increments, no local file."""
        mock_client = MagicMock()
        mock_client.insert_rows_json.return_value = []  # no errors

        with tempfile.TemporaryDirectory() as d:
            buf_path = Path(d) / "fallback.jsonl"
            pub = DataLakePublisher(
                project_id="proj",
                batch_size=2,
                local_buffer_path=str(buf_path),
            )
            pub._client = mock_client

            async def go():
                pub._buffer.append(_row(site_id="s1"))
                pub._buffer.append(_row(site_id="s2"))
                await pub._flush()
                return pub.published_total

            total = asyncio.run(go())
            assert total == 2
            assert not buf_path.exists()  # no local fallback needed

    def test_bq_flush_errors_triggers_local_fallback(self):
        """Lines 201-204: BQ returns errors → row written to local file."""
        mock_client = MagicMock()
        mock_client.insert_rows_json.return_value = [{"index": 0, "errors": ["bad"]}]

        with tempfile.TemporaryDirectory() as d:
            buf_path = Path(d) / "fallback.jsonl"
            pub = DataLakePublisher(
                project_id="proj",
                batch_size=2,
                local_buffer_path=str(buf_path),
            )
            pub._client = mock_client

            async def go():
                pub._buffer.append(_row(site_id="s1"))
                pub._buffer.append(_row(site_id="s2"))
                await pub._flush()

            asyncio.run(go())
            assert buf_path.exists()

    def test_bq_flush_exception_triggers_local_fallback(self):
        """Lines 212-214: executor raises → calls _flush_to_local."""
        mock_client = MagicMock()
        mock_client.insert_rows_json.side_effect = Exception("network error")

        with tempfile.TemporaryDirectory() as d:
            buf_path = Path(d) / "fallback.jsonl"
            pub = DataLakePublisher(
                project_id="proj",
                batch_size=1,
                local_buffer_path=str(buf_path),
            )
            pub._client = mock_client
            pub._buffer.append(_row())

            asyncio.run(pub._flush())
            assert buf_path.exists()

    def test_aexit_closes_bq_client(self):
        """Line 145: client.close() called on aexit."""
        mock_client = MagicMock()
        mock_client.close = MagicMock()

        with tempfile.TemporaryDirectory() as d:
            pub = DataLakePublisher(
                project_id="",
                local_buffer_path=d + "/buf.jsonl",
            )
            pub._client = mock_client

            asyncio.run(pub.__aexit__(None, None, None))
            mock_client.close.assert_called_once()

    def test_local_flush_exception_does_not_raise(self):
        """Line 229: write to unwritable path logs but does not raise."""
        pub = DataLakePublisher(
            project_id="",
            batch_size=1,
            local_buffer_path="/root/no_write_permission/buf.jsonl",
        )

        async def go():
            pub._buffer.append(_row())
            await pub._flush()  # should not raise

        asyncio.run(go())  # test passes if no exception
