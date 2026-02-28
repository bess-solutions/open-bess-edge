#!/usr/bin/env bash
# =============================================================================
# BESSAI Edge Gateway — mTLS Certificate Generator
# GAP-003: NTSyCS Cap. 6.1 — CEN Telemetry TLS
# =============================================================================
# Usage:
#   bash infrastructure/certs/gen_certs.sh [SITE_ID]
#
# Output (DO NOT commit *.key *.pem — they are in .gitignore):
#   infrastructure/certs/ca.key          ← CA private key (KEEP SECRET)
#   infrastructure/certs/ca.crt          ← CA certificate (safe to commit)
#   infrastructure/certs/client.key      ← Client private key
#   infrastructure/certs/client.csr      ← Certificate signing request
#   infrastructure/certs/client.crt      ← Client certificate (signed by CA)
#   infrastructure/certs/client.pem      ← Combined cert+key for convenience
#
# After running this script, set in config/.env:
#   CEN_TLS_CERT=infrastructure/certs/client.crt
#   CEN_TLS_KEY=infrastructure/certs/client.key
#   CEN_TLS_CA=infrastructure/certs/ca.crt
# =============================================================================

set -euo pipefail

SITE_ID="${1:-SITE-CL-001}"
CERTS_DIR="$(cd "$(dirname "$0")" && pwd)"
DAYS=825   # max validity for mTLS (< 2 years per CAB Forum)
COUNTRY="CL"
ORG="BESS Solutions SpA"
OU="BESSAI Edge Gateway"

echo "========================================================"
echo "  BESSAI mTLS Certificate Generator"
echo "  Site: ${SITE_ID}"
echo "  Output: ${CERTS_DIR}/"
echo "========================================================"

# Ensure OpenSSL is available
command -v openssl >/dev/null 2>&1 || { echo "ERROR: openssl not found"; exit 1; }

mkdir -p "${CERTS_DIR}"

# --- Step 1: CA Key + Certificate (self-signed) ----------------------------
echo "[1/5] Generating CA key and certificate..."
openssl genrsa -out "${CERTS_DIR}/ca.key" 4096 2>/dev/null
openssl req -new -x509 \
    -key "${CERTS_DIR}/ca.key" \
    -out "${CERTS_DIR}/ca.crt" \
    -days ${DAYS} \
    -subj "/C=${COUNTRY}/O=${ORG}/OU=${OU}/CN=BESSAI-CA-${SITE_ID}"
echo "    ✓ CA certificate: ${CERTS_DIR}/ca.crt"

# --- Step 2: Client Key + CSR -----------------------------------------------
echo "[2/5] Generating client key and CSR..."
openssl genrsa -out "${CERTS_DIR}/client.key" 2048 2>/dev/null
openssl req -new \
    -key "${CERTS_DIR}/client.key" \
    -out "${CERTS_DIR}/client.csr" \
    -subj "/C=${COUNTRY}/O=${ORG}/OU=${OU}/CN=${SITE_ID}"
echo "    ✓ Client CSR: ${CERTS_DIR}/client.csr"

# --- Step 3: Sign client cert with CA ----------------------------------------
echo "[3/5] Signing client certificate with CA..."
cat > "${CERTS_DIR}/client_ext.cnf" << EOF
[req]
req_extensions = v3_req
[v3_req]
subjectAltName = DNS:${SITE_ID},DNS:bessai-edge
extendedKeyUsage = clientAuth
keyUsage = digitalSignature, keyEncipherment
EOF

openssl x509 -req \
    -in "${CERTS_DIR}/client.csr" \
    -CA "${CERTS_DIR}/ca.crt" \
    -CAkey "${CERTS_DIR}/ca.key" \
    -CAcreateserial \
    -out "${CERTS_DIR}/client.crt" \
    -days ${DAYS} \
    -extensions v3_req \
    -extfile "${CERTS_DIR}/client_ext.cnf" \
    2>/dev/null
echo "    ✓ Client certificate: ${CERTS_DIR}/client.crt"

# --- Step 4: Combined PEM (optional, for curl/httpx testing) ----------------
echo "[4/5] Creating combined PEM..."
cat "${CERTS_DIR}/client.crt" "${CERTS_DIR}/client.key" > "${CERTS_DIR}/client.pem"
echo "    ✓ Combined PEM: ${CERTS_DIR}/client.pem"

# --- Step 5: Verify ----------------------------------------------------------
echo "[5/5] Verifying certificate chain..."
openssl verify -CAfile "${CERTS_DIR}/ca.crt" "${CERTS_DIR}/client.crt" 2>/dev/null
echo "    ✓ Certificate chain valid"

# --- Cleanup temp files -------------------------------------------------------
rm -f "${CERTS_DIR}/client.csr" "${CERTS_DIR}/client_ext.cnf" "${CERTS_DIR}/ca.srl"

# --- Summary ------------------------------------------------------------------
echo ""
echo "========================================================"
echo "  ✅ Certificates generated successfully for ${SITE_ID}"
echo "========================================================"
echo ""
echo "  Add to config/.env:"
echo "    CEN_TLS_CERT=infrastructure/certs/client.crt"
echo "    CEN_TLS_KEY=infrastructure/certs/client.key"
echo "    CEN_TLS_CA=infrastructure/certs/ca.crt"
echo ""
echo "  ⚠️  IMPORTANT:"
echo "    - ca.key and client.key are PRIVATE — never commit them"
echo "    - They are already in .gitignore"
echo "    - Share ca.crt with the CEN operator for server-side config"
echo ""
