# Guía Operativa de Ciberseguridad: Estándar IEC 62443

Este playbook técnico establece las especificaciones de diseño, endurecimiento (hardening) y respuesta a incidentes para el gateway **Open BESS Edge** conforme a los requisitos de la norma **IEC 62443** (Niveles de Seguridad SL-1 a SL-3).

---

## 1. Arquitectura de Red y Segmentación (Zonas y Conductos)

Siguiendo el estándar **IEC 62443-3-2**, la infraestructura del BESS se divide en zonas lógicas y físicas de seguridad separadas por cortafuegos (firewalls) stateful.

```
                  ┌──────────────────────────────┐
                  │    Red Corporativa / Nube    │  (Zona 4 - IT)
                  └──────────────┬───────────────┘
                                 │
                         [Firewall Perimetral]
                                 │
                  ┌──────────────▼───────────────┐
                  │       Zona Desmilitarizada   │  (Zona 2 - DMZ Industrial)
                  │   - Gateway Open BESS Edge   │
                  │   - Servidor MCP             │
                  └──────────────┬───────────────┘
                                 │
                         [Firewall Industrial]
                                 │
                  ┌──────────────▼───────────────┐
                  │       Red de Control OT      │  (Zona 1 - Control OT)
                  │   - SCADA Planta             │
                  │   - Relés de Protección MT   │
                  │   - Inversores (PCS)         │
                  │   - Controladores de Racks   │
                  └──────────────────────────────┘
```

---

## 2. Hardening del Sistema Operativo y Comunicaciones

### 2.1 Cifrado en Tránsito (TLS 1.3)
Toda comunicación que salga de la DMZ hacia redes externas debe utilizar **TLS 1.3**.

1. Modificar el archivo `/etc/ssl/openssl.cnf` (o el correspondiente en el OS) para forzar los parámetros de cifrado:
   ```ini
   [system_default_sect]
   MinProtocol = TLSv1.3
   CipherString = TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256
   ```

2. Generación de claves criptográficas y certificados locales mediante algoritmo de curva elíptica P-256:
   ```bash
   openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 \
     -keyout mcp_server.key -out mcp_server.crt -days 365 -nodes \
     -subj "/C=CL/O=BESSAI/CN=mcp.bess-solutions.cl"
   ```

### 2.2 Robustecimiento de SSH (`/etc/ssh/sshd_config`)
Para acceso de mantenimiento local/remoto seguro (SL-2/SL-3):
```ini
# Deshabilitar autenticación por contraseña y forzar llaves seguras
PasswordAuthentication no
PubkeyAuthentication yes
PermitRootLogin no

# Algoritmos de intercambio de llaves y cifrado permitidos
KexAlgorithms curve25519-sha256@libssh.org
HostKeyAlgorithms ssh-ed25519-cert-v01@openssh.com,ssh-ed25519
Ciphers chacha20-poly1305@openssh.com,aes256-gcm@openssh.com
MACs hmac-sha2-512-etm@openssh.com

# Parámetros de conexión
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2
AllowUsers operator admin_bess
```

---

## 3. Configuración de Referencia de Firewall Industrial (FortiGate)

El cortafuegos industrial debe configurarse bajo una política estricta de **Allowlist**. A continuación se presentan las políticas de referencia para un equipo FortiGate (CLI):

```fortinet
# 1. Definición de Direcciones IP de los Activos
config firewall address
    edit "Gateway_Edge_IP"
        set subnet 192.168.10.50 255.255.255.255
    next
    edit "PCS_Inverters_Subnet"
        set subnet 192.168.20.0 255.255.255.0
    next
    edit "BMS_Racks_Subnet"
        set subnet 192.168.20.100 255.255.255.224
    next
end

# 2. Definición del Servicio Modbus TCP (Puerto 502)
config firewall service custom
    edit "MODBUS_TCP"
        set tcp-portrange 502
    next
end

# 3. Regla de Acceso: Gateway Edge -> PCS (Lectura Telemetría)
config firewall policy
    edit 101
        set name "Edge-to-PCS-Modbus"
        set srcintf "port3"   # Interfaz DMZ (Gateway)
        set dstintf "port4"   # Interfaz OT (Inversores)
        set srcaddr "Gateway_Edge_IP"
        set dstaddr "PCS_Inverters_Subnet"
        set action accept
        set schedule "always"
        set service "MODBUS_TCP"
        set logtraffic all
        set utm-status enable
        set ips-status enable
        set ips-sensor "Industrial_IPS_Sensor"  # Filtro DPI para Modbus
    next
end
```

---

## 4. Playbook de Respuesta a Incidentes en Entorno OT

### Escenario A: Intento de Intrusión o Anomalías de Red OT
* **Indicador**: Múltiples intentos fallidos de autenticación SSH detectados en logs del Gateway o lecturas Modbus inválidas desde una IP externa a la DMZ.
* **Acciones Inmediatas**:
  1. **Aislamiento**: Ejecutar regla en el firewall local del Gateway para descartar tráfico de la IP ofensora:
     ```bash
     sudo iptables -A INPUT -s <IP_ATACANTE> -j DROP
     ```
  2. **Notificación**: Disparar alarma al SIEM centralizado y al canal BESSAI Swarm.
  3. **Rotación**: Forzar la rotación inmediata de las llaves de acceso SSH locales y de los certificados TLS del servidor MCP.

### Escenario B: Sospecha de Ransomware / Malware en DMZ
* **Indicador**: Ejecución de procesos no identificados consumiendo alta CPU en el Gateway, o llamadas inusuales de red hacia servidores externos no catalogados.
* **Acciones Inmediatas**:
  1. **Desconexión Física/Lógica**: Aplicar "Plan de Aislamiento de Red". El firewall perimetral corta todo tráfico de la DMZ hacia el exterior.
  2. **Fallback Local**: El EMS local asume el control del BESS de forma 100% aislada (modo autónomo sin red corporativa).
  3. **Preservación Forense**: Copiar la base de datos local y los logs de seguridad a un medio extraíble antes de reiniciar o reinstalar la imagen limpia desde el firmware firmado digitalmente.
