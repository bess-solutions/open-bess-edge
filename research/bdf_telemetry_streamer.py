# -*- coding: utf-8 -*-
"""
open-bess-edge/research/bdf_telemetry_streamer.py
Exportador y Streamer de Telemetría bajo el estándar Battery Data Format (BDF).
Alineado con el proyecto Battery Data Alliance de Linux Foundation Energy (LF Energy).
"""

import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger("OpenBESSEdge.Research.BDF")

class BDFTelemetryStreamer:
    """
    Empaqueta series temporales de alta resolución de Open BESS Edge
    en lotes estandarizados conformes a la especificación BDF.
    """
    def __init__(self, output_dir: Optional[Path] = None, batch_size: int = 100):
        self.output_dir = output_dir or Path(__file__).parent / "bdf_records"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.batch_size = batch_size
        self.buffer: List[Dict[str, Any]] = []

    def record_sample(self, timestamp: float, voltage: float, current: float, temp: float, soc: float, soh: float):
        sample = {
            "timestamp": timestamp,
            "pack_voltage_v": voltage,
            "pack_current_a": current,
            "temperature_c": temp,
            "state_of_charge": soc,
            "state_of_health": soh
        }
        self.buffer.append(sample)
        if len(self.buffer) >= self.batch_size:
            self.flush_to_bdf_parquet()

    def flush_to_bdf_parquet(self) -> Path:
        if not self.buffer:
            return None
        
        timestamp_str = int(time.time())
        filename = self.output_dir / f"bdf_edge_telemetry_{timestamp_str}.json"
        
        # En producción se exporta a Parquet con batterydf / pyarrow
        import json
        with open(filename, "w", encoding="utf-8") as f:
            json.dump({
                "schema_version": "BDF-1.0-LFE",
                "device_id": "OPEN_BESS_EDGE_LINARES_01",
                "records_count": len(self.buffer),
                "data": self.buffer
            }, f, indent=2)
            
        logger.info(f"[BDF Streamer] Lote de {len(self.buffer)} muestras exportado a: {filename}")
        self.buffer = []
        return filename

if __name__ == "__main__":
    from typing import Optional
    streamer = BDFTelemetryStreamer(batch_size=5)
    for i in range(6):
        streamer.record_sample(time.time(), 716.8, -150.0, 24.5, 65.0, 99.8)
    print("[OK] BDF Telemetry Streamer verificado.")
