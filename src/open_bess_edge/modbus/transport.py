"""Transporte Modbus TCP sobre pymodbus con capa de compatibilidad de versiones.

* pymodbus < 3.10 usa el kwarg ``slave=``; >= 3.10 usa ``device_id=``. Se detecta
  por introspección (una sola vez), no por comparación de versión.
* Toda operación está acotada por ``asyncio.wait_for`` (latencia máxima
  determinista, independiente de los reintentos internos de pymodbus).
* Ante cualquier error de comunicación el cliente se cierra: la siguiente
  operación reconecta con un socket limpio (evita respuestas desalineadas tras un
  timeout).
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
from typing import Any, Optional, Protocol, Sequence

from ..errors import PlantCommError

try:  # pragma: no cover - dependiente de la versión instalada
    from pymodbus.client import AsyncModbusTcpClient
    from pymodbus.exceptions import ModbusException
except ImportError as exc:  # pragma: no cover
    raise ImportError("Open BESS Edge requiere pymodbus>=3.9.2,<4") from exc


def _unit_kwarg() -> str:
    params = inspect.signature(AsyncModbusTcpClient.read_holding_registers).parameters
    if "device_id" in params:
        return "device_id"
    if "slave" in params:
        return "slave"
    raise RuntimeError("versión de pymodbus no soportada: sin parámetro de unidad conocido")


UNIT_KWARG = _unit_kwarg()


def _client_kwargs(timeout_s: float) -> dict[str, Any]:
    params = inspect.signature(AsyncModbusTcpClient.__init__).parameters
    kw: dict[str, Any] = {"timeout": timeout_s}
    if "retries" in params or "kwargs" in params:
        kw["retries"] = 0
    if "reconnect_delay" in params or "kwargs" in params:
        kw["reconnect_delay"] = 0          # la reconexión la gobierna el driver
    return kw


class ModbusTransport(Protocol):
    @property
    def connected(self) -> bool: ...
    async def connect(self) -> bool: ...
    async def close(self) -> None: ...
    async def read(self, function: str, address: int, count: int, unit: int) -> list[int]: ...
    async def write(self, address: int, values: Sequence[int], unit: int) -> None: ...


class PyModbusTransport:
    def __init__(self, host: str, port: int, timeout_s: float) -> None:
        self.host, self.port, self.timeout_s = host, port, timeout_s
        self._outer_s = timeout_s * 1.5 + 0.1     # red de seguridad externa al timeout propio de pymodbus
        self._client: Optional[AsyncModbusTcpClient] = None
        self._lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        c = self._client
        return bool(c is not None and c.connected)

    async def connect(self) -> bool:
        await self.close()
        client = AsyncModbusTcpClient(self.host, port=self.port, **_client_kwargs(self.timeout_s))
        try:
            await asyncio.wait_for(client.connect(), timeout=self._outer_s)
        except (asyncio.TimeoutError, OSError, ModbusException) as exc:
            _safe_close(client)
            raise PlantCommError(f"conexión Modbus a {self.host}:{self.port} fallida: {exc!r}") from exc
        if not client.connected:
            _safe_close(client)
            raise PlantCommError(f"conexión Modbus a {self.host}:{self.port} no establecida")
        self._client = client
        return True

    async def close(self) -> None:
        c, self._client = self._client, None
        if c is not None:
            _safe_close(c)

    async def _call(self, fn_name: str, *args: Any, unit: int, **kw: Any) -> Any:
        c = self._client
        if c is None or not c.connected:
            raise PlantCommError("sin conexión Modbus")
        fn = getattr(c, fn_name)
        async with self._lock:
            try:
                res = await asyncio.wait_for(fn(*args, **{UNIT_KWARG: unit}, **kw), timeout=self._outer_s)
            except asyncio.TimeoutError as exc:
                await self.close()
                raise PlantCommError(f"timeout Modbus en {fn_name} (>{self.timeout_s}s)") from exc
            except (OSError, ModbusException) as exc:
                await self.close()
                raise PlantCommError(f"error Modbus en {fn_name}: {exc!r}") from exc
            except AttributeError as exc:
                # En pymodbus < 3.8 o ante desconexión asíncrona concurrente, pymodbus puede
                # desasociar el socket en transport_send y disparar: 'NoneType' object has no attribute 'write'.
                if "NoneType" in str(exc) and "write" in str(exc):
                    await self.close()
                    raise PlantCommError(f"error de transporte Modbus en {fn_name} (socket desconectado): {exc!r}") from exc
                raise
        if res is None:
            await self.close()
            raise PlantCommError(f"respuesta vacía en {fn_name}")
        if res.isError():
            # Una excepción Modbus válida no implica enlace roto; se propaga sin cerrar.
            code = getattr(res, "exception_code", None)
            raise PlantCommError(f"excepción Modbus en {fn_name}: código={code} ({res})")
        return res

    async def read(self, function: str, address: int, count: int, unit: int) -> list[int]:
        name = "read_holding_registers" if function == "holding" else "read_input_registers"
        res = await self._call(name, address, count=count, unit=unit)
        regs = list(getattr(res, "registers", []) or [])
        if len(regs) != count:
            await self.close()
            raise PlantCommError(f"respuesta con {len(regs)} registros, se esperaban {count}")
        return regs

    async def write(self, address: int, values: Sequence[int], unit: int) -> None:
        vals = [int(v) for v in values]
        if len(vals) == 1:
            await self._call("write_register", address, vals[0], unit=unit)
        else:
            await self._call("write_registers", address, vals, unit=unit)


def _safe_close(client: Any) -> None:
    with contextlib.suppress(Exception):     # cierre best-effort
        client.close()
