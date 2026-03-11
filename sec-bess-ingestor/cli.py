"""
cli.py — Interfaz de línea de comandos para sec-bess-ingestor
──────────────────────────────────────────────────────────────
MODO NORMAL:
    python cli.py scrape              # Raspa SEC (serial, respetuoso)
    python cli.py analyze             # Analiza brechas
    python cli.py report              # Genera reporte Markdown
    python cli.py publish             # Publica al repo (requiere GITHUB_TOKEN)
    python cli.py update              # Todo: scrape → analyze → report → publish

MODO AGRESIVO (más rápido, más fuentes, texto de PDFs):
    python cli.py scrape --aggressive                  # async 8x + PDF + multi-fuente
    python cli.py scrape --aggressive --concurrency 16  # subir la concurrencia al máximo
    python cli.py scrape-all                           # solo multi-fuente (coordinador, bcn, etc.)
    python cli.py extract-pdfs                         # extrae texto de PDFs referenciados
    python cli.py update --aggressive --no-dry-run     # flujo completo agresivo con push
"""

from __future__ import annotations

import argparse
import io
import logging
import sys
from pathlib import Path

# ─── Windows UTF-8 console fix ───────────────────────────────────────────────
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding="utf-8", errors="replace"
        )
    except AttributeError:
        pass  # En algunos entornos stdout no tiene .buffer

# ─── Logging setup (antes de imports de módulos) ────────────────────────────
def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s"
    logging.basicConfig(
        level=level,
        format=fmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )
    # Silenciar librerías ruidosas
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("charset_normalizer").setLevel(logging.WARNING)

logger = logging.getLogger("cli")


# ─── Sub-comandos ─────────────────────────────────────────────────────────────

def cmd_scrape(args: argparse.Namespace) -> str:
    """Raspa SEC Chile. Con --aggressive usa async+PDF+multi-fuente."""
    aggressive = getattr(args, "aggressive", False)
    concurrency = getattr(args, "concurrency", 8)

    if aggressive:
        logger.info(f"🔥 MODO AGRESIVO — concurrencia: {concurrency}")
        return _scrape_aggressive(args, concurrency)
    else:
        from scraper.sec_scraper import SECScraper
        logger.info("🕷️  Scraping de SEC Chile (modo normal)...")
        scraper = SECScraper()
        if getattr(args, "section", None):
            records = scraper.scrape_section(args.section)
        else:
            records = scraper.scrape_all(bess_only=getattr(args, "bess_only", False))
        path = scraper.save(records)
        logger.info(f"✅ Scraping completo. {len(records)} documentos → {path}")
        return path


def _scrape_aggressive(args: argparse.Namespace, concurrency: int) -> str:
    """Pipeline agresivo: async SEC + multi-fuente + PDF extraction."""
    import json
    from datetime import datetime, timezone

    from config import RAW_DIR

    all_records: list[dict] = []

    # 1. Async SEC scraper
    try:
        from scraper.async_scraper import AsyncSECScraper
        logger.info(f"[1/3] ⚡ Async SEC scraper (concurrencia={concurrency})...")
        async_scraper = AsyncSECScraper(
            max_concurrency=concurrency,
            delay_between=0.3,
            follow_depth=2,
        )
        records = async_scraper.scrape_all(bess_only=getattr(args, "bess_only", False))
        logger.info(f"        → {len(records)} docs de sec.cl")
        all_records.extend(records)
    except ImportError:
        logger.warning("aiohttp no instalado → usando scraper normal. pip install aiohttp")
        from scraper.sec_scraper import SECScraper
        scraper = SECScraper()
        records = scraper.scrape_all(bess_only=getattr(args, "bess_only", False))
        all_records.extend(records)

    # 2. Multi-source scraper (coordinador, bcn, minenergia, cne)
    try:
        from scraper.multi_source_scraper import MultiSourceScraper
        logger.info("[2/3] 🌐 Multi-source scraper (coordinador.cl, bcn.cl, minenergia.cl, cne.cl)...")
        multi = MultiSourceScraper(max_workers=4, delay=0.5)
        extra = multi.scrape_all_sources()
        logger.info(f"        → {len(extra)} docs adicionales")
        all_records.extend(extra)
    except Exception as exc:
        logger.warning(f"Multi-source error: {exc}")

    # 3. PDF extractor sobre records con pdf_links
    try:
        from scraper.pdf_extractor import PDFExtractor
        logger.info("[3/3] 📄 Extrayendo texto de PDFs normativos...")
        extractor = PDFExtractor(cache=True)
        if extractor.is_available():
            all_records = extractor.extract_bess_relevant_only(all_records)
        else:
            logger.info("        → sin backend PDF (pip install pypdf)")
    except Exception as exc:
        logger.warning(f"PDF extractor error: {exc}")

    # Deduplicar por ID
    seen_ids: set[str] = set()
    deduped = []
    for r in all_records:
        if r["id"] not in seen_ids:
            seen_ids.add(r["id"])
            deduped.append(r)

    deduped.sort(key=lambda r: r.get("relevance_score", 0), reverse=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = RAW_DIR / f"sec_aggressive_{ts}.json"
    payload = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "total_records": len(deduped),
        "bess_relevant_count": sum(1 for r in deduped if r.get("bess_relevant")),
        "sections_scraped": list({r.get("section", "?") for r in deduped}),
        "sources": list({r.get("source", "sec") for r in deduped}),
        "mode": "aggressive",
        "records": deduped,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        f"✅ Modo agresivo completo: {len(deduped)} docs únicos "
        f"({payload['bess_relevant_count']} BESS) → {path}"
    )
    return str(path)


def cmd_scrape_all(args: argparse.Namespace) -> str:
    """Raspa SOLO las fuentes adicionales (coordinador, bcn, minenergia, cne)."""
    from scraper.multi_source_scraper import MultiSourceScraper
    sources = getattr(args, "sources", None)
    logger.info("🌐 Multi-source scraper...")
    multi = MultiSourceScraper(max_workers=getattr(args, "workers", 4))
    records = multi.scrape_all_sources(sources=sources)
    path = multi.save(records)
    logger.info(f"✅ {len(records)} docs → {path}")
    return path


def cmd_extract_pdfs(args: argparse.Namespace) -> None:
    """Extrae texto de los PDFs del último scraping."""
    import json

    from scraper.pdf_extractor import PDFExtractor
    from scraper.sec_scraper import SECScraper

    data_file = getattr(args, "data_file", None)
    if data_file:
        sec_data = SECScraper.load_file(data_file)
    else:
        sec_data = SECScraper.load_latest()
        if sec_data is None:
            logger.error("No hay datos. Ejecuta: python cli.py scrape")
            return

    extractor = PDFExtractor(cache=True)
    if not extractor.is_available():
        logger.error("Sin backend PDF. Instala: pip install pypdf")
        return

    records = sec_data["records"]
    logger.info(f"Extrayendo PDFs de {len(records)} records...")
    enriched = extractor.extract_batch(records)
    sec_data["records"] = enriched
    sec_data["pdf_extracted"] = True

    # Sobreescribir el mismo archivo con datos enriquecidos
    from datetime import datetime, timezone

    from config import RAW_DIR
    out = RAW_DIR / f"sec_pdf_enriched_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(sec_data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"✅ PDFs extraídos. Guardado: {out}")



def cmd_analyze(args: argparse.Namespace) -> tuple[list, dict]:
    """Analiza brechas normativas contra open-bess-edge."""
    from analysis.gap_analyzer import GapAnalyzer
    from scraper.sec_scraper import SECScraper

    # Cargar datos SEC
    if args.data_file:
        logger.info(f"📂 Cargando: {args.data_file}")
        sec_data = SECScraper.load_file(args.data_file)
    else:
        logger.info("📂 Cargando último scraping disponible...")
        sec_data = SECScraper.load_latest()
        if sec_data is None:
            logger.warning("⚠️  No hay datos de scraping. Ejecuta primero: python cli.py scrape")
            logger.warning("   Usando análisis sin datos SEC (brechas conocidas del código BESSAI)")
            sec_data = {"records": [], "total_records": 0, "bess_relevant_count": 0, "scraped_at": "N/A"}

    logger.info("🔍 Analizando brechas normativas...")
    analyzer = GapAnalyzer()
    gaps = analyzer.analyze(sec_data)

    stats = analyzer.summary_stats(gaps)
    logger.info(
        f"✅ Análisis completo: {stats['total']} brechas "
        f"({stats['by_priority']['critical']} 🔴 críticas, "
        f"{stats['by_priority']['medium']} 🟡 medias, "
        f"{stats['by_priority']['low']} 🟢 bajas)"
    )
    return gaps, sec_data


def cmd_report(args: argparse.Namespace) -> tuple[str, str]:
    """Genera reportes Markdown de brechas."""
    from analysis.report_builder import ReportBuilder

    gaps, sec_data = cmd_analyze(args)

    logger.info("📄 Generando reportes Markdown...")
    builder = ReportBuilder()
    full_path, summary_path = builder.save(gaps, sec_data)

    logger.info(f"✅ Reporte completo: {full_path}")
    logger.info(f"✅ Resumen ejecutivo: {summary_path}")

    if args.print:
        print("\n" + "=" * 80)
        print(Path(summary_path).read_text(encoding="utf-8"))
        print("=" * 80)

    return full_path, summary_path


def cmd_publish(args: argparse.Namespace) -> None:
    """Publica reportes al repositorio open-bess-edge."""
    from config import RAW_DIR, REPORTS_DIR
    from publisher.github_publisher import GitHubPublisher

    # Buscar reportes más recientes
    full_reports = sorted(REPORTS_DIR.glob("gap_analysis_*.md"), reverse=True)
    summaries = sorted(REPORTS_DIR.glob("gap_summary_*.md"), reverse=True)
    raw_files = sorted(RAW_DIR.glob("sec_*.json"), reverse=True)

    if not full_reports or not summaries:
        logger.error(
            "❌ No hay reportes generados. Ejecuta primero: python cli.py report"
        )
        sys.exit(1)

    full_path = str(full_reports[0])
    summary_path = str(summaries[0])
    raw_path = str(raw_files[0]) if raw_files else None

    logger.info(f"📁 Reporte a publicar: {full_reports[0].name}")
    logger.info(f"📁 Resumen a publicar: {summaries[0].name}")
    if raw_path:
        logger.info(f"📁 Datos crudos: {Path(raw_path).name}")

    pub = GitHubPublisher(dry_run=args.dry_run)
    results = pub.publish(full_path, summary_path, raw_path)

    if args.dry_run:
        logger.info("🧪 Dry-run completado. Usa --no-dry-run para publicar de verdad.")
    else:
        pr = results.get("pull_request", {})
        pr_url = pr.get("html_url", "N/A")
        logger.info(f"🚀 PR abierto: {pr_url}")

def cmd_publish_all(args: argparse.Namespace) -> None:
    """Publica TODO al repo: reportes + BEPs + código + workflow."""
    from publisher.full_project_publisher import FullProjectPublisher

    pub = FullProjectPublisher(dry_run=args.dry_run)
    results = pub.publish_all()

    if args.dry_run:
        n = len(results["files_published"])
        logger.info(f"[DRY-RUN] Se publicarían {n} archivos al repo.")
        logger.info("Usa --no-dry-run para publicar de verdad.")
    else:
        pr = results.get("pull_request", {})
        logger.info(f"PR abierto: {pr.get('html_url', 'N/A')}")


def cmd_update(args: argparse.Namespace) -> None:
    """Flujo completo: scrape → analyze → report → (BEPs) → publish ALL."""
    aggressive = getattr(args, "aggressive", False)
    logger.info(f"🔄 Flujo completo {'[AGRESIVO]' if aggressive else ''}...")



    # 1. Scrape
    logger.info("\n[1/5] Scraping...")
    if hasattr(args, "data_file") and args.data_file:
        raw_path = args.data_file
        logger.info(f"  Usando datos existentes: {raw_path}")
    else:
        raw_path = cmd_scrape(args)

    # 2. Analyze
    logger.info("\n[2/5] Analizando brechas...")
    args.data_file = raw_path
    gaps, sec_data = cmd_analyze(args)

    # 3. Report
    logger.info("\n[3/5] Generando reportes...")
    from analysis.report_builder import ReportBuilder
    builder = ReportBuilder()
    full_path, summary_path = builder.save(gaps, sec_data)

    # 4. BEPs para críticas
    logger.info("\n[4/5] Generando BEPs para brechas críticas...")
    try:
        from config import RAW_DIR
        from scripts.bep_generator import run as bep_run
        bep_out = RAW_DIR.parent / "data" / "beps"
        bep_run(bep_out, raw_path)
    except Exception as exc:
        logger.warning(f"BEP generator: {exc}")


    # 5. Publish ALL — reportes + BEPs + código completo
    logger.info("\n[5/5] Publicando TODO al repo (reportes + BEPs + código + workflow)...")
    from publisher.full_project_publisher import FullProjectPublisher
    pub = FullProjectPublisher(dry_run=args.dry_run)
    results = pub.publish_all()

    if not args.dry_run:
        pr_url = results.get("pull_request", {}).get("html_url", "N/A")
        logger.info(f"\n✅ ¡Todo publicado! PR: {pr_url}")
    else:
        n = len(results["files_published"])
        logger.info(f"\n✅ [DRY-RUN] {n} archivos listos para publicar. Usa --no-dry-run.")


# ─── Parser ──────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sec-bess-ingestor",
        description=(
            "🇨🇱 SEC Chile Mega-Scraper + Analizador de Brechas Normativas\n"
            "Para el repositorio open-bess-edge (BESSAI Edge Gateway)"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  python cli.py scrape\n"
            "  python cli.py scrape --section normativa --bess-only\n"
            "  python cli.py analyze\n"
            "  python cli.py report --print\n"
            "  python cli.py publish --dry-run\n"
            "  python cli.py update --dry-run\n"
        ),
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Logging detallado (DEBUG)"
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # ── scrape ────────────────────────────────────────────────────────────
    p_scrape = sub.add_parser("scrape", help="Raspa el sitio de SEC Chile")
    p_scrape.add_argument(
        "--section", metavar="KEY",
        help=("Sección específica a raspar. Keys: "
              "normativa, resoluciones_exentas, circulares, reglamentos, "
              "energias_renovables, noticias, fiscalizacion, sanciones")
    )
    p_scrape.add_argument(
        "--bess-only", action="store_true",
        help="Solo guardar documentos relevantes a BESS/ERNC"
    )
    p_scrape.add_argument(
        "--aggressive", "-A", action="store_true",
        help="MODO AGRESIVO: async 8x concurrente + multi-fuente + extraccion PDF"
    )
    p_scrape.add_argument(
        "--concurrency", "-C", type=int, default=8, metavar="N",
        help="Nivel de concurrencia async (default: 8, max recomendado: 16)"
    )

    # ── scrape-all ────────────────────────────────────────────────────────
    p_scrape_all = sub.add_parser(
        "scrape-all",
        help="Raspa fuentes adicionales: coordinador.cl, bcn.cl, minenergia.cl, cne.cl"
    )
    p_scrape_all.add_argument(
        "--sources", nargs="+",
        metavar="SOURCE",
        help="Fuentes a incluir (coordinador, bcn, minenergia, cne). Default: todas."
    )
    p_scrape_all.add_argument(
        "--workers", type=int, default=4,
        help="Workers paralelos (default: 4)"
    )

    # ── extract-pdfs ──────────────────────────────────────────────────────
    p_pdfs = sub.add_parser(
        "extract-pdfs",
        help="Extrae texto de PDFs del último scraping (requiere: pip install pypdf)"
    )
    p_pdfs.add_argument(
        "--data-file", "--data", metavar="PATH",
        help="Archivo JSON de scraping (default: más reciente)"
    )


    # ── analyze ───────────────────────────────────────────────────────────
    p_analyze = sub.add_parser(
        "analyze", help="Analiza brechas normativas contra open-bess-edge"
    )
    p_analyze.add_argument(
        "--data-file", "--data", metavar="PATH",
        help="Ruta a un archivo JSON de scraping específico (por defecto: más reciente)"
    )

    # ── report ────────────────────────────────────────────────────────────
    p_report = sub.add_parser("report", help="Genera reporte Markdown de brechas")
    p_report.add_argument(
        "--data-file", "--data", metavar="PATH",
        help="Ruta a archivo JSON de scraping (por defecto: más reciente)"
    )
    p_report.add_argument(
        "--print", "-p", action="store_true",
        help="Imprimir el resumen por pantalla"
    )

    # ── publish --------------------------------------------------------
    p_publish = sub.add_parser(
        "publish", help="Publica reportes (gap_analysis + resumen) al repo via GitHub API"
    )
    p_publish.add_argument(
        "--dry-run", action="store_true", default=True,
        help="Simula publicación sin hacer push (default: True)"
    )
    p_publish.add_argument(
        "--no-dry-run", dest="dry_run", action="store_false",
        help="Publica de verdad al repositorio (requiere GITHUB_TOKEN)"
    )

    # ── publish-all --------------------------------------------------------
    p_publish_all = sub.add_parser(
        "publish-all",
        help="Publica TODO: reportes + BEPs + código sec-bess-ingestor + workflow"
    )
    p_publish_all.add_argument(
        "--dry-run", action="store_true", default=True,
        help="Simula publicación sin hacer push (default: True)"
    )
    p_publish_all.add_argument(
        "--no-dry-run", dest="dry_run", action="store_false",
        help="Publica TODO de verdad (requiere GITHUB_TOKEN con scope repo)"
    )


    # ── update ────────────────────────────────────────────────────────────
    p_update = sub.add_parser(
        "update", help="Flujo completo: scrape → analyze → report → publish"
    )
    p_update.add_argument(
        "--dry-run", action="store_true", default=True,
        help="Simula publicación (default: True)"
    )
    p_update.add_argument(
        "--no-dry-run", dest="dry_run", action="store_false",
        help="Ejecuta publicación real al repo"
    )
    p_update.add_argument(
        "--bess-only", action="store_true",
        help="Solo documentos BESS relevantes"
    )
    p_update.add_argument(
        "--section", metavar="KEY",
        help="Raspar solo sección específica"
    )
    p_update.add_argument(
        "--data-file", "--data", metavar="PATH",
        help="Usar datos existentes (omite scraping)"
    )
    p_update.add_argument(
        "--aggressive", "-A", action="store_true",
        help="Modo agresivo: async + multi-fuente + PDF"
    )
    p_update.add_argument(
        "--concurrency", "-C", type=int, default=8, metavar="N",
        help="Concurrencia async (default: 8)"
    )

    return parser


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    _setup_logging(args.verbose)

    dispatch = {
        "scrape": cmd_scrape,
        "scrape-all": cmd_scrape_all,
        "extract-pdfs": cmd_extract_pdfs,
        "analyze": cmd_analyze,
        "report": cmd_report,
        "publish": cmd_publish,
        "publish-all": cmd_publish_all,
        "update": cmd_update,
    }

    try:
        dispatch[args.command](args)
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrumpido por el usuario.")
        sys.exit(0)
    except Exception as exc:
        logger.error(f"❌ Error: {exc}", exc_info=args.verbose)
        sys.exit(1)


if __name__ == "__main__":
    main()
