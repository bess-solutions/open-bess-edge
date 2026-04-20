/**
 * BESSAI Modbus RTU Slave (SainSmart UNO)
 * 
 * Simula el comportamiento de los registros principales de un Inversor de Batería BESS.
 * Requiere la librería ModbusRTUSlave de CMB27 u oficial equivalente.
 */

#include <ModbusRTUSlave.h>

// --- Configuración de Pines Físicos ---
const int PIN_POT_SOC   = A0; // Potenciómetro para controlar manualmente el State of Charge (0-100%)
const int PIN_POT_TEMP  = A1; // Potenciómetro para controlar la Temperatura (0-80°C)
const int PIN_RELAY_CHG = 7;  // LED o Relé que indica Carga (Charging)
const int PIN_RELAY_DIS = 8;  // LED o Relé que indica Descarga (Discharging)

// --- Mapa de Registros BESSAI (Simulando BESSAI_SPEC_001 simplificado) ---
// Registros Holding (Holding Registers):
const int REG_SOC           = 0; // State of Charge (0 a 100%)
const int REG_TEMP          = 1; // Temperatura
const int REG_POWER         = 2; // Potencia actual
const int REG_STATE         = 3; // Estado de Inversor
const int REG_FREQ          = 4; // Frecuencia
const int REG_AC_VOLTAGE    = 5; // Tensión RMS / Batería Voltage real

// --- Puntero a memoria Modbus ---
ModbusRTUSlave modbus(Serial);
uint16_t holdingRegisters[6] = {0, 0, 0, 0, 50, 0}; // 6 registros (Freq base = 50Hz)

void setup() {
  // Asegurar que el hardware USART se encienda independientemente de la librería Modbus
  Serial.begin(9600);
  
  // Configurar Pines
  pinMode(PIN_POT_SOC, INPUT);
  pinMode(PIN_POT_TEMP, INPUT);
  
  pinMode(PIN_RELAY_CHG, OUTPUT);
  pinMode(PIN_RELAY_DIS, OUTPUT);

  // Valores iniciales
  digitalWrite(PIN_RELAY_CHG, LOW);
  digitalWrite(PIN_RELAY_DIS, LOW);

  // Iniciar Modbus RTU en Serial (ID Esclavo = 1, Baud Rate 9600)
  modbus.configureHoldingRegisters(holdingRegisters, 6);
  modbus.begin(1, 9600);
}

void loop() {
  // 1. Escuchar repeticiones del Maestro Modbus (El Bridge TCP->RTU)
  modbus.poll();

  // 2. Leer estado del Módulo Sensor de Voltaje en A0
  int valA0Raw = analogRead(PIN_POT_SOC);
  
  // El Arduino mide de 0V a 5V escalado en 0 a 1023 bits
  float pinVoltage = (valA0Raw / 1023.0) * 5.0;
  
  // El sensor de voltaje tiene un divisor 5:1 (30k y 7.5k hms)
  // Voltaje real de tu batería o fuente externa
  float realVoltage = pinVoltage * 5.0;
  
  // Forzamos "12V" como si fuera 100% de la batería
  int calculatedSoc = (realVoltage / 12.0) * 100.0;
  if (calculatedSoc > 100) calculatedSoc = 100;
  if (calculatedSoc < 0) calculatedSoc = 0;
  
  holdingRegisters[REG_SOC] = (uint16_t)calculatedSoc;
  holdingRegisters[REG_AC_VOLTAGE] = (uint16_t)realVoltage;

  // 3. Leer estado del Potenciómetro TEMP (A1 va de 0 a 1023)
  int valTempRaw = analogRead(PIN_POT_TEMP);
  holdingRegisters[REG_TEMP] = map(valTempRaw, 0, 1023, 0, 80);

  // 4. Actuar según el comando BESSAI recibido por el Registro DRL (Ej. comando de power asignado por AI)
  // (Para esta demostración detectamos si registran un POWER positivo o negativo).
  int16_t commandedPower = (int16_t)holdingRegisters[REG_POWER];
  
  if (commandedPower > 0) {
     // Modbus nos pide Descargar batería (inyectar a la red)
     digitalWrite(PIN_RELAY_DIS, HIGH);
     digitalWrite(PIN_RELAY_CHG, LOW);
     holdingRegisters[REG_STATE] = 3; 
  } 
  else if (commandedPower < 0) {
     // Modbus nos pide Cargar batería (absorber energía)
     digitalWrite(PIN_RELAY_DIS, LOW);
     digitalWrite(PIN_RELAY_CHG, HIGH);
     holdingRegisters[REG_STATE] = 2;
  } 
  else {
     // Modbus nos pide Standby
     digitalWrite(PIN_RELAY_DIS, LOW);
     digitalWrite(PIN_RELAY_CHG, LOW);
     holdingRegisters[REG_STATE] = 1;
  }
}
