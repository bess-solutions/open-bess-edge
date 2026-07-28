# Guía de Inicio Rápido (Quick Start) — 10 Minutos

Esta guía le permitirá poner en marcha el sistema **Open BESS Edge** y su servidor MCP utilizando el simulador Modbus en su máquina local en menos de 10 minutos.

---

## 📋 Requisitos Previos

* Python 3.10 o superior instalado en el sistema.
* Git.
* Un cliente MCP compatible (como **Claude Desktop**).

---

## ⚡ Pasos de Instalación y Ejecución

### Paso 1: Clonar el Repositorio
```bash
git clone https://github.com/bess-solutions/open-bess-edge.git
cd open-bess-edge
```

### Paso 2: Crear e Inicializar el Entorno Virtual
En Linux/macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -r mcp_server/requirements.txt
```

En Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r mcp_server/requirements.txt
```

### Paso 3: Iniciar el Simulador Modbus TCP
Para interactuar localmente con registros reales del BESS sin hardware físico, iniciamos el servidor de demostración en segundo plano:
```bash
python demo_server.py
```
El simulador levantará endpoints HTTP locales y un servicio simulador de variables en `http://localhost:8000/`.

### Paso 4: Levantar el Servidor MCP
Abra un nuevo terminal, reactive el entorno virtual y ejecute el servidor MCP en modo stdio:
```bash
python mcp_server/server.py
```

---

## 🔌 Conectar con Claude Desktop

Para integrar la capacidad de diagnóstico en lenguaje natural a Claude, configure su archivo `claude_desktop_config.json`:

* **Ruta del archivo en Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
* **Ruta del archivo en macOS/Linux**: `~/Library/Application Support/Claude/claude_desktop_config.json`

Agregue el bloque de configuración del servidor:

```json
{
  "mcpServers": {
    "open-bess-edge": {
      "command": "python",
      "args": [
        "C:/Users/lenovo/OneDrive/Desktop/02_Proyectos_Tech/01_BESS_Tech/open-bess-edge/mcp_server/server.py"
      ],
      "env": {
        "PYTHONPATH": "C:/Users/lenovo/OneDrive/Desktop/02_Proyectos_Tech/01_BESS_Tech/open-bess-edge"
      }
    }
  }
}
```

*Nota: Modifique las rutas absolutas según la ubicación donde clonó el repositorio en su computadora.*

Reinicie Claude Desktop. Ahora la IA dispondrá de las herramientas para interrogar el estado del BESS directamente.
