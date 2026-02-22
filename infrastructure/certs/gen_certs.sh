#!/usr/bin/env bash
# =============================================================================
# BESSAI Edge Gateway — OT PKI Certificate Generator
# IEC 62443-3-3 SR 3.1: Communication Integrity via mutual TLS
# GAP-003 REMEDIATION
# =============================================================================
# Usage:
#   bash infrastructure/certs/gen_certs.sh
#
# Output (in infrastructure/certs/):
#   ca.key              — CA private key          (SECRET — never commit)
#   ca.crt              — CA root certificate     (safe to commit)
#   gateway-client.key  — Gateway private key     (SECRET — never commit)
#   gateway-client.crt  — Gateway certificate     (safe to commit)
#   gateway-client.csr  — CSR (intermediate)      (safe to commit/discard)
#   modbus-proxy.key    — Proxy private key       (SECRET — never commit)
#   modbus-proxy.crt    — Proxy certificate       (safe to commit)
#   modbus-proxy.csr    — CSR (intermediate)      (safe to commit/discard)
#
# Requirements: openssl (ships with Git for Windows / WSL / macOS / Linux)
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="$SCRIPT_DIR"

# Certificate validity — 10 years (edge devices have infrequent rotations)
VALIDITY_DAYS=3650

# Organization info (customize per deployment)
COUNTRY="${BESSAI_CERT_COUNTRY:-CL}"
ORG="${BESSAI_CERT_ORG:-BESSAI-Solutions}"
SITE_ID="${BESSAI_SITE_ID:-edge-001}"

echo "════════════════════════════════════════════════════"
echo "  BESSAI OT PKI Generator — IEC 62443 GAP-003"
echo "  Site: ${SITE_ID}  |  Org: ${ORG}"
echo "════════════════════════════════════════════════════"

# ── 1. CA Root (BESSAI-OT-CA) ─────────────────────────────────────────────────
echo ""
echo "[1/3] Generating BESSAI-OT-CA root certificate..."

openssl genrsa -out "${OUT_DIR}/ca.key" 4096 2>/dev/null

openssl req -new -x509 \
    -key "${OUT_DIR}/ca.key" \
    -out "${OUT_DIR}/ca.crt" \
    -days "${VALIDITY_DAYS}" \
    -subj "/C=${COUNTRY}/O=${ORG}/CN=BESSAI-OT-CA-${SITE_ID}" \
    -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
    -addext "keyUsage=critical,keyCertSign,cRLSign"

echo "    ✅ CA: ${OUT_DIR}/ca.crt"

# ── 2. Gateway Client Certificate ─────────────────────────────────────────────
echo ""
echo "[2/3] Generating gateway client certificate..."

openssl genrsa -out "${OUT_DIR}/gateway-client.key" 2048 2>/dev/null

openssl req -new \
    -key "${OUT_DIR}/gateway-client.key" \
    -out "${OUT_DIR}/gateway-client.csr" \
    -subj "/C=${COUNTRY}/O=${ORG}/CN=bessai-gateway-${SITE_ID}"

openssl x509 -req \
    -in "${OUT_DIR}/gateway-client.csr" \
    -CA "${OUT_DIR}/ca.crt" \
    -CAkey "${OUT_DIR}/ca.key" \
    -CAcreateserial \
    -out "${OUT_DIR}/gateway-client.crt" \
    -days "${VALIDITY_DAYS}" \
    -extfile <(printf "extendedKeyUsage=clientAuth\nsubjectAltName=DNS:bessai-gateway,DNS:localhost") \
    2>/dev/null

echo "    ✅ Gateway client cert: ${OUT_DIR}/gateway-client.crt"

# ── 3. Modbus Proxy (stunnel) Server Certificate ──────────────────────────────
echo ""
echo "[3/3] Generating modbus-proxy (stunnel) server certificate..."

openssl genrsa -out "${OUT_DIR}/modbus-proxy.key" 2048 2>/dev/null

openssl req -new \
    -key "${OUT_DIR}/modbus-proxy.key" \
    -out "${OUT_DIR}/modbus-proxy.csr" \
    -subj "/C=${COUNTRY}/O=${ORG}/CN=bessai-modbus-proxy-${SITE_ID}"

openssl x509 -req \
    -in "${OUT_DIR}/modbus-proxy.csr" \
    -CA "${OUT_DIR}/ca.crt" \
    -CAkey "${OUT_DIR}/ca.key" \
    -CAcreateserial \
    -out "${OUT_DIR}/modbus-proxy.crt" \
    -days "${VALIDITY_DAYS}" \
    -extfile <(printf "extendedKeyUsage=serverAuth\nsubjectAltName=DNS:bessai-stunnel,DNS:localhost") \
    2>/dev/null

echo "    ✅ Proxy server cert: ${OUT_DIR}/modbus-proxy.crt"

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════"
echo "  PKI generation complete."
echo ""
echo "  Certificates generated in: ${OUT_DIR}"
echo ""
echo "  ⚠️  PRIVATE KEYS — DO NOT COMMIT:"
echo "     ca.key  gateway-client.key  modbus-proxy.key"
echo ""
echo "  Next steps:"
echo "    1. docker compose --profile ot-security up -d"
echo "    2. Set in .env:"
echo "       OT_MTLS_ENABLED=true"
echo "       OT_CA_CERT_PATH=infrastructure/certs/ca.crt"
echo "       OT_CLIENT_CERT_PATH=infrastructure/certs/gateway-client.crt"
echo "       OT_CLIENT_KEY_PATH=infrastructure/certs/gateway-client.key"
echo "════════════════════════════════════════════════════"
