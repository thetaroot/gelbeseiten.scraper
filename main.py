#!/usr/bin/env python3
"""
Gelbe Seiten Lead Scraper - CLI Entry Point

Findet Unternehmen ohne/mit veralteter Website für Cold Outreach.
"""

import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Projekt-Root zum Path hinzufügen
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import Settings, WebsiteCheckDepth, OutputFormat, DataSource
from src.pipeline.orchestrator import Pipeline
from src.export.json_export import JSONExporter
from src.export.csv_export import CSVExporter


def setup_logging(verbose: bool = False, debug: bool = False) -> None:
    """Konfiguriert das Logging."""
    if debug:
        level = logging.DEBUG
        format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    elif verbose:
        level = logging.INFO
        format_str = "%(asctime)s - %(levelname)s - %(message)s"
    else:
        level = logging.WARNING
        format_str = "%(levelname)s: %(message)s"

    logging.basicConfig(
        level=level,
        format=format_str,
        handlers=[logging.StreamHandler(sys.stdout)]
    )


def create_parser() -> argparse.ArgumentParser:
    """Erstellt den Argument Parser."""
    parser = argparse.ArgumentParser(
        prog="gelbe-seiten-scraper",
        description="""
Gelbe Seiten Lead Scraper - Findet Unternehmen ohne/mit veralteter Website.

Scraped gelbeseiten.de nach Branche und Stadt, analysiert Websites auf Alter,
und exportiert qualifizierte Leads für Cold Outreach.
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  %(prog)s --branche "Friseur" --stadt "Berlin"
  %(prog)s --branche "Zahnarzt" --stadt "München" --limit 200 --format json
  %(prog)s --branche "Restaurant" --stadt "Hamburg" --website-check thorough
        """
    )

    # Pflicht-Parameter
    required = parser.add_argument_group("Pflicht-Parameter")
    required.add_argument(
        "--branche", "-b",
        type=str,
        required=True,
        help="Suchbegriff/Branche (z.B. 'Friseur', 'Zahnarzt', 'Restaurant')"
    )
    required.add_argument(
        "--stadt", "-s",
        type=str,
        required=True,
        help="Stadt/Region (z.B. 'Berlin', 'München', 'Hamburg')"
    )

    # Such-Optionen
    search = parser.add_argument_group("Such-Optionen")
    search.add_argument(
        "--limit", "-l",
        type=int,
        default=100,
        help="Maximale Anzahl Leads (default: 100)"
    )
    search.add_argument(
        "--max-pages",
        type=int,
        default=50,
        help="Maximale Anzahl Suchergebnis-Seiten (default: 50)"
    )
    search.add_argument(
        "--sources", "-src",
        type=str,
        choices=["gelbe-seiten", "google-maps", "all"],
        default="gelbe-seiten",
        help="Datenquellen: gelbe-seiten, google-maps, all (default: gelbe-seiten)"
    )

    # Google Maps Optionen
    gm = parser.add_argument_group("Google Maps Optionen")
    gm.add_argument(
        "--use-proxy",
        action="store_true",
        help="Proxy-Rotation für Google Maps aktivieren"
    )
    gm.add_argument(
        "--proxy-file",
        type=str,
        help="Pfad zur Proxy-Liste (Format: host:port oder type://user:pass@host:port)"
    )
    gm.add_argument(
        "--no-headless",
        action="store_true",
        help="Browser sichtbar anzeigen (für Debugging)"
    )

    # Stealth-Modus (sicheres Scraping ohne Proxy)
    stealth = parser.add_argument_group("Stealth-Modus (sicheres Scraping ohne Proxy)")
    stealth.add_argument(
        "--stealth",
        action="store_true",
        help="Aktiviert Stealth-Modus mit sehr konservativen Delays (kein Proxy nötig)"
    )
    stealth.add_argument(
        "--duration",
        type=int,
        default=180,
        help="Maximale Laufzeit in Minuten für Stealth-Modus (default: 180)"
    )

    # Website-Check
    website = parser.add_argument_group("Website-Analyse")
    website.add_argument(
        "--website-check", "-w",
        type=str,
        choices=["fast", "normal", "thorough"],
        default="normal",
        help="Tiefe der Website-Analyse (default: normal)"
    )
    website.add_argument(
        "--include-modern",
        action="store_true",
        help="Auch Unternehmen mit modernen Websites inkludieren"
    )

    # Filter
    filters = parser.add_argument_group("Filter-Optionen")
    filters.add_argument(
        "--min-quality",
        type=int,
        default=0,
        help="Mindest-Qualitätsscore 0-100 (default: 0)"
    )
    filters.add_argument(
        "--require-phone",
        action="store_true",
        help="Nur Leads mit Telefonnummer"
    )
    filters.add_argument(
        "--require-email",
        action="store_true",
        help="Nur Leads mit E-Mail"
    )

    # Export
    export = parser.add_argument_group("Export-Optionen")
    export.add_argument(
        "--output", "-o",
        type=str,
        help="Output-Dateiname (default: leads_{branche}_{stadt}.json)"
    )
    export.add_argument(
        "--format", "-f",
        type=str,
        choices=["json", "csv", "both"],
        default="json",
        help="Ausgabeformat (default: json)"
    )

    # Logging
    logging_group = parser.add_argument_group("Logging")
    logging_group.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Ausführliche Ausgabe"
    )
    logging_group.add_argument(
        "--debug",
        action="store_true",
        help="Debug-Ausgabe (sehr ausführlich)"
    )
    logging_group.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Nur Fehler ausgeben"
    )

    return parser


def print_progress(message: str, current: int, total: int) -> None:
    """Gibt Progress aus."""
    percent = (current / total) * 100 if total > 0 else 0
    bar_length = 30
    filled = int(bar_length * current / total) if total > 0 else 0
    bar = "█" * filled + "░" * (bar_length - filled)
    print(f"\r{bar} {percent:5.1f}% | {message:<40}", end="", flush=True)


def print_summary(stats: dict, leads_count: int, duration: float) -> None:
    """Gibt Zusammenfassung aus."""
    print("\n")
    print("=" * 60)
    print("ZUSAMMENFASSUNG")
    print("=" * 60)
    print(f"  Leads exportiert:     {leads_count}")
    print(f"  Dauer:                {duration:.1f} Sekunden")
    print("-" * 60)

    # Stage 1a - Gelbe Seiten
    if "stage1a_gelbe_seiten" in stats:
        print("  Stage 1a (Gelbe Seiten):")
        print(f"    Seiten gescraped:   {stats['stage1a_gelbe_seiten']['pages_scraped']}")
        print(f"    Listings gefunden:  {stats['stage1a_gelbe_seiten']['listings_found']}")
    elif "stage1" in stats:
        # Fallback für alte Stats-Struktur
        print("  Stage 1 (Gelbe Seiten):")
        print(f"    Seiten gescraped:   {stats['stage1']['pages_scraped']}")
        print(f"    Listings gefunden:  {stats['stage1']['listings_found']}")

    # Stage 1b - Google Maps
    if "stage1b_google_maps" in stats and stats["stage1b_google_maps"]["listings_found"] > 0:
        print("-" * 60)
        print("  Stage 1b (Google Maps):")
        print(f"    Seiten gescraped:   {stats['stage1b_google_maps']['pages_scraped']}")
        print(f"    Listings gefunden:  {stats['stage1b_google_maps']['listings_found']}")

    # Stage 2 - Aggregation
    if "stage2_aggregation" in stats and stats["stage2_aggregation"]["duplicates_found"] > 0:
        print("-" * 60)
        print("  Stage 2 (Aggregation):")
        print(f"    Duplikate gefunden: {stats['stage2_aggregation']['duplicates_found']}")
        print(f"    Gemergt:            {stats['stage2_aggregation']['merged_leads']}")

    # Stage 3 - Website Check
    ws_key = "stage3_website_check" if "stage3_website_check" in stats else "stage2"
    print("-" * 60)
    print(f"  Stage {'3' if 'stage3_website_check' in stats else '2'} (Website-Check):")
    print(f"    Geprüft:            {stats[ws_key]['websites_checked']}")
    print(f"    Keine Website:      {stats[ws_key]['no_website']}")
    print(f"    Alt/Veraltet:       {stats[ws_key]['websites_old']}")
    print(f"    Modern:             {stats[ws_key]['websites_modern']}")
    print(f"    Unklar:             {stats[ws_key]['websites_unknown']}")
    print("=" * 60)


def main() -> int:
    """Hauptfunktion."""
    parser = create_parser()
    args = parser.parse_args()

    # Logging einrichten
    if args.quiet:
        setup_logging(verbose=False, debug=False)
        logging.disable(logging.CRITICAL)
    else:
        setup_logging(verbose=args.verbose, debug=args.debug)

    # Quellen parsen
    sources = []
    if args.sources == "all":
        sources = [DataSource.GELBE_SEITEN, DataSource.GOOGLE_MAPS]
        sources_display = "Gelbe Seiten + Google Maps"
    elif args.sources == "google-maps":
        sources = [DataSource.GOOGLE_MAPS]
        sources_display = "Google Maps"
    else:
        sources = [DataSource.GELBE_SEITEN]
        sources_display = "Gelbe Seiten"

    # Stealth-Modus Info
    stealth_info = ""
    if args.stealth:
        stealth_info = f" (Stealth: {args.duration} Min)"

    # Banner
    if not args.quiet:
        print("\n" + "=" * 60)
        print("  GELBE SEITEN LEAD SCRAPER")
        print("=" * 60)
        print(f"  Branche:        {args.branche}")
        print(f"  Stadt:          {args.stadt}")
        print(f"  Max. Leads:     {args.limit}")
        print(f"  Quellen:        {sources_display}{stealth_info}")
        print(f"  Website-Check:  {args.website_check}")
        if args.stealth:
            print(f"  Stealth-Modus:  Aktiv (max. {args.duration} Min)")
        print("=" * 60 + "\n")

    # Settings erstellen
    settings = Settings(
        branche=args.branche,
        stadt=args.stadt,
        max_leads=args.limit,
        max_pages=args.max_pages,
        website_check_depth=WebsiteCheckDepth(args.website_check),
        sources=sources,
        verbose=args.verbose,
        debug=args.debug
    )

    # Filter-Einstellungen
    settings.filter.min_quality_score = args.min_quality
    settings.filter.include_modern_website = args.include_modern
    settings.filter.require_phone = args.require_phone
    settings.filter.require_email = args.require_email

    # Google Maps Einstellungen
    settings.google_maps.enabled = DataSource.GOOGLE_MAPS in sources
    settings.google_maps.browser_headless = not args.no_headless
    settings.proxy.enabled = args.use_proxy
    settings.proxy.proxy_file = args.proxy_file

    # Stealth-Modus Einstellungen
    settings.stealth.enabled = args.stealth
    if args.stealth:
        settings.stealth.max_session_duration_minutes = args.duration

    # Export-Einstellungen
    if args.format in ["json", "both"]:
        settings.export.output_format = OutputFormat.JSON
    else:
        settings.export.output_format = OutputFormat.CSV

    # Pipeline ausführen
    pipeline = Pipeline(settings)

    if not args.quiet:
        pipeline.set_progress_callback(print_progress)

    try:
        result = pipeline.run(args.branche, args.stadt, args.limit)
    except KeyboardInterrupt:
        print("\n\nAbgebrochen durch Benutzer.")
        return 1
    except Exception as e:
        logging.error(f"Pipeline-Fehler: {e}")
        if args.debug:
            raise
        return 1

    # Ergebnis prüfen
    if not result.leads:
        print("\nKeine Leads gefunden.")
        return 1

    # Output-Pfad bestimmen
    if args.output:
        output_base = Path(args.output).stem
        output_dir = Path(args.output).parent or Path(".")
    else:
        branche_safe = args.branche.lower().replace(" ", "_").replace("/", "_")
        stadt_safe = args.stadt.lower().replace(" ", "_")
        output_base = f"leads_{branche_safe}_{stadt_safe}"
        output_dir = Path(".")

    # Export
    exported_files = []

    if args.format in ["json", "both"]:
        json_path = output_dir / f"{output_base}.json"
        json_exporter = JSONExporter(settings.export)
        json_exporter.export(result, json_path, args.branche, args.stadt, settings)
        exported_files.append(str(json_path))

    if args.format in ["csv", "both"]:
        csv_path = output_dir / f"{output_base}.csv"
        csv_exporter = CSVExporter(settings.export)
        csv_exporter.export(result, csv_path)
        exported_files.append(str(csv_path))

    # Zusammenfassung
    if not args.quiet:
        stats = pipeline.stats.to_dict()
        print_summary(stats, len(result.leads), result.dauer_sekunden)
        print(f"\nExportiert nach:")
        for f in exported_files:
            print(f"  → {f}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
