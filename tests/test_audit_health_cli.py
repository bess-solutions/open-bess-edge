import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest
from tests.harness import Harness

from open_bess_edge.cli import main
from open_bess_edge.runtime.audit import AuditLog, verify_chain
from open_bess_edge.runtime.health import HealthServer

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------- auditoría
def test_audit_chain_verifies_and_detects_tampering(tmp_path):
    p = tmp_path / "a.jsonl"
    a = AuditLog(p)
    for i in range(20):
        a.event("X", 1000.0 + i, i=i)
    a.close()
    assert verify_chain([p])[0]
    lines = p.read_text().splitlines()
    # 1. alteración de contenido
    bad = json.loads(lines[5]); bad["data"]["i"] = 999
    t1 = tmp_path / "t1.jsonl"; t1.write_text("\n".join(lines[:5] + [json.dumps(bad)] + lines[6:]) + "\n")
    ok, msg = verify_chain([t1]); assert not ok and "alterado" in msg
    # 2. borrado de un registro
    t2 = tmp_path / "t2.jsonl"; t2.write_text("\n".join(lines[:5] + lines[6:]) + "\n")
    ok, msg = verify_chain([t2]); assert not ok
    # 3. reordenamiento
    t3 = tmp_path / "t3.jsonl"; t3.write_text("\n".join(lines[:4] + [lines[5], lines[4]] + lines[6:]) + "\n")
    assert not verify_chain([t3])[0]
    # 4. línea ilegible
    t4 = tmp_path / "t4.jsonl"; t4.write_text("\n".join(lines[:3]) + "\nno-json\n")
    assert not verify_chain([t4])[0]


def test_audit_resume_and_rotation(tmp_path):
    p = tmp_path / "a.jsonl"
    a = AuditLog(p, max_bytes=10_000, backups=3)
    for i in range(200):
        a.event("X", 1.0 + i, pad="x" * 100)
    a.close()
    files = sorted(tmp_path.glob("a.jsonl*"))
    assert len(files) >= 2
    # reanudar: la cadena continúa
    b = AuditLog(p, max_bytes=10_000, backups=3)
    rec = b.event("AFTER", 999.0)
    b.close()
    chain = [tmp_path / "a.jsonl.3", tmp_path / "a.jsonl.2", tmp_path / "a.jsonl.1", p]
    existing = [c for c in chain if c.exists()]
    ok, msg = verify_chain(existing[-2:])
    assert ok, msg
    assert rec["seq"] > 200


def test_audit_memory_only_ring():
    a = AuditLog(None, ring=5)
    for i in range(10):
        a.event("K", float(i))
    assert len(a.ring) == 5 and a.ring[-1]["seq"] == 10


# ---------------------------------------------------------------- salud HTTP
async def http(port, method, path, headers=None):
    r, w = await asyncio.open_connection("127.0.0.1", port)
    hdr = "".join(f"{k}: {v}\r\n" for k, v in (headers or {}).items())
    w.write(f"{method} {path} HTTP/1.1\r\nHost: x\r\n{hdr}\r\n".encode())
    await w.drain()
    data = await asyncio.wait_for(r.read(), 3.0)
    w.close()
    head, _, body = data.partition(b"\r\n\r\n")
    return int(head.split()[1]), body.decode()


@pytest.mark.e2e
async def test_health_endpoints_and_reset():
    hh = await Harness().start()
    hs = HealthServer(hh.node, "127.0.0.1", 0, reset_token=None)
    port = await hs.start()
    try:
        assert (await http(port, "GET", "/health"))[0] == 200          # arrancando (INIT/STARTING)
        await hh.cycle(5)
        code, body = await http(port, "GET", "/ready"); assert code == 200 and body.strip() == "RUNNING"
        code, body = await http(port, "GET", "/status")
        st = json.loads(body)
        assert code == 200 and st["state"] == "RUNNING" and st["profile"] == "open_bess_edge_reference"
        code, body = await http(port, "GET", "/metrics")
        assert code == 200 and "obe_cycles_total" in body and 'obe_node_state{state="RUNNING"} 1' in body
        assert (await http(port, "GET", "/nada"))[0] == 404
        assert (await http(port, "POST", "/health"))[0] == 404
        # disparo -> readiness 503 y reset condicionado
        hh.env.plant.overrides["cell_t_max_c"] = 60.0
        await hh.cycle()
        assert (await http(port, "GET", "/ready"))[0] == 503
        code, body = await http(port, "POST", "/reset")
        assert code == 409 and json.loads(body)["ok"] is False
        hh.env.plant.overrides["cell_t_max_c"] = 30.0
        await hh.cycle()
        code, body = await http(port, "POST", "/reset")
        assert code == 200 and json.loads(body)["ok"] is True
        # el lazo se detiene => liveness 503
        hh.clock.advance(10.0)
        assert (await http(port, "GET", "/health"))[0] == 503
    finally:
        await hs.stop()
        await hh.stop()


@pytest.mark.e2e
async def test_reset_requires_token_and_remote_bind_is_refused_without_token():
    hh = await Harness().start()
    hs = HealthServer(hh.node, "127.0.0.1", 0, reset_token="s3cret-token")
    port = await hs.start()
    hs2 = HealthServer(hh.node, "0.0.0.0", 0, reset_token=None)     # noqa: S104 - prueba del rechazo
    port2 = await hs2.start()
    try:
        assert (await http(port, "POST", "/reset"))[0] == 403
        assert (await http(port, "POST", "/reset", {"X-Reset-Token": "wrong"}))[0] == 403
        assert (await http(port, "POST", "/reset", {"X-Reset-Token": "s3cret-token"}))[0] in (200, 409)
        assert (await http(port2, "POST", "/reset"))[0] == 403
    finally:
        await hs.stop(); await hs2.stop(); await hh.stop()


@pytest.mark.e2e
async def test_health_survives_garbage_requests():
    hh = await Harness().start()
    hs = HealthServer(hh.node, "127.0.0.1", 0)
    port = await hs.start()
    try:
        for payload in (b"\x00\x01\x02garbage\r\n\r\n", b"GET\r\n\r\n", b"A" * 20000 + b"\r\n\r\n"):
            r, w = await asyncio.open_connection("127.0.0.1", port)
            w.write(payload); await w.drain()
            try:
                await asyncio.wait_for(r.read(), 3.0)
            except (asyncio.TimeoutError, ConnectionError):
                pass
            w.close()
        assert (await http(port, "GET", "/health"))[0] == 200
    finally:
        await hs.stop(); await hh.stop()


# ---------------------------------------------------------------- CLI
def test_cli_version_profile_info_check_config_and_errors(capsys, tmp_path):
    assert main(["version"]) == 0 and "3.0.0" in capsys.readouterr().out
    assert main(["profile-info"]) == 0 and "open_bess_edge_reference" in capsys.readouterr().out
    assert main(["profile-info", "huawei_sun2000"]) == 0
    info = json.loads(capsys.readouterr().out)
    assert info["mode"] == "monitor-only" and info["verification"] == "unverified"
    assert main(["profile-info", "open_bess_edge_reference"]) == 0 and '"control"' in capsys.readouterr().out
    assert main(["check-config", str(ROOT / "config" / "edge_config.yaml")]) == 0
    assert "Configuración válida" in capsys.readouterr().out
    bad = tmp_path / "bad.yaml"; bad.write_text("plant: {p_nominal_kw: -1}\n")
    assert main(["check-config", str(bad)]) == 2 and "ERROR" in capsys.readouterr().err
    assert main(["profile-info", "no_existe"]) == 2
    assert main(["run", "--config", str(tmp_path / "nada.yaml")]) == 2


def test_cli_verify_audit(tmp_path, capsys):
    p = tmp_path / "a.jsonl"
    a = AuditLog(p); a.event("X", 1.0); a.event("Y", 2.0); a.close()
    assert main(["verify-audit", str(p)]) == 0 and "OK" in capsys.readouterr().out
    p.write_text(p.read_text().replace('"X"', '"Z"'))
    assert main(["verify-audit", str(p)]) == 2 and "FALLO" in capsys.readouterr().out


@pytest.mark.slow
def test_cli_simulate_end_to_end_subprocess():
    out = subprocess.run([sys.executable, "-m", "open_bess_edge", "simulate", "--duration", "10"], capture_output=True,
                         text=True, timeout=60, cwd=ROOT, env={"PYTHONPATH": str(ROOT / "src"), "PATH": "/usr/bin:/bin"})
    assert out.returncode == 0, out.stderr
    assert "FFR_CONTINGENCY" in out.stdout and "213.3" in out.stdout and "overruns=0" in out.stdout
