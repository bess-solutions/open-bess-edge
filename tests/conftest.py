from __future__ import annotations

import pytest

from open_bess_edge.config import EdgeConfig, parse_config
from open_bess_edge.models import Telemetry


def make_cfg(**over) -> EdgeConfig:
    raw = {
        "node": {"device_id": "test-node"},
        "plant": {"p_nominal_kw": 1000.0, "e_nominal_kwh": 2000.0, "v_nominal_v": 400.0},
        "volt_var": {"q_max_kvar": 600.0},
        "runtime": {"cycle_ms": 100, "comm_loss_hold_s": 2.0, "startup_valid_cycles": 3},
        "health": {"enabled": False},
    }
    for k, v in over.items():
        raw.setdefault(k, {})
        raw[k] = {**raw[k], **v} if isinstance(v, dict) else v
    return parse_config(raw, source="<test>")


@pytest.fixture
def cfg() -> EdgeConfig:
    return make_cfg()


def tel(**kw) -> Telemetry:
    d = dict(t_mono=0.0, t_wall=0.0, frequency_hz=50.0, v_grid_v=400.0, p_kw=0.0, q_kvar=0.0, soc_pct=60.0,
             soh_pct=98.0, cell_v_min_v=3.20, cell_v_max_v=3.22, cell_t_max_c=30.0, isolation_kohm=1200.0)
    d.update(kw)
    return Telemetry(**d)
