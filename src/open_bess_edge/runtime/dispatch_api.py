"""API HTTP de despacho (programa base con expiración) para un EMS local.

``POST /api/v1/dispatch`` con ``Authorization: Bearer <token>`` y cuerpo JSON
``{"p_base_kw": <número>, "ttl_s": <0 < ttl <= 3600>}``.

Garantías:
* El token nunca está en el YAML: archivo de secreto o variable de entorno, >= 32 caracteres.
* Comparación en tiempo constante; tope de cuerpo; límite de tasa; JSON estricto (sin NaN/inf/tipos ajenos).
* Sólo loopback: TLS **no está implementado**, por lo que un bind no-loopback se rechaza al construir.
* La consigna se recorta a la capacidad al aceptarla; en cada ciclo el programa pasa por la envolvente de
  seguridad y por las restricciones de instalación (el resultado por ciclo queda en los eventos SETPOINT).
* Cada petición (aceptada, recortada o rechazada) queda en la auditoría con origen, valor y veredicto.
"""

from __future__ import annotations

import asyncio
import contextlib
import hmac
import json
import math
import os
from pathlib import Path
from typing import Any, Optional

from ..config import DispatchApiConfig
from ..errors import ConfigError
from .health import _is_loopback
from .node import EdgeNode

MIN_TOKEN_LEN = 32
MAX_TTL_S = 3600.0


def load_api_token(cfg: DispatchApiConfig, environ: Optional[dict[str, str]] = None) -> str:
    env = os.environ if environ is None else environ
    token: Optional[str] = None
    if cfg.token_file is not None:
        try:
            token = Path(cfg.token_file).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ConfigError(f"no se pudo leer dispatch_api.token_file: {exc}") from exc
    elif env.get(cfg.token_env):
        token = env[cfg.token_env].strip()
    if not token:
        raise ConfigError(f"dispatch_api habilitada sin token ({cfg.token_env} o token_file)")
    if len(token) < MIN_TOKEN_LEN:
        raise ConfigError(f"el token de la API debe tener al menos {MIN_TOKEN_LEN} caracteres")
    return token


def _strict_json(body: bytes) -> Any:
    def _reject(c: str) -> Any:
        raise ValueError(f"constante no permitida: {c}")

    return json.loads(body.decode("utf-8"), parse_constant=_reject)


class DispatchApi:
    def __init__(self, node: EdgeNode, host: str, port: int, token: str, *, max_body_bytes: int = 4096,
                 rate_limit_per_s: float = 20.0) -> None:
        if not _is_loopback(host):
            raise ConfigError("dispatch_api: bind no-loopback prohibido (TLS no implementado); use 127.0.0.1 o un proxy TLS")
        if len(token) < MIN_TOKEN_LEN:
            raise ConfigError(f"el token de la API debe tener al menos {MIN_TOKEN_LEN} caracteres")
        self.node, self.host, self.port = node, host, port
        self._token = token.encode()
        self.max_body = max_body_bytes
        self._rate, self._tokens, self._t_refill = rate_limit_per_s, rate_limit_per_s, node.clock.mono()
        self._last_auth_audit = -1e18
        self._server: Optional[asyncio.AbstractServer] = None

    async def start(self) -> int:
        self._server = await asyncio.start_server(self._handle, self.host, self.port)
        self.port = self._server.sockets[0].getsockname()[1]
        return self.port

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    def _allow(self) -> bool:
        now = self.node.clock.mono()
        self._tokens = min(self._rate, self._tokens + (now - self._t_refill) * self._rate)
        self._t_refill = now
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        return False

    def _audit(self, peer: str, verdict: str, **data: Any) -> None:
        self.node.audit.event("DISPATCH_REQUEST", self.node.clock.wall(), peer=peer, verdict=verdict, **data)

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = str((writer.get_extra_info("peername") or ("?",))[0])
        try:
            code, payload = await self._process(reader, peer)
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, asyncio.TimeoutError, ConnectionError, OSError):
            code, payload = 400, {"ok": False, "error": "petición incompleta o inválida"}
        try:
            body = json.dumps(payload).encode()
            reasons = {200: "OK", 400: "Bad Request", 401: "Unauthorized", 404: "Not Found", 413: "Payload Too Large",
                       429: "Too Many Requests", 503: "Service Unavailable"}
            writer.write(f"HTTP/1.1 {code} {reasons.get(code, 'Error')}\r\nContent-Type: application/json\r\n"
                         f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode() + body)
            await writer.drain()
        except (ConnectionError, OSError):
            pass
        finally:
            with contextlib.suppress(Exception):
                writer.close()

    async def _process(self, reader: asyncio.StreamReader, peer: str) -> tuple[int, dict[str, Any]]:
        head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=5.0)
        if len(head) > 8192:
            return 400, {"ok": False, "error": "cabeceras demasiado grandes"}
        lines = head.decode("latin-1").split("\r\n")
        try:
            method, path, _ = lines[0].split(" ", 2)
        except ValueError:
            return 400, {"ok": False, "error": "petición inválida"}
        headers = {k.strip().lower(): v.strip() for k, _, v in (ln.partition(":") for ln in lines[1:]) if k}
        if not self._allow():
            return 429, {"ok": False, "error": "límite de tasa"}
        if path.split("?", 1)[0] != "/api/v1/dispatch" or method != "POST":
            return 404, {"ok": False, "error": "no encontrado"}
        auth = headers.get("authorization", "")
        supplied = auth[7:].encode() if auth.lower().startswith("bearer ") else b""
        if not hmac.compare_digest(supplied, self._token):
            now = self.node.clock.mono()
            if now - self._last_auth_audit >= 1.0:          # evita inundar la auditoría bajo ataque
                self._last_auth_audit = now
                self._audit(peer, "REJECTED", reason="AUTH_FAILURE")
            return 401, {"ok": False, "error": "no autorizado"}
        try:
            length = int(headers.get("content-length", ""))
        except ValueError:
            return 400, {"ok": False, "error": "Content-Length requerido"}
        if length < 0 or length > self.max_body:
            self._audit(peer, "REJECTED", reason="BODY_TOO_LARGE", bytes=length)
            return 413, {"ok": False, "error": "cuerpo demasiado grande"}
        body = await asyncio.wait_for(reader.readexactly(length), timeout=5.0)
        try:
            doc = _strict_json(body)
            if not isinstance(doc, dict) or set(doc) != {"p_base_kw", "ttl_s"}:
                raise ValueError("se esperan exactamente las claves p_base_kw y ttl_s")
            p, ttl = doc["p_base_kw"], doc["ttl_s"]
            for v in (p, ttl):
                if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                    raise ValueError("valores numéricos finitos requeridos")
            if not 0 < ttl <= MAX_TTL_S:
                raise ValueError(f"ttl_s debe estar en (0, {MAX_TTL_S:.0f}]")
        except (ValueError, UnicodeDecodeError) as exc:
            self._audit(peer, "REJECTED", reason=f"INVALID_BODY: {exc}")
            return 400, {"ok": False, "error": f"cuerpo inválido: {exc}"}
        if not self.node.control_enabled:
            self._audit(peer, "REJECTED", reason="MONITOR_ONLY", requested_p_kw=p)
            return 503, {"ok": False, "error": "nodo en modo monitor"}
        applied = self.node.set_dispatch(float(p), float(ttl))
        verdict = "ACCEPTED" if abs(applied - p) < 1e-9 else "CLAMPED"
        self._audit(peer, verdict, requested_p_kw=p, ttl_s=ttl, applied_p_kw=applied)
        return 200, {"ok": True, "verdict": verdict, "applied_p_kw": applied, "ttl_s": ttl}
