# Guía para Contribuir Perfiles de Hardware al BESSAI Registry

> **Audiencia**: Integradores, fabricantes de hardware, y la comunidad BESSAI  
> **Nivel**: Intermedio  
> **Tiempo estimado**: 1–3 horas por perfil

---

## ¿Por qué contribuir un perfil?

El **BESSAI Hardware Registry** (`registry/`) es la biblioteca de dispositivos compatibles con el gateway. Cada perfil JSON define:
- La interfaz de comunicación del dispositivo (Modbus, CAN, REST, SunSpec)
- Los registros/endpoints necesarios para leer estado y enviar comandos
- El mapeo al modelo interno de BESSAI (`soc_pct`, `active_power_kw`, `temp_c`, etc.)
- Los límites de seguridad del hardware

Más perfiles = mayor ecosistema + mayor adopción del proyecto.

---

## Paso 1: Revisar si ya existe el perfil

```bash
# Buscar por fabricante o modelo
ls registry/ | grep -i <fabricante>
```

Si ya existe, considera mejorarlo abriendo una issue con la etiqueta `registry-improvement`.

---

## Paso 2: Reunir la documentación del fabricante

Necesitas al menos uno de los siguientes:

| Protocolo | Documentación necesaria |
|---|---|
| **Modbus RTU/TCP** | Mapa de registros completo con tipo, escala y descripción |
| **SunSpec** | Model ID(s) implementados (ej. Model 103, Model 124) |
| **CAN bus** | DBC file o tabla de frames/signals con CAN IDs |
| **REST API** | Documentación de endpoints, autenticación, y esquema de respuesta |
| **MQTT** | Tópicos, payload schema (JSON), y QoS |

---

## Paso 3: Copiar la plantilla

```bash
cp registry/TEMPLATE_interop_certification.json registry/<fabricante>_<modelo>.json
```

### Estructura mínima requerida

```json
{
  "$schema": "https://bessai.io/schemas/device-profile/v2.json",
  "profile_version": "2.0.0",
  "device": {
    "manufacturer": "NombreFabricante",
    "model": "ModeloExacto",
    "description": "Descripción breve del dispositivo y su caso de uso",
    "firmware_reference": "Nombre y versión del manual técnico",
    "protocol": "ModbusTCP | CAN | HTTP_REST | SunSpec | MQTT"
  },
  "connection": { },
  "registers": { },
  "bessai_mapping": {
    "soc_pct": "<registro_soc>",
    "active_power_kw": {"register": "<registro_potencia>", "transform": "..."},
    "temp_c": "<registro_temperatura>"
  },
  "safety_limits": {
    "soc_min_pct": 10.0,
    "soc_max_pct": 95.0,
    "temp_min_c": -10.0,
    "temp_max_c": 55.0
  },
  "interop_certification": {
    "status": "community_validated | experimental_community | manufacturer_certified",
    "tested_firmware": ["v1.0.0"],
    "test_date": "YYYY-MM",
    "contributor": "Tu nombre / organización"
  }
}
```

### Campos de `bessai_mapping` (obligatorios)

| Campo | Tipo | Descripción |
|---|---|---|
| `soc_pct` | `string` o `object` | Estado de carga (0–100%) |
| `active_power_kw` | `object` | Potencia activa en kW. Positivo = descarga. |
| `temp_c` | `string` o `object` | Temperatura de batería en °C |
| `dispatch_register` | `string` (opcional) | Registro para enviar setpoint de despacho |

### Transforms disponibles

| Transform | Descripción |
|---|---|
| `divide_by_1000` | Convertir W → kW |
| `negate_divide_by_1000` | Invertir signo + W → kW |
| `multiply_by_10` | Aplicar escala ×10 |
| `voltage_x_current_div_1000` | Calcular kW desde tensión × corriente |

---

## Paso 4: Validar el perfil

```bash
# Instalar herramienta de validación (incluida en dev dependencies)
pip install -e ".[dev]"

# Validar esquema JSON
python scripts/validate_registry_profile.py registry/<tu_perfil>.json

# Si tienes el hardware disponible: test de conectividad en vivo
python scripts/test_hardware_connect.py --profile registry/<tu_perfil>.json --host 192.168.x.x
```

### Pruebas de interoperabilidad (suite `tests/interop/`)

```bash
# Correr pruebas de validación estructural para todos los perfiles
python -m pytest tests/interop/ -v

# Tu nuevo perfil debe pasar todas las pruebas de schema validation
```

---

## Paso 5: Abrir un Pull Request

1. **Fork** del repositorio en GitHub
2. Crear rama: `git checkout -b registry/fabricante-modelo`
3. Añadir el archivo JSON a `registry/`
4. Correr las pruebas: `pytest tests/interop/ -v`
5. Abrir PR con la plantilla de registro de hardware:

```markdown
## Nuevo perfil: <Fabricante> <Modelo>

**Fabricante**: ...
**Modelo**: ...
**Protocolo**: ModbusTCP | CAN | REST | SunSpec
**Capacidad probada**: X kWh
**Firmware probado**: vX.X.X
**Hardware disponible para reproducir**: Sí / No (simulado)

### Checklist
- [ ] JSON válido contra `$schema`
- [ ] `bessai_mapping` completo (soc_pct, active_power_kw, temp_c)
- [ ] `safety_limits` definidos
- [ ] `interop_certification.status` correcto
- [ ] Pruebas interop pasan (`pytest tests/interop/ -v`)
```

---

## Niveles de certificación

| Estado | Descripción | Requisito |
|---|---|---|
| `experimental_community` | Funcionamiento parcial verificado | JSON válido + prueba básica de conectividad |
| `community_validated` | Probado en hardware real, control bidireccional | Lectura SOC + despacho verificado + PR aprobado |
| `manufacturer_certified` | Validado por el fabricante | Colaboración oficial con BESSAI Engineering Team |

---

## Ejemplos de referencia

Consulta estos perfiles existentes para inspirarte:

| Perfil | Protocolo | Complejidad |
|---|---|---|
| [`victron_multiplus2.json`](../../registry/victron_multiplus2.json) | Modbus RTU | Media |
| [`huawei_sun2000.json`](../../registry/huawei_sun2000.json) | Modbus TCP | Alta |
| [`solaredge_storedge.json`](../../registry/solaredge_storedge.json) | SunSpec Model 124 | Alta |
| [`byd_battery_box.json`](../../registry/byd_battery_box.json) | CAN bus | Avanzada |
| [`tesla_powerwall3.json`](../../registry/tesla_powerwall3.json) | REST API | Avanzada |

---

## ¿Necesitas ayuda?

- Abre una [GitHub Discussion](https://github.com/bess-solutions/open-bess-edge/discussions) con la etiqueta `hardware-registry`
- Incluye el manual del fabricante o la documentación de protocolo que tengas
- El equipo de BESSAI puede ayudarte a mapear los registros

---

*¿Tu empresa fabrica inversores o BMS y quieres certificación oficial? Escríbenos a `hello@bessai.io` para un proceso de certificación acelerado.*
