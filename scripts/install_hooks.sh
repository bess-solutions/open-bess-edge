#!/usr/bin/env bash
# =============================================================================
# BESSAI — Install git hooks (PI Protection Policy v1.2)
# Run this once after cloning:
#   bash scripts/install_hooks.sh
# =============================================================================
set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"
git config core.hooksPath .githooks
echo "✅  BESSAI git hooks activated (core.hooksPath = .githooks)"
echo "    Pre-commit: blocks proprietary files (ONNX, .env, certs, tariffs)"
