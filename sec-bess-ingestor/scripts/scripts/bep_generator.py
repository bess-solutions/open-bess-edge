"""
scripts/bep_generator.py — Generador automático de BEPs para brechas críticas
──────────────────────────────────────────────────────────────────────────────
Genera BESSAI Enhancement Proposals (BEPs) en formato Markdown para cada
brecha normativa crítica detectada. Los BEPs se depositan en docs/bep/
del repositorio open-bess-edge para iniciar el proceso de revisión.

Uso:
    python scripts/bep_generator.py                 # Desde sec-bess-ingestor/
    python scripts/bep_generator.py --output /path  # Directorio alternativo
"""

from __future__ import annotations

import argparse
import io
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Windows UTF-8
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except AttributeError:
        pass

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from analysis.gap_analyzer import GapAnalyzer, GapItem, REGULATORY_RULES
from scraper.sec_scraper import SECScraper

logger = logging.getLogger(__name__)

# ── Numeración de BEPs ── (los BEPs del repo van del 0100 al 0303 aprox.)
# Los BEPs de normativa SEC empezarán en 0400
BEP_BASE_NUMBER = 400


def next_bep_number(output_dir: Path) -> int:
    """Determina el siguiente número BEP disponible."""
    existing = sorted(output_dir.glob("BEP-04*.md"))
    if not existing:
        return BEP_BASE_NUMBER
    last = int(existing[-1].stem.split("-")[1])
    return last + 1


def generate_bep(gap: GapItem, bep_number: int) -> str:
    """Genera el Markdown de un BEP para una brecha normativa."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    bep_id = f"BEP-{bep_number:04d}"
    status = "Draft"

    effort_map = {"critical": "M", "medium": "S", "low": "XS"}
    size = effort_map.get(gap.priority, "M")

    return f"""# {bep_id} — {gap.norm_ref}

| Campo | Valor |
|---|---|
| **BEP** | {bep_id} |
| **Título** | Implementar cumplimiento: {gap.norm_ref} |
| **Estado** | {status} |
| **Tipo** | Normative Compliance |
| **Prioridad** | {gap.priority_label} |
| **Fecha** | {today} |
| **Origen** | sec-bess-ingestor — análisis normativo automático SEC Chile |
| **T-shirt size** | {size} ({gap.estimated_effort}) |

---

## Motivación

{gap.description}

### Referencia normativa

- **Norma:** {gap.norm_ref}
- **Documento SEC:** [{gap.sec_document_title}]({gap.sec_document_url})

---

## Estado Actual en open-bess-edge

{gap.status_label}: {gap.bess_current_state}

```
Referencia de código: {gap.bess_code_ref}
```

---

## Propuesta de Implementación

{gap.technical_action}

### Criterios de aceptación

- [ ] La implementación cubre los requisitos de `{gap.norm_ref}`
- [ ] Tests unitarios e integración con coverage ≥ 80%
- [ ] Documentación actualizada en `docs/compliance/`
- [ ] Sin regresiones en el suite de 613 tests existente
- [ ] Revisado y aprobado por maintainer principal

---

## Impacto

| Área | Cambio |
|---|---|
| Cumplimiento normativo | ✅ Cierra brecha {gap.gap_id} |
| Riesgo regulatorio | Reduce exposición ante fiscalización SEC/CEN |
| Esfuerzo estimado | {gap.estimated_effort} |
| Versión objetivo | v2.0 |

---

## Referencias

- [Análisis de brechas SEC](../../docs/compliance/sec_gap_analysis.md)
- [NTSyCS 2022](https://www.coordinador.cl/normativa/)
- [SEC Chile](https://www.sec.cl)

---

*Generado automáticamente por [sec-bess-ingestor](../../sec-bess-ingestor/) — {today}*
"""


def run(output_dir: Path, data_file: Optional[str] = None) -> list[str]:
    """
    Genera BEPs para todas las brechas críticas.
    Retorna lista de rutas de BEPs generados.
    """
    from typing import Optional

    output_dir.mkdir(parents=True, exist_ok=True)

    # Cargar datos SEC
    if data_file:
        sec_data = SECScraper.load_file(data_file)
    else:
        sec_data = SECScraper.load_latest() or {
            "records": [], "total_records": 0, "bess_relevant_count": 0
        }

    # Analizar brechas
    analyzer = GapAnalyzer()
    gaps = analyzer.analyze(sec_data)
    critical_gaps = [g for g in gaps if g.priority == "critical"]

    logger.info(f"Generando BEPs para {len(critical_gaps)} brechas críticas...")

    bep_number = next_bep_number(output_dir)
    generated: list[str] = []

    for gap in critical_gaps:
        bep_content = generate_bep(gap, bep_number)
        bep_filename = f"BEP-{bep_number:04d}.md"
        bep_path = output_dir / bep_filename
        bep_path.write_text(bep_content, encoding="utf-8")
        logger.info(f"  BEP generado: {bep_path}")
        generated.append(str(bep_path))
        bep_number += 1

    logger.info(f"Total BEPs generados: {len(generated)}")
    return generated


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    parser = argparse.ArgumentParser(description="Generador de BEPs normativos SEC")
    parser.add_argument(
        "--output", "-o", default=None,
        help="Directorio de salida (default: ../open-bess-edge/docs/bep/ o data/beps/)"
    )
    parser.add_argument("--data-file", default=None, help="Archivo JSON de scraping")
    args = parser.parse_args()

    if args.output:
        out_dir = Path(args.output)
    else:
        # Intentar escribir al repo open-bess-edge local
        bess_bep_dir = Path(__file__).parent.parent.parent / "open-bess-edge" / "docs" / "bep"
        if bess_bep_dir.exists():
            out_dir = bess_bep_dir
            logger.info(f"Usando BEP dir del repo: {out_dir}")
        else:
            out_dir = Path(__file__).parent.parent / "data" / "beps"
            logger.info(f"Repo no encontrado. Guardando en: {out_dir}")

    run(out_dir, args.data_file)


if __name__ == "__main__":
    main()
