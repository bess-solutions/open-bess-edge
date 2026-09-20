"""Oráculo independiente: cantools decodifica las mismas tramas que el decodificador del proyecto."""
import math
import random
from pathlib import Path

import pytest

from open_bess_edge.experimental.can_bms import DBCParser, IndustrialCANBMSDriver

cantools = pytest.importorskip("cantools")

DBC_DIR = Path(__file__).resolve().parents[1] / "data" / "can_dbc"
DBCS = sorted(DBC_DIR.glob("*.dbc"))


@pytest.mark.parametrize("dbc", DBCS, ids=lambda p: p.stem)
def test_decoder_matches_cantools_on_random_payloads(dbc):
    ours = DBCParser(str(dbc))
    ref = cantools.database.load_file(str(dbc))
    rng = random.Random(1234)
    checked = 0
    for msg in ref.messages:
        assert msg.frame_id in ours.messages_by_id, f"{dbc.stem}: falta el mensaje {msg.name}"
        for _ in range(60):
            data = bytes(rng.randrange(256) for _ in range(msg.length))
            want = msg.decode(data, decode_choices=False, scaling=True)
            got = ours.messages_by_id[msg.frame_id].decode(data)
            for name, w in want.items():
                assert name in got, (dbc.stem, msg.name, name)
                assert math.isclose(float(got[name]), float(w), rel_tol=1e-9, abs_tol=1e-9), (dbc.stem, msg.name, name, got[name], w, data.hex())
                checked += 1
    assert checked > 100


def test_driver_default_dbcs_load_and_unknown_id_reports_error():
    d = IndustrialCANBMSDriver()
    assert len(d.parsers) == len(DBCS) >= 3
    assert "error" in d.decode_raw_frame(0x123, b"\x00" * 8)
