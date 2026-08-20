# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/core/offline_cen_buffer.py
===============================
BESSAI Edge Gateway — Resilient Offline SQLite Ring Buffer for CEN Telemetry.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = ["OfflineCENBuffer", "TelemetryRecord"]


@dataclass
class TelemetryRecord:
    timestamp: float
    plant_id: str
    active_power_mw: float
    reactive_power_mvar: float
    soc_pct: float
    grid_freq_hz: float
    status_code: int


class OfflineCENBuffer:
    """Local SQLite Ring Buffer for CEN telemetry resilience."""

    def __init__(self, db_path: str = ":memory:", max_records: int = 259200):
        self.db_path = db_path
        self.max_records = max_records
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self.db_path == ":memory:":
            if self._conn is None:
                self._conn = sqlite3.connect(":memory:")
            return self._conn
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        conn = self._get_connection()
        conn.execute("""
        CREATE TABLE IF NOT EXISTS cen_telemetry_buffer (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            plant_id TEXT NOT NULL,
            active_power_mw REAL,
            reactive_power_mvar REAL,
            soc_pct REAL,
            grid_freq_hz REAL,
            status_code INTEGER,
            synced INTEGER DEFAULT 0
        )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cen_unsynced ON cen_telemetry_buffer(synced, timestamp)")
        conn.commit()

    def record_telemetry(self, record: TelemetryRecord) -> int:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO cen_telemetry_buffer (timestamp, plant_id, active_power_mw, reactive_power_mvar, soc_pct, grid_freq_hz, status_code, synced)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        """, (record.timestamp, record.plant_id, record.active_power_mw, record.reactive_power_mvar, record.soc_pct, record.grid_freq_hz, record.status_code))
        row_id = cur.lastrowid

        # Ring buffer prune if exceeded
        conn.execute("""
        DELETE FROM cen_telemetry_buffer
        WHERE id IN (
            SELECT id FROM cen_telemetry_buffer ORDER BY id ASC LIMIT MAX(0, (SELECT COUNT(*) FROM cen_telemetry_buffer) - ?)
        )
        """, (self.max_records,))
        conn.commit()
        return row_id or 0

    def get_unsynced_batch(self, limit: int = 100) -> list[dict[str, Any]]:
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
        SELECT id, timestamp, plant_id, active_power_mw, reactive_power_mvar, soc_pct, grid_freq_hz, status_code
        FROM cen_telemetry_buffer
        WHERE synced = 0
        ORDER BY timestamp ASC
        LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]

    def mark_as_synced(self, record_ids: list[int]) -> int:
        if not record_ids:
            return 0
        conn = self._get_connection()
        cur = conn.cursor()
        placeholders = ",".join(["?"] * len(record_ids))
        cur.execute(f"UPDATE cen_telemetry_buffer SET synced = 1 WHERE id IN ({placeholders})", record_ids)
        conn.commit()
        return cur.rowcount

    def get_pending_count(self) -> int:
        conn = self._get_connection()
        return conn.execute("SELECT COUNT(*) FROM cen_telemetry_buffer WHERE synced = 0").fetchone()[0]
