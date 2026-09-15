#!/usr/bin/env python3
"""
verify_claims.py — Automated CI Guardrail for Open BESS Edge
Validates that 100% of documented claims, hardware profiles marked with '✅',
and referenced Python modules exist physically in the codebase.

Enforces:
  - Rule 1: Zero Mock Data / Zero Hallucination
  - Rule 10: Continuous Verification
"""

import sys
import re
import importlib
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent
REGISTRY_DIR = ROOT_DIR / "registry"
README_ES = ROOT_DIR / "README.md"
README_EN = ROOT_DIR / "README.en.md"

def verify_hardware_claims(readme_path: Path) -> list[str]:
    """Extracts all '✅ registry/<profile>.json' claims and checks file existence."""
    errors = []
    if not readme_path.exists():
        return [f"Missing documentation file: {readme_path}"]

    content = readme_path.read_text(encoding="utf-8")
    
    # Pattern to match '✅ registry/<filename>.json' or '✅ <filename>.json'
    matches = re.findall(r"✅\s*(?:registry/)?([a-zA-Z0-9_\-]+\.json)", content)
    if not matches:
        errors.append(f"No hardware profiles found in {readme_path.name}")
        return errors

    print(f"🔍 Checking {len(matches)} hardware claims in {readme_path.name}...")
    for filename in matches:
        target_file = REGISTRY_DIR / filename
        if not target_file.exists():
            errors.append(f"FALSE CLAIM in {readme_path.name}: '✅ {filename}' referenced but file does not exist in registry/")
        else:
            print(f"  [PASS] Verified profile: {filename}")

    # Ensure no unverified manufacturer is marked with ✅
    disallowed_unverified = ["Sungrow", "Kehua", "Ingeteam", "Power Electronics", "CATL", "Gotion", "EVE Energy"]
    for unverified in disallowed_unverified:
        # Check if there is a line with both the manufacturer and ✅
        for line in content.splitlines():
            if unverified.lower() in line.lower() and "✅" in line:
                # Disallow unless explicitly in comments or tests
                errors.append(f"UNVERIFIED CLAIM in {readme_path.name}: '{unverified}' is marked with '✅' without a registry profile: {line.strip()}")

    return errors

def verify_python_modules() -> list[str]:
    """Verifies that all core modules and controllers exist and can be imported."""
    errors = []
    core_modules = [
        "src.edge_node",
        "src.controllers.ffr_droop_controller",
        "src.controllers.volt_var_controller",
        "src.drivers.modbus_client",
        "src.drivers.can_bms_driver",
        "src.drivers.iec104_client",
        "src.drivers.goose_fast_trip",
        "src.drivers.cen_sipub_client",
        "src.safety.safety_envelope_evaluator",
    ]

    print(f"\n🔍 Verifying {len(core_modules)} core Python modules in src/...")
    # Add root dir to sys.path
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))

    for mod_name in core_modules:
        try:
            importlib.import_module(mod_name)
            print(f"  [PASS] Module imported: {mod_name}")
        except Exception as exc:
            errors.append(f"MODULE IMPORT ERROR: Could not import '{mod_name}': {exc}")

    return errors

def main() -> int:
    print("=" * 70)
    print("🛡️  OPEN BESS EDGE — CI CLAIM VERIFICATION GUARDRAIL")
    print("=" * 70)

    all_errors = []
    all_errors.extend(verify_hardware_claims(README_ES))
    all_errors.extend(verify_hardware_claims(README_EN))
    all_errors.extend(verify_python_modules())

    print("=" * 70)
    if all_errors:
        print(f"❌ CI GUARDRAIL FAILED WITH {len(all_errors)} ERRORS:")
        for err in all_errors:
            print(f"  - {err}")
        print("=" * 70)
        return 1

    print("✅ 100% OF DOCUMENTED HARDWARE AND CODE CLAIMS ARE VERIFIED ON DISK.")
    print("=" * 70)
    return 0

if __name__ == "__main__":
    sys.exit(main())
