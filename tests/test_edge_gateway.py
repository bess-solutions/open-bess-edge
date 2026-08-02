# ruff: noqa: E402
"""
Unit Tests for BESS-OPEN-EDGE v2.18.0 Gateway Modules
=====================================================
Pruebas unitarias para validar el cliente Flower mTLS, la inferencia ONNX local,
las guardas de seguridad física y el registro Modbus de inversores Tier-1.
"""

import os
import sys
import time
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization

# Agregar rutas al path para importar src
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

try:
    from core.fl_coordinator import BESSFlowerClient

    _FLWR_AVAILABLE = True
except ImportError:
    BESSFlowerClient = None
    _FLWR_AVAILABLE = False

from core.hardware_registry import HardwareRegistry
from core.onnx_inference import ONNXInferenceEngine


class TestEdgeGatewayModules(unittest.TestCase):
    def setUp(self):
        self.certs_dir = ROOT / "certs"
        self.certs_dir.mkdir(exist_ok=True)
        self.private_key_path = self.certs_dir / "ed25519_node_test.pem"

        # Iniciar modelo ONNX real
        self.model_path = (
            Path(__file__).resolve().parent.parent.parent / "models" / "rl_arbitrage.onnx"
        )

    def tearDown(self):
        # Limpiar clave de prueba si existe
        if self.private_key_path.exists():
            os.remove(self.private_key_path)
        if self.certs_dir.exists() and not os.listdir(self.certs_dir):
            os.rmdir(self.certs_dir)

    @unittest.skipUnless(_FLWR_AVAILABLE, "flwr no instalado (ver requirements-federated.txt)")
    def test_fl_coordinator_key_generation_and_signatures(self):
        """Valida la generación de llaves Ed25519 y la firma criptográfica de parámetros."""
        client = BESSFlowerClient(node_id="test_node", private_key_path=str(self.private_key_path))
        self.assertTrue(
            self.private_key_path.exists(), "La clave Ed25519 debería haberse generado."
        )

        # Test de firma
        params = client.get_parameters({})
        signature, pub_pem = client._sign_parameters(params)

        # Validar firma usando la clave pública
        public_key = serialization.load_pem_public_key(pub_pem)
        serialized_params = b"".join([p.tobytes() for p in params])

        # Si no arroja excepción, la firma es válida
        try:
            public_key.verify(signature, serialized_params)
            verification = True
        except Exception:
            verification = False

        self.assertTrue(verification, "La firma criptográfica Ed25519 de parámetros falló.")

    @unittest.skipUnless(_FLWR_AVAILABLE, "flwr no instalado (ver requirements-federated.txt)")
    def test_fl_coordinator_fit_and_evaluate_payloads(self):
        """Valida que fit y evaluate agreguen las firmas Ed25519 a las métricas."""
        client = BESSFlowerClient(node_id="test_node", private_key_path=str(self.private_key_path))
        params = client.get_parameters({})

        _, _, fit_metrics = client.fit(params, {})
        self.assertIn("signature_hex", fit_metrics)
        self.assertIn("pub_key_pem", fit_metrics)
        self.assertEqual(fit_metrics["node_id"], "test_node")

        _, _, eval_metrics = client.evaluate(params, {})
        self.assertIn("loss_signature_hex", eval_metrics)
        self.assertIn("pub_key_pem", eval_metrics)
        self.assertEqual(eval_metrics["node_id"], "test_node")

    def test_onnx_inference_engine_loading_and_prediction(self):
        """Valida la carga del modelo ONNX y la inferencia rápida (<5ms)."""
        if not self.model_path.exists():
            self.skipTest(
                f"Modelo ONNX de referencia no encontrado en {self.model_path}. Omitiendo test."
            )

        engine = ONNXInferenceEngine(str(self.model_path))

        start_time = time.perf_counter()
        action = engine.predict_action(
            soc=0.5, solar_radiation=600.0, historical_spread=45.0, price=50.0
        )
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        # Latencia debe ser inferior a 5ms en la CPU
        print(f"[TEST] Latencia de Inferencia ONNX: {latency_ms:.3f} ms")
        self.assertLess(
            latency_ms, 5.0, "La latencia de inferencia ONNX supera los 5ms requeridos."
        )
        self.assertIn(action, [0, 1, 2], "La acción predicha debe ser 0, 1 o 2.")

    def test_onnx_inference_engine_safety_guardrails(self):
        """Valida las guardas de seguridad física (temperatura y SOC) en el borde."""
        if not self.model_path.exists():
            self.skipTest(
                f"Modelo ONNX de referencia no encontrado en {self.model_path}. Omitiendo test."
            )

        engine = ONNXInferenceEngine(str(self.model_path), power_limit_kw=100.0)

        # 1. Emergencia por temperatura >= 45°C (shutdown)
        setpoint, status = engine.get_dispatch_setpoint(
            soc=0.5, temp=46.0, solar_radiation=500.0, historical_spread=30.0, price=50.0
        )
        self.assertEqual(setpoint, 0.0)
        self.assertEqual(status, "EMERGENCY_THERMAL_SHUTDOWN")

        # 2. Derating térmico preventivo a 42°C (potencia reducida al 50%)
        # Forzar una acción de descarga (2) simulando a mano la guarda
        setpoint_normal, _ = engine.validate_and_clamp(action=2, soc=0.5, temp=25.0)
        setpoint_derated, _ = engine.validate_and_clamp(action=2, soc=0.5, temp=41.0)
        self.assertEqual(
            setpoint_derated,
            setpoint_normal * 0.5,
            "El derating térmico debería reducir la potencia al 50%.",
        )

        # 3. Guardas de SOC límite
        # Carga bloqueada si SOC >= 95%
        setpoint_soc_high, status_soc_high = engine.validate_and_clamp(
            action=0, soc=0.96, temp=25.0
        )
        self.assertEqual(setpoint_soc_high, 0.0)
        self.assertEqual(status_soc_high, "SOC_OVERCHARGE_PROTECTION")

        # Descarga bloqueada si SOC <= 5%
        setpoint_soc_low, status_soc_low = engine.validate_and_clamp(action=2, soc=0.04, temp=25.0)
        self.assertEqual(setpoint_soc_low, 0.0)
        self.assertEqual(status_soc_low, "SOC_DEEP_DISCHARGE_PROTECTION")

    def test_hardware_registry_modbus_decoding(self):
        """Prueba la decodificación de registros Modbus TCP para las marcas homologadas Tier-1."""
        # 1. ABB PCS100
        abb_registers = {
            30002: 75,  # 75 kW actuales
            30005: 850,  # SOC 85.0% (escala 0.1)
            30007: 325,  # Temp 32.5°C (escala 0.1)
            30012: 2,  # Operating
            30010: 0,  # Sin alarmas
            30015: 0,  # Anti-isla desactivada
        }
        abb_data = HardwareRegistry.parse_telemetry("ABB", abb_registers)
        self.assertEqual(abb_data["brand"], "ABB PCS100")
        self.assertAlmostEqual(abb_data["soc"], 0.85)
        self.assertAlmostEqual(abb_data["temperature"], 32.5)
        self.assertEqual(abb_data["active_power_kw"], 75.0)
        self.assertTrue(abb_data["is_healthy"])

        # 2. GE Grid Solutions
        ge_registers = {
            30102: 120,  # 120 kW
            30105: 60,  # SOC 60%
            30108: 24,  # Temp 24°C
            30110: 1,  # Running
            30112: 0,
            30115: 0,
        }
        ge_data = HardwareRegistry.parse_telemetry("GE", ge_registers)
        self.assertEqual(ge_data["brand"], "GE Grid Solutions")
        self.assertAlmostEqual(ge_data["soc"], 0.60)
        self.assertEqual(ge_data["temperature"], 24.0)

        # 3. Schneider Conext
        schneider_registers = {
            30202: 40,  # 40 kW
            30205: 90,  # SOC 90%
            30207: 29,  # Temp 29°C
            30208: 1,  # OK
            30210: 0,  # No alarm
            30215: 1,  # Anti-isla detectada (ISLA ACTIVA)
        }
        sch_data = HardwareRegistry.parse_telemetry("SCHNEIDER", schneider_registers)
        self.assertTrue(sch_data["anti_islanding_triggered"])
        self.assertFalse(
            sch_data["is_healthy"],
            "El inyector no debe reportar healthy si hay disparo anti-isla.",
        )

    def test_hardware_registry_write_command_formatting(self):
        """Valida el formateo del comando Modbus para setpoint de potencia."""
        reg, val = HardwareRegistry.format_write_command("ABB", -50.0)
        self.assertEqual(reg, 40001)
        self.assertEqual(val, -50)

        reg, val = HardwareRegistry.format_write_command("GE", 120.5)
        self.assertEqual(reg, 40101)
        self.assertEqual(val, 120)


if __name__ == "__main__":
    unittest.main()
