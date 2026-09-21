"""Registro de auditoría append-only con cadena de hash (evidencia de integridad).

Cada línea JSON incluye ``seq``, ``prev`` (hash del registro anterior) y ``hash``
(SHA-256 del contenido canónico + ``prev``). ``verify_chain`` detecta cualquier
modificación, borrado o reordenamiento de registros. Es *tamper-evident*, no
*tamper-proof*: un atacante con acceso de escritura puede reescribir toda la
cadena; para no repudio se requiere anclar el hash en un sistema externo.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections import deque
from pathlib import Path
from typing import Any, Deque, Iterable, Optional

GENESIS = "0" * 64


def _digest(body: dict[str, Any], prev: str) -> str:
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256((prev + canon).encode("utf-8")).hexdigest()


class AuditLog:
    def __init__(self, path: Optional[Path], max_bytes: int = 50_000_000, backups: int = 5, ring: int = 1000) -> None:
        self.path = Path(path) if path else None
        self.max_bytes, self.backups = max_bytes, backups
        self.ring: Deque[dict[str, Any]] = deque(maxlen=ring)
        self._seq = 0
        self._prev = GENESIS
        self._fh = None
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._resume()
            self._fh = open(self.path, "a", encoding="utf-8", buffering=1)

    def _resume(self) -> None:
        assert self.path is not None  # nosec B101
        if not self.path.exists() or self.path.stat().st_size == 0:
            return
        last = None
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    last = line
        if last:
            rec = json.loads(last)
            self._seq, self._prev = int(rec["seq"]), rec["hash"]

    def event(self, kind: str, wall: float, **data: Any) -> dict[str, Any]:
        self._seq += 1
        body = {"seq": self._seq, "t": round(wall, 6), "kind": kind, "data": data}
        h = _digest(body, self._prev)
        rec = {**body, "prev": self._prev, "hash": h}
        self._prev = h
        self.ring.append(rec)
        if self._fh is not None:
            self._fh.write(json.dumps(rec, sort_keys=True, ensure_ascii=False) + "\n")
            self._fh.flush()
            if self._fh.tell() >= self.max_bytes:
                self._rotate()
        return rec

    def _rotate(self) -> None:
        assert self.path is not None and self._fh is not None  # nosec B101
        self._fh.close()
        if self.backups > 0:
            for i in range(self.backups - 1, 0, -1):
                src = self.path.with_suffix(self.path.suffix + f".{i}")
                if src.exists():
                    os.replace(src, self.path.with_suffix(self.path.suffix + f".{i + 1}"))
            os.replace(self.path, self.path.with_suffix(self.path.suffix + ".1"))
        else:
            self.path.unlink()
        self._fh = open(self.path, "a", encoding="utf-8", buffering=1)

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None


def verify_chain(paths: Iterable[Path | str]) -> tuple[bool, str]:
    """Verifica una o más piezas de la cadena (en orden cronológico)."""
    prev: Optional[str] = None
    seq: Optional[int] = None
    n = 0
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            for ln, line in enumerate(fh, 1):
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                    body = {k: rec[k] for k in ("seq", "t", "kind", "data")}
                    claimed_prev, claimed_hash = rec["prev"], rec["hash"]
                except (ValueError, KeyError) as exc:
                    return False, f"{p}:{ln}: registro ilegible ({exc})"
                if prev is not None and claimed_prev != prev:
                    return False, f"{p}:{ln}: cadena rota (prev no coincide)"
                if seq is not None and rec["seq"] != seq + 1:
                    return False, f"{p}:{ln}: secuencia discontinua ({seq} -> {rec['seq']})"
                if _digest(body, claimed_prev) != claimed_hash:
                    return False, f"{p}:{ln}: hash inválido (registro alterado)"
                prev, seq, n = claimed_hash, rec["seq"], n + 1
    return True, f"{n} registros verificados"
