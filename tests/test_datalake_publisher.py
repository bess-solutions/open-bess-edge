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


class TestDataLakePublisher:

    def test_publish_buffers_row(self):
        with tempfile.TemporaryDirectory() as d:
            pub = DataLakePublisher(
                project_id="", batch_size=3,
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
                project_id="", batch_size=3,
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
            pub = DataLakePublisher(project_id="", batch_size=10,
                                    local_buffer_path=d + "/buf2.jsonl")

            async def go():
                async with pub:
                    n = await pub.publish_many([_row(), _row()])
                    return n

            n = asyncio.run(go())
            assert n == 2

    def test_aexit_flushes_remaining(self):
        with tempfile.TemporaryDirectory() as d:
            path = d + "/flush_test.jsonl"
            pub = DataLakePublisher(project_id="", batch_size=10,
                                    local_buffer_path=path)

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
