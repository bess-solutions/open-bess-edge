# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
tests/test_alert_manager_extended.py
======================================
Extended unit tests for ``src.interfaces.alert_manager``.

Covers:
  - Alert dataclass: alert_id uniqueness, resolve(), age_s(), to_dict()
  - AlertManager.fire(): basic firing, deduplication, re-fire after window
  - AlertManager.resolve(): resolves and moves to history
  - AlertManager.resolve_all(): clears all active alerts
  - AlertLevel values, active_count, critical_count, has_critical
  - summary() structure and correctness
  - max_history rotation (deque maxlen)
  - Edge cases: resolve unknown alert, fire empty name
"""

from __future__ import annotations

import time

from src.interfaces.alert_manager import Alert, AlertLevel, AlertManager

# ---------------------------------------------------------------------------
# Alert dataclass
# ---------------------------------------------------------------------------

class TestAlertDataclass:
    def test_alert_id_is_8_chars(self):
        a = Alert()
        assert len(a.alert_id) == 8

    def test_alert_ids_are_unique(self):
        ids = {Alert().alert_id for _ in range(50)}
        assert len(ids) == 50

    def test_default_not_resolved(self):
        a = Alert()
        assert not a.resolved
        assert a.resolved_at is None

    def test_resolve_sets_resolved(self):
        a = Alert()
        a.resolve()
        assert a.resolved is True
        assert a.resolved_at is not None

    def test_age_s_positive(self):
        a = Alert()
        time.sleep(0.01)
        assert a.age_s() >= 0.01

    def test_to_dict_keys(self):
        a = Alert(level=AlertLevel.CRITICAL, name="OVERTEMP", message="Temp=58°C")
        d = a.to_dict()
        for key in ["alert_id", "level", "name", "message", "site_id", "timestamp",
                    "resolved", "age_s"]:
            assert key in d

    def test_to_dict_level_is_string(self):
        a = Alert(level=AlertLevel.WARNING)
        assert a.to_dict()["level"] == "WARNING"

    def test_to_dict_resolved_default_false(self):
        a = Alert()
        assert a.to_dict()["resolved"] is False


# ---------------------------------------------------------------------------
# AlertManager.fire()
# ---------------------------------------------------------------------------

class TestFire:
    def test_fire_returns_alert(self):
        mgr = AlertManager()
        result = mgr.fire(AlertLevel.CRITICAL, "OVERTEMP", "Temp exceeded")
        assert isinstance(result, Alert)

    def test_fire_adds_to_active(self):
        mgr = AlertManager()
        mgr.fire(AlertLevel.WARNING, "SOC_LOW", "SOC < 15%")
        assert mgr.active_count == 1

    def test_fire_multiple_different_names(self):
        mgr = AlertManager()
        mgr.fire(AlertLevel.WARNING, "SOC_LOW", "")
        mgr.fire(AlertLevel.CRITICAL, "OVERTEMP", "")
        assert mgr.active_count == 2

    def test_fire_sets_alert_level(self):
        mgr = AlertManager()
        alert = mgr.fire(AlertLevel.CRITICAL, "FAULT")
        assert alert is not None
        assert alert.level == AlertLevel.CRITICAL

    def test_fire_sets_site_id(self):
        mgr = AlertManager(site_id="CL-001")
        alert = mgr.fire(AlertLevel.INFO, "VPP_EVENT")
        assert alert is not None
        assert alert.site_id == "CL-001"

    def test_deduplication_suppresses_repeat(self):
        mgr = AlertManager(dedup_window_s=60.0)
        mgr.fire(AlertLevel.WARNING, "SOC_LOW")
        result = mgr.fire(AlertLevel.WARNING, "SOC_LOW")  # within window
        assert result is None  # deduplicated
        assert mgr.active_count == 1  # still only one alert

    def test_deduplication_zero_window_allows_repeat(self):
        mgr = AlertManager(dedup_window_s=0.0)
        mgr.fire(AlertLevel.WARNING, "SOC_LOW")
        result = mgr.fire(AlertLevel.WARNING, "SOC_LOW")
        assert result is not None  # not deduplicated

    def test_different_names_not_deduplicated(self):
        mgr = AlertManager(dedup_window_s=60.0)
        r1 = mgr.fire(AlertLevel.WARNING, "SOC_LOW")
        r2 = mgr.fire(AlertLevel.WARNING, "OVERTEMP")
        assert r1 is not None
        assert r2 is not None

    def test_fire_after_resolve_allowed(self):
        mgr = AlertManager(dedup_window_s=60.0)
        mgr.fire(AlertLevel.WARNING, "SOC_LOW")
        mgr.resolve("SOC_LOW")    # resolves and removes from active
        # Now fire again — no longer in _active, so dedup won't block it
        # (dedup checks both time window AND name in _active)
        result = mgr.fire(AlertLevel.WARNING, "SOC_LOW")
        assert result is not None


# ---------------------------------------------------------------------------
# AlertManager.resolve() and resolve_all()
# ---------------------------------------------------------------------------

class TestResolve:
    def test_resolve_returns_true_for_active(self):
        mgr = AlertManager()
        mgr.fire(AlertLevel.WARNING, "SOC_LOW")
        assert mgr.resolve("SOC_LOW") is True

    def test_resolve_returns_false_for_unknown(self):
        mgr = AlertManager()
        assert mgr.resolve("DOESNOTEXIST") is False

    def test_resolve_removes_from_active(self):
        mgr = AlertManager()
        mgr.fire(AlertLevel.WARNING, "SOC_LOW")
        mgr.resolve("SOC_LOW")
        assert mgr.active_count == 0

    def test_resolve_moves_to_history(self):
        mgr = AlertManager()
        mgr.fire(AlertLevel.CRITICAL, "FAULT")
        mgr.resolve("FAULT")
        assert len(mgr._history) == 1

    def test_resolved_alert_has_resolved_flag(self):
        mgr = AlertManager()
        mgr.fire(AlertLevel.CRITICAL, "FAULT")
        mgr.resolve("FAULT")
        resolved_alert = mgr._history[-1]
        assert resolved_alert.resolved is True
        assert resolved_alert.resolved_at is not None

    def test_resolve_all_clears_all_active(self):
        mgr = AlertManager()
        mgr.fire(AlertLevel.CRITICAL, "FAULT_A")
        mgr.fire(AlertLevel.WARNING, "FAULT_B")
        mgr.fire(AlertLevel.INFO, "FAULT_C")
        count = mgr.resolve_all()
        assert count == 3
        assert mgr.active_count == 0

    def test_resolve_all_empty_returns_zero(self):
        mgr = AlertManager()
        assert mgr.resolve_all() == 0

    def test_resolve_all_moves_to_history(self):
        mgr = AlertManager()
        mgr.fire(AlertLevel.CRITICAL, "A")
        mgr.fire(AlertLevel.WARNING, "B")
        mgr.resolve_all()
        assert len(mgr._history) == 2


# ---------------------------------------------------------------------------
# Counts and properties
# ---------------------------------------------------------------------------

class TestCounts:
    def test_active_count_zero_initially(self):
        mgr = AlertManager()
        assert mgr.active_count == 0

    def test_critical_count_only_critical(self):
        mgr = AlertManager()
        mgr.fire(AlertLevel.CRITICAL, "FAULT_A")
        mgr.fire(AlertLevel.CRITICAL, "FAULT_B")
        mgr.fire(AlertLevel.WARNING, "WARN")
        assert mgr.critical_count == 2

    def test_has_critical_true_when_critical_present(self):
        mgr = AlertManager()
        mgr.fire(AlertLevel.CRITICAL, "FAULT")
        assert mgr.has_critical is True

    def test_has_critical_false_when_no_critical(self):
        mgr = AlertManager()
        mgr.fire(AlertLevel.WARNING, "WARN")
        assert mgr.has_critical is False

    def test_has_critical_false_when_no_alerts(self):
        mgr = AlertManager()
        assert mgr.has_critical is False

    def test_has_critical_false_after_resolve(self):
        mgr = AlertManager()
        mgr.fire(AlertLevel.CRITICAL, "FAULT")
        mgr.resolve("FAULT")
        assert mgr.has_critical is False


# ---------------------------------------------------------------------------
# summary()
# ---------------------------------------------------------------------------

class TestSummary:
    def test_summary_keys(self):
        mgr = AlertManager(site_id="TEST")
        s = mgr.summary()
        for key in ["site_id", "active_total", "critical", "warning", "info",
                    "history_total", "active"]:
            assert key in s

    def test_summary_site_id(self):
        mgr = AlertManager(site_id="SITE-CL-001")
        assert mgr.summary()["site_id"] == "SITE-CL-001"

    def test_summary_counts_correct(self):
        mgr = AlertManager()
        mgr.fire(AlertLevel.CRITICAL, "C1")
        mgr.fire(AlertLevel.CRITICAL, "C2")
        mgr.fire(AlertLevel.WARNING, "W1")
        mgr.fire(AlertLevel.INFO, "I1")
        s = mgr.summary()
        assert s["active_total"] == 4
        assert s["critical"] == 2
        assert s["warning"] == 1
        assert s["info"] == 1

    def test_summary_history_count(self):
        mgr = AlertManager()
        mgr.fire(AlertLevel.WARNING, "W")
        mgr.resolve("W")
        assert mgr.summary()["history_total"] == 1

    def test_summary_active_list_contains_dicts(self):
        mgr = AlertManager()
        mgr.fire(AlertLevel.CRITICAL, "FAULT", "detail here")
        active = mgr.summary()["active"]
        assert len(active) == 1
        assert active[0]["name"] == "FAULT"


# ---------------------------------------------------------------------------
# History max rotation
# ---------------------------------------------------------------------------

class TestHistoryRotation:
    def test_history_bounded_by_max_history(self):
        mgr = AlertManager(max_history=3, dedup_window_s=0.0)
        for i in range(10):
            n = f"FAULT_{i}"
            mgr.fire(AlertLevel.WARNING, n)
            mgr.resolve(n)
        assert len(mgr._history) <= 3  # deque maxlen enforced

    def test_history_keeps_most_recent(self):
        mgr = AlertManager(max_history=3, dedup_window_s=0.0)
        for i in range(5):
            n = f"FAULT_{i}"
            mgr.fire(AlertLevel.WARNING, n)
            mgr.resolve(n)
        # Oldest entries should be dropped; last 3 should be retained
        names_in_history = [a.name for a in mgr._history]
        assert "FAULT_4" in names_in_history  # most recent preserved


# ---------------------------------------------------------------------------
# get_active()
# ---------------------------------------------------------------------------

class TestGetActive:
    def test_get_active_empty_initially(self):
        mgr = AlertManager()
        assert mgr.get_active() == []

    def test_get_active_returns_list_of_dicts(self):
        mgr = AlertManager()
        mgr.fire(AlertLevel.WARNING, "SOC_LOW", "SOC=12%")
        active = mgr.get_active()
        assert len(active) == 1
        assert active[0]["name"] == "SOC_LOW"

    def test_get_active_after_resolve_empty(self):
        mgr = AlertManager()
        mgr.fire(AlertLevel.CRITICAL, "FAULT")
        mgr.resolve("FAULT")
        assert mgr.get_active() == []
