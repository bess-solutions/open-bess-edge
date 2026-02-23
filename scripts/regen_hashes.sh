#!/usr/bin/env bash
# =============================================================================
# scripts/regen_hashes.sh — Regenerate requirements.hash.txt
# =============================================================================
# Usage (from repo root):
#   bash scripts/regen_hashes.sh
#
# Requirements:
#   pip install pip-tools
#
# What it does:
#   1. Runs pip-compile to resolve all transitive deps from requirements.txt
#   2. Generates SHA-256 hashes for every package (--generate-hashes)
#   3. Outputs requirements.hash.txt (checked in, used by CI verify-hashes job)
#
# Run after:
#   - Adding/upgrading a dependency in requirements.txt
#   - Rotating hashes for security reasons
#
# IEC 62443-2-3 / OpenSSF Gold Badge: reproducible builds with pinned hashes.
# =============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "▶ Installing pip-tools..."
pip install --quiet pip-tools

echo "▶ Compiling requirements with hashes..."
pip-compile \
  requirements.txt \
  --generate-hashes \
  --output-file requirements.hash.txt \
  --resolver=backtracking \
  --verbose

echo "✅ requirements.hash.txt generated. Review and commit."
echo ""
echo "   To verify hash install locally:"
echo "   pip install --require-hashes --no-deps -r requirements.hash.txt"
