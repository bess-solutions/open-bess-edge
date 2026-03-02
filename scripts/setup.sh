#!/usr/bin/env bash
# =============================================================================
# BESSAI Edge Gateway — Interactive Setup Script
# Genera config/.env listo para usar basado en tu caso de uso.
# Uso: bash scripts/setup.sh
# =============================================================================
set -euo pipefail

# ── Colores ───────────────────────────────────────────────────────────────────
GRN='\033[0;32m'; CYN='\033[0;36m'; YLW='\033[1;33m'
RED='\033[0;31m'; BLD='\033[1m'; NC='\033[0m'

logo() {
cat << 'EOF'

  ██████╗ ███████╗███████╗███████╗ █████╗ ██╗
  ██╔══██╗██╔════╝██╔════╝██╔════╝██╔══██╗██║
  ██████╔╝█████╗  ███████╗███████╗███████║██║
  ██╔══██╗██╔══╝  ╚════██║╚════██║██╔══██║██║
  ██████╔╝███████╗███████║███████║██║  ██║██║
  ╚═════╝ ╚══════╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝
  Edge Gateway Setup — v2.14.0

EOF
}

ask() {
  local prompt="$1" var="$2" default="${3:-}"
  if [ -n "$default" ]; then
    echo -e "${CYN}${prompt}${NC} ${YLW}[${default}]${NC}: \c"
  else
    echo -e "${CYN}${prompt}${NC}: \c"
  fi
  read -r answer
  if [ -z "$answer" ] && [ -n "$default" ]; then
    answer="$default"
  fi
  eval "$var=\"\$answer\""
}

ask_yn() {
  local prompt="$1" var="$2" default="${3:-n}"
  echo -e "${CYN}${prompt}${NC} ${YLW}[y/n, default=${default}]${NC}: \c"
  read -r answer
  answer="${answer:-$default}"
  eval "$var=\"\$answer\""
}

separator() { echo -e "\n${CYN}────────────────────────────────────────────────${NC}"; }

# =============================================================================
logo
echo -e "${BLD}Este script crea config/.env con la configuración base para tu sitio.${NC}"
echo -e "Tarda ~2 minutos. Puedes editar el archivo generado después.\n"

# ── Prerequisito: directorio config/ ──────────────────────────────────────────
mkdir -p config
if [ -f config/.env ]; then
  ask_yn "⚠️  config/.env ya existe. ¿Sobrescribir?" OVERWRITE "n"
  if [[ ! "$OVERWRITE" =~ ^[Yy] ]]; then
    echo -e "\n${YLW}Setup cancelado. config/.env no fue modificado.${NC}"
    exit 0
  fi
  cp config/.env "config/.env.backup.$(date +%Y%m%d_%H%M%S)"
  echo -e "${GRN}Backup guardado en config/.env.backup.*${NC}"
fi

# =============================================================================
separator
echo -e "\n${BLD}1 / 5 — Identidad del sitio${NC}\n"
ask "ID único del sitio (ej: SITE-CL-001, SITE-MX-001)" SITE_ID "SITE-CL-001"
ask "Capacidad BESS en kWh" CAPACITY_KWH "200.0"
ask "Potencia nominal en kW" P_NOM_KW "100.0"

# =============================================================================
separator
echo -e "\n${BLD}2 / 5 — Hardware (inversor)${NC}\n"
echo -e "Protocolos disponibles:"
echo -e "  ${GRN}1${NC}) Modbus TCP  (Huawei SUN2000, SolarEdge, Victron, etc.)"
echo -e "  ${GRN}2${NC}) IEC 60870-5-104  (inversores industriales con puerto 2404)"
echo -e "  ${GRN}3${NC}) Solo simulador  (sin hardware físico, para pruebas)"
ask "Seleccionar protocolo" PROTOCOL "1"

case "$PROTOCOL" in
  1)
    ask "IP del inversor (Modbus TCP)" INVERTER_IP "192.168.1.100"
    ask "Puerto Modbus" INVERTER_PORT "502"
    echo -e "\nPerfiles de hardware disponibles:"
    ls registry/*.json 2>/dev/null | sed 's/registry\//  - /; s/\.json//'
    ask "Perfil del inversor (nombre sin .json)" DRIVER_PROFILE "huawei_sun2000"
    IEC104_HOST=""
    ;;
  2)
    ask "IP del inversor (IEC 104)" IEC104_HOST "192.168.1.100"
    INVERTER_IP="$IEC104_HOST"; INVERTER_PORT="2404"
    DRIVER_PROFILE="huawei_sun2000"
    ;;
  3)
    INVERTER_IP="modbus-simulator"; INVERTER_PORT="502"
    DRIVER_PROFILE="huawei_sun2000"; IEC104_HOST=""
    echo -e "${YLW}  Modo simulador activado. Perfecto para pruebas locales.${NC}"
    ;;
  *)
    INVERTER_IP="192.168.1.100"; INVERTER_PORT="502"
    DRIVER_PROFILE="huawei_sun2000"; IEC104_HOST=""
    ;;
esac

# =============================================================================
separator
echo -e "\n${BLD}3 / 5 — Mercado eléctrico${NC}\n"
echo -e "  ${GRN}1${NC}) Chile (SEN/CEN — NTSyCS, SC Bidder)"
echo -e "  ${GRN}2${NC}) México (CENACE/GDMTH)"
echo -e "  ${GRN}3${NC}) Otro / Sin integración de mercado"
ask "Mercado" MARKET "3"

CEN_ENDPOINT=""; CSIRT_API_KEY=""; SC_PFR_PRICE="1.5"; SC_CREG_PRICE="2.0"; SC_AGC_PRICE="3.5"

case "$MARKET" in
  1)
    echo -e "\n${YLW}Para Chile necesitarás:"
    echo -e "  - CEN endpoint: cert.cen.cl → sección Almacenamiento"
    echo -e "  - CSIRT API key: csirt.gob.cl/registro-operadores${NC}"
    ask "CEN endpoint (dejar vacío si no lo tienes aún)" CEN_ENDPOINT ""
    ask "CSIRT API key (dejar vacío si no la tienes aún)" CSIRT_API_KEY ""
    ask "Precio SC PFR (USD/MWh)" SC_PFR_PRICE "1.5"
    ;;
  2)
    echo -e "${YLW}Modo México: tarifas GDMTH disponibles en src/analytics/tariffs/${NC}"
    CEN_ENDPOINT=""; CSIRT_API_KEY=""
    ;;
  3)
    echo -e "${YLW}Sin integración de mercado. Puedes configurar precios manualmente.${NC}"
    ;;
esac

# =============================================================================
separator
echo -e "\n${BLD}4 / 5 — Cloud y observabilidad${NC}\n"
ask_yn "¿Usar GCP Pub/Sub para telemetría cloud?" USE_GCP "n"
GCP_PROJECT=""; GCP_TOPIC=""
if [[ "$USE_GCP" =~ ^[Yy] ]]; then
  ask "GCP Project ID" GCP_PROJECT ""
  ask "GCP Pub/Sub Topic" GCP_TOPIC "bessai-telemetry"
fi

# =============================================================================
separator
echo -e "\n${BLD}5 / 5 — Seguridad${NC}\n"
echo -e "${YLW}Genera una contraseña fuerte para Grafana:${NC}"
GF_PASS=$(openssl rand -base64 16 2>/dev/null || head -c 16 /dev/urandom | base64)
echo -e "  Contraseña generada: ${GRN}${GF_PASS}${NC}"
ask_yn "¿Usar esta contraseña automática?" USE_AUTO_PASS "y"
if [[ "$USE_AUTO_PASS" =~ ^[Yy] ]]; then
  GF_PASSWORD="$GF_PASS"
else
  ask "Contraseña de Grafana (mín. 12 caracteres)" GF_PASSWORD ""
fi

# =============================================================================
# Generar config/.env
separator
echo -e "\n${BLD}Generando config/.env...${NC}\n"

cat > config/.env << ENVEOF
# =============================================================================
# BESSAI Edge Gateway — config/.env
# Generado por scripts/setup.sh — $(date '+%Y-%m-%d %H:%M:%S')
# Edita este archivo según las instrucciones de cada sección.
# IMPORTANTE: nunca subas este archivo a git.
# =============================================================================

# ── Identidad del sitio ───────────────────────────────────────────────────────
BESSAI_SITE_ID=${SITE_ID}
BESSAI_CAPACITY_KWH=${CAPACITY_KWH}
BESSAI_P_NOM_KW=${P_NOM_KW}

# ── Hardware / Protocolo ──────────────────────────────────────────────────────
INVERTER_IP=${INVERTER_IP}
INVERTER_PORT=${INVERTER_PORT}
DRIVER_PROFILE_PATH=registry/${DRIVER_PROFILE}.json
MODBUS_HOST=${INVERTER_IP}
MODBUS_PORT=${INVERTER_PORT}
IEC104_HOST=${IEC104_HOST}
IEC104_PORT=2404

# ── Mercado eléctrico ─────────────────────────────────────────────────────────
CEN_ENDPOINT=${CEN_ENDPOINT}
CEN_SC_DRY_RUN=true
CSIRT_API_KEY=${CSIRT_API_KEY}
SC_PFR_PRICE_USD_MWH=${SC_PFR_PRICE}
SC_CREG_PRICE_USD_MWH=${SC_CREG_PRICE}
SC_AGC_PRICE_USD_MWH=${SC_AGC_PRICE}

# ── GCP / Cloud (opcional) ────────────────────────────────────────────────────
GCP_PROJECT_ID=${GCP_PROJECT}
GCP_PUBSUB_TOPIC=${GCP_TOPIC}
GCP_ENABLED=${USE_GCP}

# ── Observabilidad ────────────────────────────────────────────────────────────
OTEL_EXPORTER_OTLP_ENDPOINT=http://bessai-otel-collector:4317
OTEL_SERVICE_NAME=bessai-edge
LOG_LEVEL=INFO

# ── Seguridad / Grafana ───────────────────────────────────────────────────────
GF_SECURITY_ADMIN_PASSWORD=${GF_PASSWORD}

# ── IA / DRL (desactivado por defecto — activar en Día 7) ────────────────────
BESSAI_DRL_ENABLED=false
BESSAI_ONNX_MODEL_PATH=models/dispatch_policy.onnx

# ── Certificados mTLS CEN (obtener con: make cert SITE_ID=${SITE_ID}) ─────────
CEN_TLS_CERT=infrastructure/certs/${SITE_ID}/client.crt
CEN_TLS_KEY=infrastructure/certs/${SITE_ID}/client.key
CEN_TLS_CA=infrastructure/certs/${SITE_ID}/ca.crt

# end of config/.env
ENVEOF

echo -e "${GRN}✅ config/.env generado correctamente.${NC}\n"

# =============================================================================
# Resumen
separator
echo -e "\n${BLD}Resumen de configuración${NC}\n"
echo -e "  Sitio:         ${GRN}${SITE_ID}${NC}"
echo -e "  Capacidad:     ${GRN}${CAPACITY_KWH} kWh / ${P_NOM_KW} kW${NC}"
echo -e "  Hardware:      ${GRN}${INVERTER_IP}:${INVERTER_PORT} (${DRIVER_PROFILE})${NC}"
echo -e "  Mercado:       ${GRN}$([ "$MARKET" = "1" ] && echo "Chile/CEN" || ([ "$MARKET" = "2" ] && echo "México" || echo "Sin integración"))${NC}"
echo -e "  GCP:           ${GRN}$([ "${USE_GCP:-n}" = "y" ] || [ "${USE_GCP:-n}" = "Y" ] && echo "Activado ($GCP_PROJECT)" || echo "Desactivado")${NC}"

separator
echo -e "\n${BLD}Próximos pasos:${NC}\n"
echo -e "  1. Revisar y ajustar ${YLW}config/.env${NC} si es necesario"

if [ "$PROTOCOL" = "3" ]; then
  echo -e "  2. Levantar el stack con simulador:"
  echo -e "     ${GRN}docker compose -f infrastructure/docker/docker-compose.yml --profile simulator --profile monitoring up -d${NC}"
else
  echo -e "  2. Verificar conectividad al inversor:"
  echo -e "     ${GRN}nc -zv ${INVERTER_IP} ${INVERTER_PORT}${NC}"
  echo -e "  3. Levantar el gateway:"
  echo -e "     ${GRN}docker compose -f docker-compose.yml -f docker-compose.production.yml --profile monitoring up -d${NC}"
fi

echo -e "  4. Verificar estado:"
echo -e "     ${GRN}curl http://localhost:8000/health${NC}"
echo -e "\n  📖 Guía completa: ${CYN}docs/ONBOARDING_7DAYS.md${NC}"
echo -e "  ❓ Problemas: ${CYN}docs/FAQ.md${NC}\n"
