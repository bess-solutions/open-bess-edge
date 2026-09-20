"""Fuzz de invariantes de seguridad: eventos aleatorios (semilla fija) sobre el nodo completo por TCP real."""
import random

import pytest
from tests.harness import Harness

from open_bess_edge.models import NodeState

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


@pytest.mark.parametrize("seed", [1, 7, 42])
async def test_random_event_soak_never_violates_safety_invariants(seed):
    rng = random.Random(seed)
    h = await Harness().start()
    plant, srv = h.env.plant, h.env.server
    down_left = wexc_left = hot_left = bad_left = 0
    f = 50.0
    stats = {"trips": 0, "comm": 0, "nonzero_cycles": 0}
    try:
        for i in range(2500):
            # --- perturbaciones ---
            f = max(49.2, min(50.8, f + rng.gauss(0, 0.02) + (rng.choice([-0.3, 0.3]) if rng.random() < 0.004 else 0)))
            h.set_freq(f if rng.random() > 0.01 else 0.0)                          # lecturas basura ocasionales
            h.set_volt(rng.uniform(370, 430))
            if hot_left == 0 and rng.random() < 0.004:
                hot_left = rng.randint(1, 8); plant.overrides["cell_t_max_c"] = 60.0
            if hot_left and (hot_left := hot_left - 1) == 0:
                plant.overrides.pop("cell_t_max_c", None)
            if bad_left == 0 and rng.random() < 0.006:
                bad_left = rng.randint(1, 5)
                plant.overrides[rng.choice(["soc_pct", "cell_v_min_v", "cell_v_max_v"])] = rng.choice([-5.0, 0.0, 999.0])
            if bad_left and (bad_left := bad_left - 1) == 0:
                for k in ("soc_pct", "cell_v_min_v", "cell_v_max_v"):
                    plant.overrides.pop(k, None)
            if down_left == 0 and rng.random() < 0.004 and srv._server is not None:
                down_left = rng.randint(3, 45)
                await srv.stop(); srv.kick_all(); stats["comm"] += 1
            if down_left and (down_left := down_left - 1) == 0:
                await srv.start(); h.node.plant.transport.port = srv.port
            if wexc_left == 0 and rng.random() < 0.004:
                wexc_left = rng.randint(1, 6); srv.faults.write_exception = 4
            if wexc_left and (wexc_left := wexc_left - 1) == 0:
                srv.faults.write_exception = None
            if rng.random() < 0.02 and h.node.state is NodeState.TRIPPED:
                h.node.request_reset()
            if rng.random() < 0.01:
                h.node.set_dispatch(rng.uniform(-800, 900))

            res = await h.cycle(settle=0.001 if down_left == 0 else 0.0)
            if res.state == "TRIPPED":
                stats["trips"] += 1

            # --- invariantes ---
            p, q = h.p_reg, h.q_reg
            assert abs(p) <= 1000 and abs(q) <= 600, (i, p, q)
            assert abs(res.p_setpoint_kw) <= 1000 and abs(res.q_setpoint_kvar) <= 600
            if any(c in res.faults for c in ("BESS-GUARD-090", "BESS-GUARD-001", "BESS-GUARD-002", "BESS-GUARD-003", "BESS-GUARD-004")):
                assert res.p_setpoint_kw == 0.0 and res.q_setpoint_kvar == 0.0, (i, res)
                if res.commit_ok and srv._server is not None and down_left == 0:
                    assert p == 0 and q == 0, (i, res, p, q)
            if res.state in ("TRIPPED", "SAFE_STATE") and res.commit_ok and down_left == 0:
                assert p == 0 and q == 0, (i, res.state, p, q)
            if res.state == "STARTING":
                assert res.p_setpoint_kw == 0.0
            if p != 0 or q != 0:
                stats["nonzero_cycles"] += 1
        assert h.node.metrics.internal_errors == 0
        assert stats["nonzero_cycles"] > 100 and stats["comm"] >= 1     # el escenario sí ejercitó el control y las caídas
    finally:
        await srv.start() if srv._server is None else None
        await h.stop()
