"""
BESSAI Edge Gateway — Industrial Hardware Registry
==================================================
Define los mapeos de registros Modbus TCP y la lógica de traducción de telemetría
para inversores y sistemas de conversión de potencia (PCS) Tier-1 homologados:
  1. ABB PCS100
  2. GE Grid Solutions
  3. Schneider Conext

Normas de referencia: IEC 61850, IEEE 2030.5
"""

import logging
from typing import Dict, Any, Optional, Tuple

# Configurar logs
logger = logging.getLogger("bess.edge.hardware_registry")

class ModbusProfile:
    """Representa la estructura de registros Modbus para una marca específica."""
    def __init__(self, brand: str, write_power_reg: int, read_power_reg: int,
                 read_soc_reg: int, read_temp_reg: int, read_status_reg: int,
                 read_alarm_reg: int, scale_soc: float = 1.0, scale_temp: float = 1.0,
                 scale_power: float = 1.0, anti_island_reg: Optional[int] = None):
        self.brand = brand
        self.write_power_reg = write_power_reg
        self.read_power_reg = read_power_reg
        self.read_soc_reg = read_soc_reg
        self.read_temp_reg = read_temp_reg
        self.read_status_reg = read_status_reg
        self.read_alarm_reg = read_alarm_reg
        self.scale_soc = scale_soc
        self.scale_temp = scale_temp
        self.scale_power = scale_power
        self.anti_island_reg = anti_island_reg


class HardwareRegistry:
    """
    Registro y decodificador de perfiles Modbus TCP para inversores Tier-1.
    """
    PROFILES = {
        "ABB": ModbusProfile(
            brand="ABB PCS100",
            write_power_reg=40001,  # Setpoint de potencia activa (kW)
            read_power_reg=30002,   # Potencia activa actual (kW)
            read_soc_reg=30005,     # SOC de batería (0-1000, escala 0.1)
            read_temp_reg=30007,    # Temperatura de celda (0-1000, escala 0.1)
            read_status_reg=30012,  # Estado: 0=Offline, 1=Standby, 2=Operating, 3=Fault
            read_alarm_reg=30010,   # Código de alarmas activas
            scale_soc=0.1,          # Traduce 0-1000 a 0-100%
            scale_temp=0.1,         # Traduce a °C
            scale_power=1.0,
            anti_island_reg=30015   # 1 = Isla detectada
        ),
        "GE": ModbusProfile(
            brand="GE Grid Solutions",
            write_power_reg=40101,  # Setpoint de potencia
            read_power_reg=30102,   # Potencia activa leída
            read_soc_reg=30105,     # SOC directo (0-100%)
            read_temp_reg=30108,    # Temperatura directa (°C)
            read_status_reg=30110,  # Estado: 0=Stop, 1=Running, 2=Fault
            read_alarm_reg=30112,   # Alarmas
            scale_soc=1.0,
            scale_temp=1.0,
            scale_power=1.0,
            anti_island_reg=30115
        ),
        "SCHNEIDER": ModbusProfile(
            brand="Schneider Conext",
            write_power_reg=40201,  # Setpoint de potencia
            read_power_reg=30202,   # Potencia actual
            read_soc_reg=30205,     # SOC directo (%)
            read_temp_reg=30207,    # Temperatura (°C)
            read_status_reg=30208,  # Estado
            read_alarm_reg=30210,   # Alarmas
            scale_soc=1.0,
            scale_temp=1.0,
            scale_power=1.0,
            anti_island_reg=30215   # Registro de estado de Grid (Anti-isla)
        )
    }

    @classmethod
    def get_profile(cls, brand: str) -> ModbusProfile:
        """Obtiene el perfil Modbus correspondiente."""
        brand_upper = brand.upper()
        if brand_upper not in cls.PROFILES:
            raise ValueError(f"Marca de hardware no soportada en el registro: {brand}. Homologados: {list(cls.PROFILES.keys())}")
        return cls.PROFILES[brand_upper]

    @classmethod
    def parse_telemetry(cls, brand: str, registers: Dict[int, int]) -> Dict[str, Any]:
        """
        Traduce los registros brutos leídos por Modbus TCP en telemetría física estructurada.
        """
        profile = cls.get_profile(brand)
        
        # Extraer y escalar valores con fallbacks seguros en caso de falta de registro
        raw_soc = registers.get(profile.read_soc_reg, 0)
        soc = float(raw_soc * profile.scale_soc) / 100.0  # Convertir a rango 0.0 - 1.0
        
        raw_temp = registers.get(profile.read_temp_reg, 0)
        temp = float(raw_temp * profile.scale_temp)
        
        raw_power = registers.get(profile.read_power_reg, 0)
        power_kw = float(raw_power * profile.scale_power)
        
        status_code = registers.get(profile.read_status_reg, 0)
        alarm_code = registers.get(profile.read_alarm_reg, 0)
        
        # Verificar Anti-Isla
        isla_activa = False
        if profile.anti_island_reg and profile.anti_island_reg in registers:
            isla_activa = registers[profile.anti_island_reg] == 1

        telemetry = {
            "brand": profile.brand,
            "soc": soc,
            "temperature": temp,
            "active_power_kw": power_kw,
            "status_code": status_code,
            "alarm_code": alarm_code,
            "anti_islanding_triggered": isla_activa,
            "is_healthy": (status_code != 3 and alarm_code == 0 and not isla_activa)
        }
        
        logger.debug(f"[{profile.brand}] Telemetría Modbus decodificada: SOC={soc*100:.1f}%, Temp={temp}°C, Power={power_kw}kW")
        return telemetry

    @classmethod
    def format_write_command(cls, brand: str, power_setpoint_kw: float) -> Tuple[int, int]:
        """
        Formatea el comando de escritura Modbus TCP para establecer la potencia.
        Retorna (registro_destino, valor_a_escribir).
        """
        profile = cls.get_profile(brand)
        # Por seguridad Modbus, usualmente se transmiten enteros con signo de 16-bits
        value = int(power_setpoint_kw / profile.scale_power)
        
        # Clampar al límite de un short con signo (-32768 a 32767)
        value = max(-32768, min(32767, value))
        
        return profile.write_power_reg, value

if __name__ == "__main__":
    # Test rápido de perfiles
    registry = HardwareRegistry()
    profile = registry.get_profile("ABB")
    print(f"Perfil ABB cargado: {profile.brand} | Registro Escritura: {profile.write_power_reg}")
    
    # Simular lectura de registros de ABB
    sample_registers = {
        30002: 85,      # 85 kW
        30005: 550,     # SOC 55.0%
        30007: 284,     # Temp 28.4°C
        30012: 2,       # Operating
        30010: 0,       # Sin alarmas
        30015: 0        # Sin disparo anti-isla
    }
    
    data = registry.parse_telemetry("ABB", sample_registers)
    print("Telemetría decodificada:", data)
