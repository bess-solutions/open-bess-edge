"""
BESSAI Edge Gateway — ONNX Inference and Safety Guard Engine
============================================================
Carga y ejecuta el modelo de despacho de aprendizaje por refuerzo (DRL)
de tipo PPO/Q-values en formato ONNX en <5ms localmente en el borde.
Aplica guardas de seguridad en tiempo real para proteger la vida útil de la batería
y evitar condiciones operacionales peligrosas según el estándar IEC 62443.
"""

import logging
import os
import time
import numpy as np
import onnxruntime as ort
from typing import Dict, Tuple

# Configurar logs
logger = logging.getLogger("bess.edge.onnx_inference")

class ONNXInferenceEngine:
    """
    Motor de Inferencia local ONNX con componente de Guardas de Seguridad físico.
    """
    def __init__(self, model_path: str, power_limit_kw: float = 100.0):
        self.model_path = model_path
        self.power_limit_kw = power_limit_kw
        self.session = self._init_session()
        
    def _init_session(self) -> ort.InferenceSession:
        """Inicializa la sesión de ONNX Runtime, cargando el modelo en CPU."""
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Modelo ONNX no encontrado en: {self.model_path}")
        try:
            # Configurar opciones de sesión para optimizar latencia en borde (CPU)
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 1
            opts.inter_op_num_threads = 1
            opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            session = ort.InferenceSession(self.model_path, sess_options=opts)
            logger.info(f"Sesión ONNX cargada con éxito desde {self.model_path}")
            return session
        except Exception as e:
            logger.error(f"Error inicializando sesión ONNX: {e}")
            raise e

    def predict_action(self, soc: float, solar_radiation: float, historical_spread: float, price: float) -> int:
        """
        Ejecuta la inferencia ONNX para predecir la acción de despacho.
        Métricas: Latencia < 5ms.
        
        Args:
            soc: Estado de carga de la batería (0.0 a 1.0)
            solar_radiation: Radiación solar en W/m2
            historical_spread: Spread histórico de precios marginales en USD/MWh
            price: Precio spot de la barra en tiempo real en USD/MWh
            
        Returns:
            action: Acción discreta (0 = Cargar, 1 = Hold/Esperar, 2 = Descargar)
        """
        start_time = time.perf_counter()
        
        # El modelo espera un array de forma [batch_size, 4] con dtype float32
        input_data = np.array([[soc, solar_radiation, historical_spread, price]], dtype=np.float32)
        
        input_name = self.session.get_inputs()[0].name
        outputs = self.session.run(None, {input_name: input_data})
        
        # Obtener los Q-values o logits
        q_values = outputs[0]
        action = int(np.argmax(q_values[0]))
        
        latency_ms = (time.perf_counter() - start_time) * 1000.0
        logger.debug(f"Inferencia ONNX ejecutada en {latency_ms:.2f}ms. Acción elegida: {action}")
        return action

    def validate_and_clamp(self, action: int, soc: float, temp: float) -> Tuple[float, str]:
        """
        Valida la acción de inyección/carga propuesta contra las restricciones físicas del sistema.
        Seguridad de Batería de Litio LFP en el borde (IEC 62443 Guardrails).
        
        Returns:
            power_setpoint_kw: Setpoint final de potencia a escribir vía Modbus.
            status: Código de estado del inyector.
        """
        # Mapear acción a potencia propuesta en kW
        if action == 0:
            proposed_power = -1.0 * self.power_limit_kw  # Carga (consumo de red)
        elif action == 2:
            proposed_power = 1.0 * self.power_limit_kw   # Descarga (inyección a red)
        else:
            proposed_power = 0.0                          # Espera
            
        # 1. Guarda Térmica Crítica
        if temp >= 45.0:
            logger.critical(f"⚠️ DISPARO TÉRMICO: Temperatura de celdas ({temp}°C) sobrepasa límite crítico (45°C). Setpoint clamped a 0 kW.")
            return 0.0, "EMERGENCY_THERMAL_SHUTDOWN"
            
        # 2. Desgaste y Derating Térmico Preventivo (Reduce capacidad un 50% entre 40°C y 45°C)
        if temp > 40.0:
            derating_factor = 0.5
            proposed_power *= derating_factor
            logger.warning(f"🌡️ DERATING TÉRMICO ACTIVO: Temperatura de celdas ({temp}°C) > 40°C. Potencia limitada en un { (1 - derating_factor)*100 }%.")
            
        # 3. Protecciones de SOC (Límites químicos 5% - 95%)
        # Protección de sobrecarga (no se puede cargar más si SOC >= 0.95)
        if soc >= 0.95 and proposed_power < 0:
            logger.warning(f"🔋 SOBRECARGA PROTEGIDA: SOC ({soc*100:.1f}%) >= 95%. Bloqueada acción de carga.")
            return 0.0, "SOC_OVERCHARGE_PROTECTION"
            
        # Protección de sobredescarga (no se puede descargar más si SOC <= 0.05)
        if soc <= 0.05 and proposed_power > 0:
            logger.warning(f"🪫 DESCARGA PROFUNDA PROTEGIDA: SOC ({soc*100:.1f}%) <= 5%. Bloqueada acción de inyección.")
            return 0.0, "SOC_DEEP_DISCHARGE_PROTECTION"
            
        return proposed_power, "NORMAL_OPERATION"

    def get_dispatch_setpoint(self, soc: float, temp: float, solar_radiation: float, historical_spread: float, price: float) -> Tuple[float, str]:
        """
        Método unificado de despacho local del edge gateway:
        Inferencia de optimización + Filtro de guardas de seguridad física.
        """
        action = self.predict_action(soc, solar_radiation, historical_spread, price)
        setpoint, status = self.validate_and_clamp(action, soc, temp)
        return setpoint, status

if __name__ == "__main__":
    # Test rápido local con el modelo del repositorio
    # Ruta absoluta
    model_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../models/rl_arbitrage.onnx"))
    if os.path.exists(model_path):
        engine = ONNXInferenceEngine(model_path)
        p, status = engine.get_dispatch_setpoint(soc=0.5, temp=25.0, solar_radiation=800.0, historical_spread=60.0, price=75.0)
        print(f"Setpoint obtenido: {p} kW | Estado: {status}")
    else:
        print("Modelo rl_arbitrage.onnx no disponible para test directo.")
