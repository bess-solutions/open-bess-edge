"""Servidor HTTP mínimo (stdlib) para salud, estado, métricas y reset de disparos.

Endpoints: ``GET /health`` (liveness: el lazo sigue ciclando), ``GET /ready``
(readiness: estado operativo), ``GET /status`` (JSON), ``GET /metrics``
(Prometheus) y ``POST /reset`` (libera disparos enclavados si están despejados).

Seguridad: por defecto escucha en 127.0.0.1. ``POST /reset`` exige el token
configurado (cabecera ``X-Reset-Token``); sin token sólo se acepta si el servidor
está ligado a loopback. Límites duros de tamaño y tiempo por petición.
"""

from __future__ import annotations

import asyncio
import contextlib
import hmac
import ipaddress
import json
import logging
from typing import Optional

from ..models import NodeState
from .node import EdgeNode

log = logging.getLogger("open_bess_edge.health")

_READY = {NodeState.RUNNING, NodeState.DEGRADED, NodeState.MONITOR_ONLY}


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class HealthServer:
    def __init__(self, node: EdgeNode, host: str = "127.0.0.1", port: int = 8080, reset_token: Optional[str] = None):
        self.node, self.host, self.port, self.token = node, host, port, reset_token
        self._server: Optional[asyncio.AbstractServer] = None

    async def start(self) -> int:
        self._server = await asyncio.start_server(self._handle, self.host, self.port)
        self.port = self._server.sockets[0].getsockname()[1]
        return self.port

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    # -- lógica -------------------------------------------------------------
    def alive(self) -> bool:
        n = self.node
        if n.last_cycle_mono is None:
            return n.state in (NodeState.INIT, NodeState.STARTING)
        limit = max(5 * n.cfg.runtime.cycle_ms / 1000.0, 2.0)
        return (n.clock.mono() - n.last_cycle_mono) <= limit

    def status(self) -> dict:
        n, r = self.node, self.node.last_result
        return {
            "device_id": n.cfg.node.device_id, "state": n.state.value, "alive": self.alive(),
            "control_enabled": n.control_enabled, "profile": n.plant.profile.name,
            "profile_verification": n.plant.profile.verification_level,
            "connected": n.plant.connected, "latched_trips": list(n.safety.latched_codes),
            "last": None if r is None else {
                "status": r.status, "f_hz": r.f_hz, "v_v": r.v_v, "p_measured_kw": r.p_measured_kw,
                "p_setpoint_kw": r.p_setpoint_kw, "q_setpoint_kvar": r.q_setpoint_kvar,
                "ffr": r.ffr_status, "safety": r.safety_status, "faults": list(r.faults),
                "latency_ms": round(r.latency_ms, 3)},
        }

    def metrics_text(self) -> str:
        n, m = self.node, self.node.metrics
        r = n.last_result
        lines = []

        def g(name: str, value: float, help_: str, typ: str = "gauge") -> None:
            lines.extend([f"# HELP {name} {help_}", f"# TYPE {name} {typ}", f"{name} {value}"])

        for st in NodeState:
            lines.append(f'obe_node_state{{state="{st.value}"}} {1 if n.state is st else 0}')
        g("obe_cycles_total", m.cycles, "Ciclos de control ejecutados", "counter")
        g("obe_cycle_overruns_total", m.overruns, "Ciclos que excedieron el período", "counter")
        g("obe_comm_errors_total", m.comm_errors, "Ciclos sin telemetría", "counter")
        g("obe_write_failures_total", m.write_failures, "Escrituras de consigna fallidas", "counter")
        g("obe_verify_mismatches_total", m.verify_mismatches, "Verificaciones de escritura fallidas", "counter")
        g("obe_safety_trips_total", m.trips, "Disparos de seguridad", "counter")
        g("obe_safe_state_entries_total", m.safe_state_entries, "Entradas a SAFE_STATE", "counter")
        g("obe_internal_errors_total", m.internal_errors, "Excepciones internas en el ciclo", "counter")
        g("obe_ffr_budget_exceeded_total", m.ffr_budget_exceeded, "Contingencias que excedieron el presupuesto de latencia", "counter")
        g("obe_latency_ms_last", round(m.latency_ms_last, 4), "Latencia muestra->escritura (último ciclo)")
        g("obe_latency_ms_p99", round(m.percentile(0.99), 4), "Latencia muestra->escritura p99")
        g("obe_latency_ms_max", round(m.latency_ms_max, 4), "Latencia muestra->escritura máxima")
        if r is not None:
            g("obe_p_setpoint_kw", r.p_setpoint_kw, "Consigna P aplicada (kW)")
            g("obe_q_setpoint_kvar", r.q_setpoint_kvar, "Consigna Q aplicada (kvar)")
            if r.f_hz is not None:
                g("obe_frequency_hz", r.f_hz, "Frecuencia medida")
        return "\n".join(lines) + "\n"

    # -- HTTP ---------------------------------------------------------------
    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            try:
                head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=5.0)
            except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, asyncio.TimeoutError):
                return
            if len(head) > 8192:
                return await self._send(writer, 431, "text/plain", "cabeceras demasiado grandes")
            lines = head.decode("latin-1").split("\r\n")
            try:
                method, path, _ = lines[0].split(" ", 2)
            except ValueError:
                return await self._send(writer, 400, "text/plain", "petición inválida")
            headers = {}
            for ln in lines[1:]:
                if ":" in ln:
                    k, v = ln.split(":", 1)
                    headers[k.strip().lower()] = v.strip()
            path = path.split("?", 1)[0]
            if method == "GET" and path == "/health":
                ok = self.alive()
                return await self._send(writer, 200 if ok else 503, "text/plain", "ok\n" if ok else "lazo detenido\n")
            if method == "GET" and path == "/ready":
                ok = self.alive() and self.node.state in _READY
                return await self._send(writer, 200 if ok else 503, "text/plain", f"{self.node.state.value}\n")
            if method == "GET" and path == "/status":
                return await self._send(writer, 200, "application/json", json.dumps(self.status()))
            if method == "GET" and path == "/metrics":
                return await self._send(writer, 200, "text/plain; version=0.0.4", self.metrics_text())
            if method == "POST" and path == "/reset":
                if self.token is not None:
                    if not hmac.compare_digest(headers.get("x-reset-token", ""), self.token):
                        return await self._send(writer, 403, "text/plain", "token inválido\n")
                elif not _is_loopback(self.host):
                    return await self._send(writer, 403, "text/plain", "reset remoto requiere token\n")
                ok, msg = self.node.request_reset()
                return await self._send(writer, 200 if ok else 409, "application/json", json.dumps({"ok": ok, "detail": msg}))
            return await self._send(writer, 404, "text/plain", "no encontrado\n")
        except (ConnectionError, OSError):
            pass
        finally:
            with contextlib.suppress(Exception):
                writer.close()

    @staticmethod
    async def _send(writer: asyncio.StreamWriter, code: int, ctype: str, body: str) -> None:
        reasons = {200: "OK", 400: "Bad Request", 403: "Forbidden", 404: "Not Found", 409: "Conflict",
                   431: "Request Header Fields Too Large", 503: "Service Unavailable"}
        data = body.encode("utf-8")
        writer.write(f"HTTP/1.1 {code} {reasons.get(code, 'OK')}\r\nContent-Type: {ctype}; charset=utf-8\r\n"
                     f"Content-Length: {len(data)}\r\nConnection: close\r\n\r\n".encode() + data)
        await writer.drain()
