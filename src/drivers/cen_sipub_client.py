#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
open-bess-edge/src/drivers/cen_sipub_client.py
==============================================================================
Cliente Asíncrono de Telemetría Oficial del Coordinador Eléctrico Nacional (CEN)
==============================================================================
Recuperado mediante ingeniería inversa de bytecode Dalvik (cen.app.coordinador).
Consume directamente la API móvil SIPUB sin intermediarios ni bloqueos de WAF Cloudflare.
Proporciona Costos Marginales (CMg) en tiempo real, demanda del sistema y vertimiento ERNC
para el algoritmo de despacho óptimo en Nodo Linares.
==============================================================================
"""

from __future__ import annotations

import asyncio
import json
import urllib.request
import urllib.parse
from dataclasses import dataclass
from typing import List, Optional
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class MarginalCostReading:
    node_name: str
    order: int
    timestamp: int
    cmg_usd_mwh: float


@dataclass
class SystemDemandReading:
    date: str
    hour: int
    demand_mw: float


class CENSipubClient:
    """Cliente de telemetría de mercado eléctrico SEN Chile para Open BESS Edge."""

    CMG_ONLINE_URL = "https://sipub.api.coordinador.cl/costos-marginales-online-8b/v4/findAll?user_key=028f23746cc6a4dd0648a6feae8a32ad"
    CMG_SCHEDULED_URL = (
        "https://sipub.api.coordinador.cl/mobile/cmg-programados/v4/findAll?user_key=028f23746cc6a4dd0648a6feae8a32ad"
    )
    DEMAND_REAL_URL = "https://sipubv1.api.coordinador.cl/api/v1/recursos/demandasistemareal?user_key=f3cdad2758436a0a2c2c1fec92853de7"
    GENERATION_TECH_URL = "https://sipubv1.api.coordinador.cl/api/v1/recursos/generacion_centrales_tecnologia_horario?user_key=f3cdad2758436a0a2c2c1fec92853de7"

    def __init__(self, timeout_s: float = 10.0):
        self.timeout = timeout_s
        self.headers = {"User-Agent": "CEN-Mobile-Client/4.0 (Android; BESSAI-Edge)", "Accept": "application/json"}

    def _get_json_sync(self, url: str) -> dict:
        if not (
            url.startswith("https://sipub.api.coordinador.cl/") or url.startswith("https://sipubv1.api.coordinador.cl/")
        ):
            raise ValueError(f"URL de destino no permitida para API CEN: {url}")
        req = urllib.request.Request(url, headers=self.headers)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # nosec B310
            if resp.status != 200:
                raise RuntimeError(f"CEN API returned status {resp.status}")
            return json.loads(resp.read().decode("utf-8"))

    async def get_marginal_costs_online(self) -> List[MarginalCostReading]:
        """Obtiene los costos marginales online más recientes para todas las barras del SEN."""
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, self._get_json_sync, self.CMG_ONLINE_URL)

        readings = []
        barras = data.get("barras", [])
        for b in barras:
            nombre = b.get("nombre", "Unknown")
            orden = b.get("orden", 0)
            valores = b.get("valores", [])
            if valores:
                ultimo = valores[-1]
                readings.append(
                    MarginalCostReading(
                        node_name=nombre,
                        order=orden,
                        timestamp=ultimo.get("fecha", 0),
                        cmg_usd_mwh=float(ultimo.get("valor", 0.0)),
                    )
                )
        return readings

    async def get_system_demand_real(self) -> Optional[SystemDemandReading]:
        """Obtiene la demanda real más reciente del Sistema Eléctrico Nacional."""
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, self._get_json_sync, self.DEMAND_REAL_URL)

        records = data.get("data", [])
        if records:
            ultimo = records[-1]
            return SystemDemandReading(
                date=ultimo.get("fecha", ""),
                hour=int(ultimo.get("hora", 0)),
                demand_mw=float(ultimo.get("demanda", 0.0)),
            )
        return None


if __name__ == "__main__":

    async def main():
        client = CENSipubClient()
        print("[*] Consultando costos marginales online del CEN...")
        cmgs = await client.get_marginal_costs_online()
        for c in cmgs:
            print(f"  -> Barra: {c.node_name:<20} | CMg: ${c.cmg_usd_mwh:.2f} USD/MWh")

        print("[*] Consultando demanda real del SEN...")
        dem = await client.get_system_demand_real()
        if dem:
            print(f"  -> Demanda SEN ({dem.date} H{dem.hour:02d}): {dem.demand_mw:.2f} MW")

    asyncio.run(main())
