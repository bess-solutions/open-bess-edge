"""
tests/test_alert_manager.py
============================
Unit tests for AlertManager and Alert dataclass.
"""

from __future__ import annotations

import time

from src.interfaces.alert_manager import Alert, AlertLevel, AlertManager


class TestAlert:
    def test_alert_level_enum_values(self):
        assert AlertLevel.CRITICAL.value == "CRITICAL"
        assert AlertLevel.WARNING.value == "WARNING"
        assert AlertLevel.INFO.value == "INFO"

    def test_alert_defaults_unresolved(self):
        a = Alert(name="TEST")
        assert a.resolved is False
        assert a.resolved_at is None

    def test_alert_resolve_sets_flags(self):
        a = Alert(name="TEST")
        a.resolve()
        assert a.resolved is True
        assert a.resolved_at is not None

    def test_alert_age_increases(self):
        a = Alert(name="TEST")
        time.sleep(0.01)
        assert a.age_s() > 0.0

    def test_alert_to_dict_has_required_keys(self):
        a = Alert(level=AlertLevel.CRITICAL, name="OVERTEMP", message="58°C")
        d = a.to_dict()
        for key in ("alert_id", "level", "name", "message", "timestamp", "resolved"):
            assert key in d


class TestAlertManager:
    def _mgr(self) -> AlertManager:
        return AlertManager(site_id="test", dedup_window_s=1.0)

    def test_fire_returns_alert(self):
        mgr = self._mgr()
        alert = mgr.fire(AlertLevel.WARNING, "TEST_ALERT", "test msg")
        assert isinstance(alert, Alert)

    def test_fire_increments_active_count(self):
        mgr = self._mgr()
        mgr.fire(AlertLevel.WARNING, "ALERT_A")
        mgr.fire(AlertLevel.WARNING, "ALERT_B")
        assert mgr.active_count == 2

    def test_deduplication_suppresses_same_name(self):
        mgr = self._mgr()
        r1 = mgr.fire(AlertLevel.WARNING, "DUP_ALERT")
        r2 = mgr.fire(AlertLevel.WARNING, "DUP_ALERT")  # within dedup window
        assert r1 is not None
        assert r2 is None
        assert mgr.active_count == 1

    def test_fire_different_names_not_deduped(self):
        mgr = self._mgr()
        mgr.fire(AlertLevel.WARNING, "ALERT_X")
        mgr.fire(AlertLevel.WARNING, "ALERT_Y")
        assert mgr.active_count == 2

    def test_resolve_removes_from_active(self):
        mgr = self._mgr()
        mgr.fire(AlertLevel.WARNING, "RESOLVE_ME")
        resolved = mgr.resolve("RESOLVE_ME")
        assert resolved is True
        assert mgr.active_count == 0

    def test_resolve_missing_returns_false(self):
        mgr = self._mgr()
        assert mgr.resolve("NONEXISTENT") is False

    def test_critical_count(self):
        mgr = self._mgr()
        mgr.fire(AlertLevel.CRITICAL, "CRIT_1")
        mgr.fire(AlertLevel.CRITICAL, "CRIT_2")
        mgr.fire(AlertLevel.WARNING, "WARN_1")
        assert mgr.critical_count == 2
        assert mgr.has_critical is True

    def test_resolve_all(self):
        mgr = self._mgr()
        mgr.fire(AlertLevel.WARNING, "A1")
        mgr.fire(AlertLevel.WARNING, "A2")
        n = mgr.resolve_all()
        assert n == 2
        assert mgr.active_count == 0

    def test_summary_dict_structure(self):
        mgr = self._mgr()
        mgr.fire(AlertLevel.CRITICAL, "OVERTEMP")
        mgr.fire(AlertLevel.WARNING, "LOW_SOC")
        s = mgr.summary()
        assert s["active_total"] == 2
        assert s["critical"] == 1
        assert s["warning"] == 1
        assert isinstance(s["active"], list)
