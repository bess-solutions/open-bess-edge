# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

import time
from src.core.offline_cen_buffer import OfflineCENBuffer, TelemetryRecord


def test_offline_buffer_store_and_sync():
    buf = OfflineCENBuffer(db_path=":memory:", max_records=100)
    now = time.time()

    # Store 3 telemetry samples
    for i in range(3):
        buf.record_telemetry(TelemetryRecord(
            timestamp=now + i,
            plant_id="BESS-LINARES-01",
            active_power_mw=2.5,
            reactive_power_mvar=0.2,
            soc_pct=85.0 - i,
            grid_freq_hz=50.01,
            status_code=1,
        ))

    assert buf.get_pending_count() == 3

    batch = buf.get_unsynced_batch(limit=2)
    assert len(batch) == 2
    ids = [b["id"] for b in batch]

    buf.mark_as_synced(ids)
    assert buf.get_pending_count() == 1


def test_offline_buffer_ring_prune():
    buf = OfflineCENBuffer(db_path=":memory:", max_records=5)
    for i in range(10):
        buf.record_telemetry(TelemetryRecord(
            timestamp=float(i),
            plant_id="BESS-ATACAMA",
            active_power_mw=10.0,
            reactive_power_mvar=0.0,
            soc_pct=50.0,
            grid_freq_hz=50.0,
            status_code=1,
        ))

    assert buf.get_pending_count() == 5
