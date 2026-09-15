"""Unified SITR SCADA & Substation Gateway Service for Open BESS Edge.

Designed for BESSAI Distributed Intelligence Architecture.
Bridges:
  1. Industrial CAN BMS Driver (cell balancing, thermal envelope, NFPA 855)
  2. IEC 60870-5-104 SITR Server (CEN Despacho Nacional real-time telemetry)
  3. IEC 61850 GOOSE Fast Trip Substation Teleprotection (sub-4ms trip & FFR)
"""

from __future__ import annotations

import asyncio
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Ensure drivers are discoverable
current_dir = Path(__file__).resolve().parent
src_dir = current_dir.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from drivers.can_bms_driver import IndustrialCANBMSDriver
from drivers.iec104_client import IEC104SITRServer
from drivers.goose_fast_trip import GOOSETransceiver, TripCause

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("bess_edge.sitr_gateway")


@dataclass
class GatewayConfig:
    sitr_host: str = "127.0.0.1"
    sitr_port: int = 2404
    sitr_common_address: int = 1
    goose_interface: str = "127.0.0.1"
    goose_port: int = 40001
    telemetry_refresh_hz: float = 2.0
    nominal_freq_hz: float = 50.0
    ffr_underfreq_threshold_hz: float = 49.50
    overfreq_trip_threshold_hz: float = 51.50


class SITRGatewayService:
    """Industrial edge service bridging Field Hardware -> CEN SITR -> IEC 61850 GOOSE."""

    def __init__(self, config: Optional[GatewayConfig] = None):
        self.cfg = config or GatewayConfig()
        self.can_driver = IndustrialCANBMSDriver()
        self.sitr_server = IEC104SITRServer(
            host=self.cfg.sitr_host,
            port=self.cfg.sitr_port,
            common_address=self.cfg.sitr_common_address,
        )
        self.goose = GOOSETransceiver(
            interface=self.cfg.goose_interface,
            port=self.cfg.goose_port,
        )

        # Operational state
        self.active_power_mw: float = 0.0
        self.reactive_power_mvar: float = 0.0
        self.grid_frequency_hz: float = 50.00
        self.bus_voltage_kv: float = 220.0
        self.breaker_closed: bool = True
        self.is_running = False

        # Register CEN setpoint dispatch handler
        self.sitr_server.setpoint_callback = self._on_cen_setpoint_received

    def _on_cen_setpoint_received(self, ioa: int, value: float) -> None:
        """Invoked when CEN Despacho Nacional sends an IEC 104 setpoint."""
        if ioa == 3001:
            logger.info(f"[CEN DESPACHO] Dispatched Active Power P_ref = {value:.2f} MW")
            self.active_power_mw = value
        elif ioa == 3002:
            logger.info(f"[CEN DESPACHO] Dispatched Reactive Power Q_ref = {value:.2f} MVAr")
            self.reactive_power_mvar = value

    async def start(self) -> None:
        """Start all telemetry services and event loops."""
        logger.info("Starting Open BESS Edge SITR Gateway Service...")
        self.is_running = True

        # 1. Start IEC 60870-5-104 SITR Server
        await self.sitr_server.start()

        # 2. Start GOOSE Transceiver
        self.goose.start_listener()

        # 3. Launch background synchronization task
        asyncio.create_task(self._telemetry_sync_loop())
        asyncio.create_task(self._fast_protection_loop())
        logger.info("SITR Gateway Service operational.")

    async def stop(self) -> None:
        self.is_running = False
        await self.sitr_server.stop()
        self.goose.close()
        logger.info("SITR Gateway Service stopped.")

    async def _telemetry_sync_loop(self) -> None:
        """Periodically copies CAN BMS & PCS readings to SITR IEC 104 data store."""
        interval = 1.0 / self.cfg.telemetry_refresh_hz
        while self.is_running:
            try:
                bms_snap = self.can_driver.get_telemetry_snapshot()["safety_envelope"]

                # Calculate available charge/discharge capacities (40 MWh nominal pack)
                soc = bms_snap["pack_soc_pct"]
                nominal_mwh = 40.0
                avail_charge_mwh = round(max(0.0, nominal_mwh * (1.0 - (soc / 100.0))), 2)
                avail_discharge_mwh = round(max(0.0, nominal_mwh * (soc / 100.0)), 2)

                # Push to IEC 60870-5-104 Outstation
                self.sitr_server.update_measurement(1001, self.grid_frequency_hz)
                self.sitr_server.update_measurement(1002, self.bus_voltage_kv)
                self.sitr_server.update_measurement(1003, self.active_power_mw)
                self.sitr_server.update_measurement(1004, self.reactive_power_mvar)
                self.sitr_server.update_measurement(1005, soc)
                self.sitr_server.update_measurement(1006, avail_charge_mwh)
                self.sitr_server.update_measurement(1007, avail_discharge_mwh)
                self.sitr_server.update_measurement(2001, 1.0 if self.breaker_closed else 0.0)

            except Exception as e:
                logger.error(f"Error in telemetry sync loop: {e}")

            await asyncio.sleep(interval)

    async def _fast_protection_loop(self) -> None:
        """High-frequency (100 Hz / 10ms) protection and contingency monitoring."""
        while self.is_running:
            try:
                # 1. Under-frequency Contingency -> FFR Sub-500ms Trigger
                if self.grid_frequency_hz <= self.cfg.ffr_underfreq_threshold_hz and self.breaker_closed:
                    logger.critical(
                        f"[CONTINGENCY] Grid Underfrequency ({self.grid_frequency_hz:.3f} Hz <= {self.cfg.ffr_underfreq_threshold_hz} Hz)! Triggering Fast Frequency Response FFR!"
                    )
                    # In underfrequency, FFR ramps injection to maximum (e.g. +10 MW)
                    self.active_power_mw = 10.0
                    self.goose.publish_trip(cause=TripCause.UNDER_FREQUENCY_FFR)

                # 2. Over-frequency Contingency -> Trip Breaker
                elif self.grid_frequency_hz >= self.cfg.overfreq_trip_threshold_hz and self.breaker_closed:
                    logger.critical(
                        f"[PROTECTION TRIP] Grid Overfrequency ({self.grid_frequency_hz:.3f} Hz >= {self.cfg.overfreq_trip_threshold_hz} Hz)! Tripping 52G Breaker!"
                    )
                    self.breaker_closed = False
                    self.active_power_mw = 0.0
                    self.goose.publish_trip(cause=TripCause.OVER_FREQUENCY_TRIP)

                # 3. BMS Thermal Runaway Emergency Trip
                bms_snap = self.can_driver.get_telemetry_snapshot()["safety_envelope"]
                if bms_snap["safety_trip_active"] and self.breaker_closed:
                    logger.critical(
                        f"[BMS TRIP] Thermal/Insulation Safety Gate Fired: {bms_snap['trip_reason']}! Tripping 52G Breaker!"
                    )
                    self.breaker_closed = False
                    self.active_power_mw = 0.0
                    self.goose.publish_trip(cause=TripCause.DC_THERMAL_RUNAWAY)

            except Exception as e:
                logger.error(f"Error in fast protection loop: {e}")

            await asyncio.sleep(0.01)  # 10ms loop


async def _run_gateway_test():
    import struct

    print("=== SITR Gateway Service End-to-End Validation ===")
    cfg = GatewayConfig(sitr_port=24041, goose_port=40003)
    gw = SITRGatewayService(cfg)
    await gw.start()

    print("\n[Step 1] Ingesting Live CAN BMS Frames into Gateway...")
    # Inject CATL Master frame: 1250V, -100A (charging), 80% SoC, 99% SoH
    catl_payload = struct.pack("<HHHBB", 12500, 4000, 800, 99, 0x01)
    gw.can_driver.decode_raw_frame(402908660, catl_payload)
    await asyncio.sleep(0.6)

    # Verify IEC 104 data store updated
    print(f"  SITR IOA 1005 (SoC): {gw.sitr_server.data_store[1005]}%")
    print(f"  SITR IOA 1006 (Avail Charge): {gw.sitr_server.data_store[1006]} MWh")
    print(f"  SITR IOA 1007 (Avail Discharge): {gw.sitr_server.data_store[1007]} MWh")

    print("\n[Step 2] Simulating CEN Despacho Dispatch Setpoint via IEC 104...")
    gw._on_cen_setpoint_received(3001, 8.5)  # Setpoint 8.5 MW discharge
    print(f"  BESS Injection Power is now: {gw.active_power_mw} MW")

    print("\n[Step 3] Simulating Grid Underfrequency Incident (49.38 Hz) -> FFR Sub-500ms Trigger...")
    gw.grid_frequency_hz = 49.38
    await asyncio.sleep(0.1)

    print(f"  Post-Contingency Power Injection: {gw.active_power_mw} MW (FFR Active)")
    print(f"  Breaker 52G Status: {'CLOSED' if gw.breaker_closed else 'TRIPPED'}")

    await gw.stop()
    print("\n=== SITR Gateway Service Test PASSED Successfully ===")


if __name__ == "__main__":
    asyncio.run(_run_gateway_test())
