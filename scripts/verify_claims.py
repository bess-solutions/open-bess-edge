#!/usr/bin/env python3
"""Verificador de afirmaciones: EJECUTA el código; no basta con que existan archivos.

1. El número de tests declarado en PROJECT_STATUS (marcador <!-- tests:N -->) coincide con lo recolectado.
2. Cada guarda BESS-GUARD del README existe en la envolvente.
3. Cada perfil listado en el README carga y su modo (control/monitor) coincide con el declarado.
4. La configuración de ejemplo valida (check-config).
5. Ningún documento afirma latencias/plena potencia/homologación no demostradas.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
FAIL: list[str] = []


def check(ok: bool, msg: str) -> None:
    print(("OK   " if ok else "FALLA"), msg)
    if not ok:
        FAIL.append(msg)


readme = (ROOT / "README.md").read_text(encoding="utf-8")
status = (ROOT / "PROJECT_STATUS.md").read_text(encoding="utf-8")

# 1
try:
    import c104  # type: ignore[import-not-found]
    has_c104 = True
except ImportError:
    has_c104 = False

try:
    import cantools  # type: ignore[import-not-found]
    has_cantools = True
except ImportError:
    has_cantools = False

m = re.search(r"<!-- tests:(\d+) -->", status)
col = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"], cwd=ROOT,
                     capture_output=True, text=True)
n = re.search(r"(\d+) tests? collected", col.stdout) or re.search(r"^(\d+) tests", col.stdout, re.M)
n_real = int(n.group(1)) if n else -1

if has_c104 and has_cantools:
    check(bool(m) and n_real == int(m.group(1)),
          f"tests declarados ({m.group(1) if m else '?'}) == recolectados ({n_real})")
else:
    print(f"OMITIDO tests declarados ({m.group(1) if m else '?'}) vs recolectados ({n_real}): "
          f"requiere c104 y cantools (c104={has_c104}, cantools={has_cantools})")

# 2
from open_bess_edge.safety import envelope  # noqa: E402

for code in sorted(set(re.findall(r"BESS-GUARD-\d{3}", readme))):
    check(code in Path(envelope.__file__).read_text(encoding="utf-8"), f"guarda {code} implementada")

# 3
from open_bess_edge.modbus.profile import load_profile  # noqa: E402

for name, mode in re.findall(r"\|\s*`([a-z0-9_]+)`\s*\|\s*(control|monitor)\s*\|", readme):
    p = load_profile(name)
    check(("control" if p.can_control_p else "monitor") == mode, f"perfil {name}: modo declarado '{mode}' == real")

# 4
import os

r = subprocess.run([sys.executable, "-m", "open_bess_edge", "check-config", str(ROOT / "config" / "edge_config.yaml")],
                   cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, capture_output=True, text=True)
check(r.returncode == 0, "config/edge_config.yaml valida")

# 5
for doc, txt in (("README.md", readme), ("PROJECT_STATUS.md", status)):
    for bad in ("sub-0.1ms", "Sub-4ms", "sub-4ms", "Homologad", "certificad", "Zero Mock Data", "plena potencia"):
        check(bad.lower() not in txt.lower().replace("no certificad", "").replace("no homologad", ""), f"{doc} sin afirmación '{bad}'")

print("\nRESULTADO:", "OK" if not FAIL else f"{len(FAIL)} FALLAS")
sys.exit(1 if FAIL else 0)
