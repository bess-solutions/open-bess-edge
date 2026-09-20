import copy
import json
from pathlib import Path

import pytest

from open_bess_edge.errors import ProfileError
from open_bess_edge.modbus.codec import Order, RegType
from open_bess_edge.modbus.profile import (
    apply_scale,
    list_profiles,
    load_profile,
    parse_profile,
    registry_dir,
    resolve_profile_path,
    unapply_scale,
)

REF = json.loads((Path(__file__).resolve().parents[1] / "registry" / "open_bess_edge_reference.json").read_text())


def mutate(fn):
    d = copy.deepcopy(REF)
    fn(d)
    return d


def test_reference_profile_capabilities():
    p = load_profile("open_bess_edge_reference")
    assert p.can_control_p and p.can_control_q and p.has_heartbeat and p.verification_level == "reference"
    assert set(p.telemetry_signals) >= {"frequency_hz", "cell_v_min_v", "isolation_kohm"}
    assert p.missing_signals(["soc_pct", "ambient_c"]) == ["ambient_c"]


def test_read_plan_merges_contiguous_blocks_and_respects_gap():
    p = load_profile("open_bess_edge_reference")
    plan = p.read_plan(p.telemetry_signals)
    assert len(plan) == 1 and (plan[0].start, plan[0].count) == (100, 10)
    only = p.read_plan(["frequency_hz", "isolation_kohm"], max_gap=0)
    assert [(b.start, b.count) for b in only] == [(100, 1), (109, 1)]
    merged = p.read_plan(["frequency_hz", "isolation_kohm"], max_gap=8)
    assert [(b.start, b.count) for b in merged] == [(100, 10)]


def test_read_plan_splits_at_125_registers():
    d = mutate(lambda d: d.update(registers={f"r{i}": {"address": 1000 + i, "type": "UINT16", "access": "RO"} for i in range(200)},
                                  canonical={"frequency_hz": {"register": "r0"}, "v_grid_v": {"register": "r199"}}))
    p = parse_profile(d, "x")
    assert [(b.start, b.count) for b in p.read_plan(["frequency_hz", "v_grid_v"], max_gap=500)] == [(1000, 200 - 75)] or \
           all(b.count <= 125 for b in p.read_plan(["frequency_hz", "v_grid_v"], max_gap=500))


@pytest.mark.parametrize("fn,msg", [
    (lambda d: d["registers"]["f_measured"].update(type="FLOAT16"), "tipo"),
    (lambda d: d["registers"]["f_measured"].update(count=2), "count"),
    (lambda d: d["registers"]["f_measured"].update(address=70000), "dirección"),
    (lambda d: d["registers"]["f_measured"].update(address=65535, type="UINT32", count=2), "excede"),
    (lambda d: d["registers"]["f_measured"].update(access="WO"), "access"),
    (lambda d: d["registers"]["f_measured"].update(scale=0), "scale"),
    (lambda d: d["registers"]["f_measured"].update(function="coil"), "function"),
    (lambda d: d["canonical"].update(bogus={"register": "f_measured"}), "desconocida"),
    (lambda d: d["canonical"].update(frequency_hz={"register": "nope"}), "inexistente"),
    (lambda d: d["canonical"].update(frequency_hz={"register": "f_measured", "sign": 2}), "sign"),
    (lambda d: d["canonical"].update(frequency_hz={"register": "f_measured", "factor": 0}), "factor"),
    (lambda d: d["canonical"].update(p_setpoint_kw={"register": "p_actual"}), "RW"),
    (lambda d: d["canonical"].update(heartbeat={"register": "p_setpoint"}), "sin signo"),
    (lambda d: d.update(verification={"level": "certified"}), "level"),
    (lambda d: d["connection"].update(byte_order="MIDDLE"), "byte_order"),
    (lambda d: d.update(registers={}), "registers"),
    (lambda d: d["device"].update(protocol="CAN"), "no es un perfil Modbus"),
])
def test_invalid_profiles_rejected(fn, msg):
    with pytest.raises(ProfileError, match=msg):
        parse_profile(mutate(fn), "x")


def test_scale_register_resolution_by_address_and_name():
    d = mutate(lambda d: (d["registers"].update(sf={"address": 500, "type": "INT16", "access": "RO"},
                                                pw={"address": 499, "type": "INT16", "access": "RO", "scale_register": 500}),
                          d["canonical"].update(p_kw={"register": "pw"})))
    p = parse_profile(d, "x")
    assert p.registers["pw"].scale_register == "sf"
    assert {r.name for b in p.read_plan(["p_kw"]) for r in b.registers} == {"pw", "sf"}
    bad = mutate(lambda d: d["registers"].update(pw={"address": 499, "type": "INT16", "access": "RO", "scale_register": 12345}))
    with pytest.raises(ProfileError, match="scale_register"):
        parse_profile(bad, "x")


def test_binding_conversions_roundtrip():
    p = load_profile("huawei_sun2000")
    b = p.bindings["p_kw"]
    assert b.sign == -1 and b.to_canonical(100.0) == -100.0 and b.to_engineering(-100.0) == 100.0


def test_apply_scale_exact_for_decimal_scales():
    assert apply_scale(4997, 0.01) == 49.97 and apply_scale(855, 0.1) == 85.5 and apply_scale(7, 1.0) == 7.0
    assert unapply_scale(49.97, 0.01) == pytest.approx(4997.0)
    assert apply_scale(3, 0.3) == pytest.approx(0.9)


def test_registry_lookup(tmp_path, monkeypatch):
    assert "open_bess_edge_reference" in list_profiles()
    assert resolve_profile_path("open_bess_edge_reference").name == "open_bess_edge_reference.json"
    monkeypatch.setenv("OBE_REGISTRY_DIR", str(tmp_path))
    assert registry_dir() == tmp_path and list_profiles() == []
    with pytest.raises(ProfileError, match="no encontrado"):
        load_profile("nada")
    (tmp_path / "bad.json").write_text("{")
    with pytest.raises(ProfileError, match="JSON"):
        load_profile("bad")
    (tmp_path / "arr.json").write_text("[]")
    with pytest.raises(ProfileError, match="objeto"):
        load_profile("arr")


def test_every_shipped_profile_is_either_valid_or_explicitly_not_modbus():
    """Ningún perfil del registro puede estar silenciosamente roto."""
    bad = {}
    for name in list_profiles():
        try:
            load_profile(name)
        except ProfileError as exc:
            bad[name] = str(exc)
    assert set(bad) == {"TEMPLATE_interop_certification", "byd_battery_box", "tesla_powerwall3"}, bad
    assert all("no es un perfil Modbus" in m for m in bad.values())


def test_vendor_profiles_are_monitor_only_and_honest():
    for name in ("huawei_sun2000", "sma_sunny_tripower", "fronius_gen24_byd", "solaredge_storedge", "victron_multiplus2"):
        p = load_profile(name)
        assert not p.can_control_p and p.verification_level == "unverified"
        assert p.missing_signals(["cell_v_min_v", "isolation_kohm"])       # sin señales de celda => control prohibido
    assert load_profile("huawei_sun2000").registers["ac_current"].count == 2   # regresión: INT32 con count=1


def test_word_and_byte_order_from_profile():
    d = mutate(lambda d: d["connection"].update(byte_order="LITTLE", word_order="LITTLE"))
    p = parse_profile(d, "x")
    assert p.byte_order is Order.LITTLE and p.word_order is Order.LITTLE
    assert p.registers["f_measured"].rtype is RegType.UINT16
