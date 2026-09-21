"""API HTTP de despacho: autenticación, validación estricta, límites y auditoría."""
import asyncio
import json

import pytest
from tests.harness import Harness
from tests.test_installation import btm_cfg

from open_bess_edge.config import DispatchApiConfig
from open_bess_edge.errors import ConfigError
from open_bess_edge.runtime.dispatch_api import DispatchApi, load_api_token

TOKEN = "t" * 40
pytestmark = pytest.mark.e2e


async def call(port, method="POST", path="/api/v1/dispatch", token=TOKEN, body=None, raw_body=None, headers=None,
               content_length=True):
    data = raw_body if raw_body is not None else (json.dumps(body).encode() if body is not None else b"")
    hdr = {"Host": "x"}
    if token is not None:
        hdr["Authorization"] = f"Bearer {token}"
    if content_length:
        hdr["Content-Length"] = str(len(data))
    hdr.update(headers or {})
    r, w = await asyncio.open_connection("127.0.0.1", port)
    w.write((f"{method} {path} HTTP/1.1\r\n" + "".join(f"{k}: {v}\r\n" for k, v in hdr.items()) + "\r\n").encode() + data)
    await w.drain()
    resp = await asyncio.wait_for(r.read(), 4.0)
    w.close()
    head, _, payload = resp.partition(b"\r\n\r\n")
    return int(head.split()[1]), (json.loads(payload) if payload else {})


@pytest.fixture
async def rig():
    h = await Harness(btm_cfg(ffr={"ramp_pct_per_min": 6000.0})).start()
    api = DispatchApi(h.node, "127.0.0.1", 0, TOKEN)
    port = await api.start()
    yield h, api, port
    await api.stop()
    await h.stop()


def audits(h, verdict=None):
    ev = [e["data"] for e in h.node.audit.ring if e["kind"] == "DISPATCH_REQUEST"]
    return [d for d in ev if verdict is None or d["verdict"] == verdict]


async def test_valid_request_is_applied_and_audited(rig):
    h, _, port = rig
    code, out = await call(port, body={"p_base_kw": -150, "ttl_s": 30})
    assert code == 200 and out == {"ok": True, "verdict": "ACCEPTED", "applied_p_kw": -150.0, "ttl_s": 30}
    a = audits(h, "ACCEPTED")[0]
    assert a["peer"] == "127.0.0.1" and a["requested_p_kw"] == -150 and a["applied_p_kw"] == -150.0 and a["ttl_s"] == 30
    assert h.node._dispatch_p == -150.0 and h.node._dispatch_ttl == 30.0


async def test_request_beyond_capacity_is_clamped_and_still_goes_through_the_limiter(rig):
    h, _, port = rig
    await h.cycle(8)
    h.env.plant.site_load_kw = 100.0
    code, out = await call(port, body={"p_base_kw": 1e9, "ttl_s": 60})
    assert code == 200 and out["verdict"] == "CLAMPED" and out["applied_p_kw"] == 1000.0
    assert audits(h, "CLAMPED")[0]["requested_p_kw"] == 1e9
    for _ in range(25):
        await h.cycle()
    assert h.env.plant.p_kw <= 100.0 + 1e-6            # la API no salta la restricción de no-exportación


@pytest.mark.parametrize("token", [None, "", "wrong-" + "x" * 40, TOKEN[:-1], TOKEN + "x"])
async def test_authentication_failures(rig, token):
    h, _, port = rig
    code, out = await call(port, token=token, body={"p_base_kw": 10, "ttl_s": 5})
    assert code == 401 and out["ok"] is False
    assert h.node._dispatch_p == 0.0                   # no se aplicó nada
    assert audits(h, "REJECTED")[0]["reason"] == "AUTH_FAILURE"


async def test_auth_failure_audit_is_rate_limited(rig):
    h, _, port = rig
    for _ in range(6):
        assert (await call(port, token="bad", body={"p_base_kw": 1, "ttl_s": 1}))[0] == 401
    assert len(audits(h, "REJECTED")) == 1


@pytest.mark.parametrize("body,raw", [
    ({"p_base_kw": 10}, None), ({"ttl_s": 10}, None), ({"p_base_kw": 10, "ttl_s": 10, "extra": 1}, None),
    ({"p_base_kw": "10", "ttl_s": 10}, None), ({"p_base_kw": True, "ttl_s": 10}, None),
    ({"p_base_kw": 10, "ttl_s": 0}, None), ({"p_base_kw": 10, "ttl_s": -5}, None), ({"p_base_kw": 10, "ttl_s": 3601}, None),
    ([1, 2], None), (None, b"no es json"), (None, b'{"p_base_kw": NaN, "ttl_s": 10}'),
    (None, b'{"p_base_kw": Infinity, "ttl_s": 10}'), (None, b'{"p_base_kw": 1e999, "ttl_s": 10}'), (None, b"\xff\xfe"),
])
async def test_strict_body_validation(rig, body, raw):
    h, _, port = rig
    code, out = await call(port, body=body, raw_body=raw)
    assert code == 400 and out["ok"] is False and h.node._dispatch_p == 0.0
    assert audits(h, "REJECTED")[-1]["reason"].startswith("INVALID_BODY")


async def test_protocol_level_rejections(rig):
    h, _, port = rig
    assert (await call(port, method="GET"))[0] == 404
    assert (await call(port, path="/otra"))[0] == 404
    assert (await call(port, body={"p_base_kw": 1, "ttl_s": 1}, content_length=False))[0] == 400
    assert (await call(port, body={"p_base_kw": 1, "ttl_s": 1}, headers={"Content-Length": "abc"}))[0] == 400
    code, _ = await call(port, raw_body=b"x" * 5000)
    assert code == 413 and audits(h, "REJECTED")[-1]["reason"] == "BODY_TOO_LARGE"
    r, w = await asyncio.open_connection("127.0.0.1", port)          # basura sin cabeceras válidas
    w.write(b"\x00\x01garbage\r\n\r\n")
    await w.drain()
    assert (await asyncio.wait_for(r.read(), 4.0)).startswith(b"HTTP/1.1 400")
    w.close()
    assert h.node._dispatch_p == 0.0


async def test_rate_limit_returns_429():
    h = await Harness(btm_cfg()).start()
    api = DispatchApi(h.node, "127.0.0.1", 0, TOKEN, rate_limit_per_s=2.0)
    port = await api.start()
    try:
        codes = [(await call(port, body={"p_base_kw": 1, "ttl_s": 1}))[0] for _ in range(4)]
        assert codes[:2] == [200, 200] and codes[2:] == [429, 429]
        h.clock.advance(1.0)                                            # se recargan los tokens
        assert (await call(port, body={"p_base_kw": 1, "ttl_s": 1}))[0] == 200
    finally:
        await api.stop()
        await h.stop()


async def test_monitor_only_node_refuses_dispatch(rig):
    h, _, port = rig
    h.node.control_enabled = False
    code, out = await call(port, body={"p_base_kw": 10, "ttl_s": 5})
    assert code == 503 and audits(h, "REJECTED")[-1]["reason"] == "MONITOR_ONLY"


async def test_construction_guards():
    h = await Harness(btm_cfg()).start()
    try:
        with pytest.raises(ConfigError, match="no-loopback"):
            DispatchApi(h.node, "0.0.0.0", 0, TOKEN)                    # noqa: S104
        with pytest.raises(ConfigError, match="al menos 32"):
            DispatchApi(h.node, "127.0.0.1", 0, "corto")
    finally:
        await h.stop()


def test_token_loading(tmp_path):
    cfg = DispatchApiConfig(enabled=True)
    assert load_api_token(cfg, {"OBE_API_TOKEN": "  " + TOKEN + "\n"}) == TOKEN
    with pytest.raises(ConfigError, match="sin token"):
        load_api_token(cfg, {})
    with pytest.raises(ConfigError, match="al menos 32"):
        load_api_token(cfg, {"OBE_API_TOKEN": "x" * 31})
    f = tmp_path / "tok"
    f.write_text(TOKEN + "\n")
    assert load_api_token(DispatchApiConfig(enabled=True, token_file=f), {}) == TOKEN
    assert load_api_token(DispatchApiConfig(enabled=True, token_file=f), {"OBE_API_TOKEN": "x" * 40}) == TOKEN   # el archivo prevalece
    with pytest.raises(ConfigError, match="token_file"):
        load_api_token(DispatchApiConfig(enabled=True, token_file=tmp_path / "no"), {})
    assert DispatchApiConfig().enabled is False                         # deshabilitada por defecto
