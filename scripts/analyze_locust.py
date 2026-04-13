#!/usr/bin/env python3
"""
scripts/analyze_locust.py
=========================
Analizador rápido de resultados de carga de Locust para validar SLAs (Tier-1).
Uso:
    python scripts/analyze_locust.py results_stats.csv
"""

import os
import sys


def analyze(csv_file: str) -> None:
    if not os.path.exists(csv_file):
        print(f"Error: {csv_file} no encontrado.")
        sys.exit(1)

    print(f"--- BESSAI Load Test Analysis ({csv_file}) ---")

    sla_violation = False

    with open(csv_file, encoding="utf-8") as f:
        lines = f.readlines()

        if len(lines) <= 1:
            print("CSV vacío o sin suficientes datos.")
            return

        headers = lines[0].strip().split(",")

        try:
            # Buscar índices comunes dinámicamente tolerando comillas o sin comillas
            stripped_headers = [h.strip('"') for h in headers]
            idx_name = stripped_headers.index('Name')
            idx_reqs = stripped_headers.index('Request Count')
            idx_fails = stripped_headers.index('Failure Count')
            idx_p99 = stripped_headers.index('99%')
        except ValueError as e:
            print(f"Formato de CSV no soportado: {e}")
            return

        for line in lines[1:]:
            parts = line.strip().split(",")
            if len(parts) < max(idx_name, idx_reqs, idx_fails, idx_p99):
                continue

            name = parts[idx_name].strip('"')
            if name == "Aggregated":
                print(f"\nResumen Global: {parts[idx_reqs]} peticiones, {parts[idx_fails]} fallos.")
                continue

            try:
                p99 = float(parts[idx_p99])
                fails = int(parts[idx_fails])
            except ValueError:
                continue

            print(f"Endpoint: {name:20s} | P99: {p99} ms | Fallos: {fails}")

            if p99 > 100.0:
                print(f"  [!] ALERTA: Violación de SLA en {name} (P99 = {p99}ms > 100ms)")
                sla_violation = True
            if fails > 0:
                print(f"  [!] ALERTA: Detectados {fails} fallos en el endpoint {name}.")

    print("-------------------------------------------------")
    if sla_violation:
        print("[FAIL] Resultado: SLA de Tier-1 NO CUMPLIDO.")
        sys.exit(1)
    else:
        print("[PASS] Resultado: Operaciones normales, SLA CUMPLIDO.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python analyze_locust.py <archivo_stats.csv>")
        sys.exit(1)

    analyze(sys.argv[1])
