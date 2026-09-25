#!/usr/bin/env python3
"""Verificador de afirmaciones: EJECUTA el código; no basta con que existan archivos.

1. El número de tests declarado en PROJECT_STATUS (marcador <!-- tests:N -->) coincide con lo recolectado.
2. Cada guarda BESS-GUARD del README existe en la envolvente.
3. Cada perfil listado en el README carga y su modo (control/monitor) coincide con el declarado.
4. La configuración de ejemplo valida (check-config).
5. Auditoría integral de documentación (raíz y docs/ completo): Cero buzzwords, física imposible o afirmaciones no sustentadas.
6. Gobernanza de autoría: commits de bots ficticios autónomos vetados en HEAD.
"""
from __future__ import annotations

import importlib.util
import os
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
readme_en = (ROOT / "README.en.md").read_text(encoding="utf-8") if (ROOT / "README.en.md").exists() else ""
status = (ROOT / "PROJECT_STATUS.md").read_text(encoding="utf-8")

# 1. Verificación de tests canónicos y opcionales
has_c104 = importlib.util.find_spec("c104") is not None
has_cantools = importlib.util.find_spec("cantools") is not None

m = re.search(r"<!-- tests:(\d+) -->", status)
col = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"], cwd=ROOT,
                     capture_output=True, text=True)  # nosec S603
n = re.search(r"(\d+) tests? collected", col.stdout) or re.search(r"^(\d+) tests", col.stdout, re.M)
n_real = int(n.group(1)) if n else -1

if has_c104 and has_cantools:
    check(bool(m) and n_real == int(m.group(1)),
          f"tests declarados ({m.group(1) if m else '?'}) == recolectados ({n_real}) con módulos opcionales")
else:
    check(n_real == 278, f"tests recolectados ({n_real}) == 278 canónicos del núcleo (c104={has_c104}, cantools={has_cantools})")

# 2. Guardas de seguridad BESS-GUARD declaradas en README existen en el código
from open_bess_edge.safety import envelope  # noqa: E402

for code in sorted(set(re.findall(r"BESS-GUARD-\d{3}", readme))):
    check(code in Path(envelope.__file__).read_text(encoding="utf-8"), f"guarda {code} implementada")

# 3. Perfiles del registry cargan y modo declarado coincide
from open_bess_edge.modbus.profile import load_profile  # noqa: E402

for name, mode in re.findall(r"\|\s*`([a-z0-9_]+)`\s*\|\s*(control|monitor)\s*\|", readme):
    p = load_profile(name)
    check(("control" if p.can_control_p else "monitor") == mode, f"perfil {name}: modo declarado '{mode}' == real")

# 4. Configuración de producción valida
r = subprocess.run(  # noqa: S603
    [sys.executable, "-m", "open_bess_edge", "check-config", str(ROOT / "config" / "edge_config.yaml")],
    cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, capture_output=True, text=True,
)
check(r.returncode == 0, "config/edge_config.yaml valida")

# 5. Truth-in-Advertising Integral: Raíz + todos los documentos en docs/
forbidden_buzzwords = (
    "sub-0.1ms", "sub-4ms", "zero mock data", "plena potencia", "hvdc",
    "500 mw", "800 mw", "100% listo para producción", "planetary energy os",
)

docs_to_scan: list[tuple[str, str]] = [
    ("README.md", readme),
    ("README.en.md", readme_en),
    ("PROJECT_STATUS.md", status),
]

if (ROOT / "GOVERNANCE.md").exists():
    docs_to_scan.append(("GOVERNANCE.md", (ROOT / "GOVERNANCE.md").read_text(encoding="utf-8")))

docs_dir = ROOT / "docs"
if docs_dir.exists():
    for md_file in sorted(docs_dir.rglob("*.md")):
        rel = str(md_file.relative_to(ROOT))
        docs_to_scan.append((rel, md_file.read_text(encoding="utf-8", errors="ignore")))

for doc_path, txt in docs_to_scan:
    clean_txt = txt.lower()
    # Permitir homologación solo en contexto explícito de "pendiente de homologación", "no homologado", o reglas en GOVERNANCE
    clean_homolog = (
        clean_txt.replace("pendiente de homologación", "")
        .replace("no homologad", "")
        .replace('"homologado"', "")
        .replace("'homologado'", "")
        .replace("«homologado»", "")
    )
    check("homologad" not in clean_homolog, f"{doc_path} sin afirmación no demostrada 'homologad'")

    # Bloquear afirmaciones falsas de certificación de producto/software, permitiendo certificados TLS/mTLS/X.509
    for bad_cert in ("software certificad", "producto certificad", "algoritmo certificad", "100% certificad", "certificad contra ntsycs", "certificación sec"):
        check(bad_cert not in clean_txt, f"{doc_path} sin afirmación no demostrada '{bad_cert}'")

    # Bloquear buzzwords no sustentados
    for bad in forbidden_buzzwords:
        check(bad not in clean_txt, f"{doc_path} sin afirmación no demostrada '{bad}'")

    # Bloquear BESSAIEvolve salvo si el documento explícitamente lo declara retirado/withdrawn
    if "bessaievolve" in clean_txt:
        is_withdrawn = "withdrawn" in clean_txt or "retirad" in clean_txt or "obsolet" in clean_txt
        check(is_withdrawn, f"{doc_path} menciona BESSAIEvolve solo como propuesta retirada/withdrawn")

# 6. Gobernanza de autoría: Comprobar que HEAD no proviene de bots autónomos ficticios
FORBIDDEN_AUTHORS = (
    "docker-agent",
    "gordon - docker ai assistant",
    "bessai v bot",
    "thermal optimization bot",
    "cen resilience bot",
    "ingeteam specialist bot",
)
try:
    head_author = subprocess.run(
        ["git", "log", "-n", "1", "--format=%an <%ae>"],
        cwd=ROOT, capture_output=True, text=True, check=False
    ).stdout.lower()
    for bad_author in FORBIDDEN_AUTHORS:
        check(bad_author not in head_author, f"HEAD commit no proviene de bot ficticio '{bad_author}'")
except Exception as e:
    print(f"WARN No se pudo verificar autoría git: {e}")

print("\nRESULTADO:", "OK" if not FAIL else f"{len(FAIL)} FALLAS")
sys.exit(1 if FAIL else 0)
