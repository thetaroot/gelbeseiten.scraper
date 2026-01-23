#!/usr/bin/env python3
"""
Gelbe Seiten Lead Scraper - CLI Entry Point

Findet Unternehmen ohne/mit veralteter Website für Cold Outreach.
"""

import sys
import argparse
import logging
import json
import time
from pathlib import Path
from datetime import datetime
from typing import List, Optional

# Projekt-Root zum Path hinzufügen
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import Settings, WebsiteCheckDepth, OutputFormat, DataSource
from config.branchen import BRANCHEN_LISTE, BRANCHEN_KATEGORIEN, get_branchen, get_kategorien
from src.pipeline.orchestrator import Pipeline
from src.pipeline.aggregator import LeadAggregator
from src.export.json_export import JSONExporter
from src.export.csv_export import CSVExporter
from src.models.lead import Lead


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
  %(prog)s --all-branchen --stadt "Essen" --stealth --duration 1440
  %(prog)s --kategorie handwerk --stadt "Köln" --stealth --duration 720
        """
    )

    # Pflicht-Parameter
    required = parser.add_argument_group("Pflicht-Parameter")
    required.add_argument(
        "--branche", "-b",
        type=str,
        required=False,
        help="Suchbegriff/Branche (z.B. 'Friseur', 'Zahnarzt', 'Restaurant')"
    )
    required.add_argument(
        "--stadt", "-s",
        type=str,
        required=True,
        help="Stadt/Region (z.B. 'Berlin', 'München', 'Hamburg')"
    )
    required.add_argument(
        "--all-branchen",
        action="store_true",
        help="Alle Branchen durchsuchen (maximale Marktabdeckung)"
    )
    required.add_argument(
        "--kategorie", "-k",
        type=str,
        choices=list(BRANCHEN_KATEGORIEN.keys()),
        help=f"Nur bestimmte Kategorie: {', '.join(BRANCHEN_KATEGORIEN.keys())}"
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


def run_multi_branche_scrape(
    branchen: List[str],
    stadt: str,
    args,
    settings_template: Settings
) -> List[Lead]:
    """
    Durchläuft alle Branchen und sammelt Leads.

    Speichert Zwischenergebnisse alle 10 Branchen für den Fall eines Abbruchs.
    Dedupliziert am Ende über alle Branchen hinweg.
    """
    all_leads = []
    aggregator = LeadAggregator()
    total_branchen = len(branchen)
    start_time = time.time()

    # Checkpoint-Datei für Zwischenspeicherung
    stadt_safe = stadt.lower().replace(" ", "_")
    checkpoint_file = Path(f".checkpoint_leads_{stadt_safe}.json")
    processed_branchen_file = Path(f".checkpoint_branchen_{stadt_safe}.json")

    # Bereits verarbeitete Branchen laden (für Fortsetzung nach Abbruch)
    processed_branchen = set()
    if processed_branchen_file.exists():
        try:
            with open(processed_branchen_file, "r") as f:
                processed_branchen = set(json.load(f))
            print(f"\n  Fortsetzung: {len(processed_branchen)} Branchen bereits verarbeitet")
        except:
            pass

    # Bestehende Leads laden
    if checkpoint_file.exists() and processed_branchen:
        try:
            with open(checkpoint_file, "r") as f:
                checkpoint_data = json.load(f)
                # Leads aus Checkpoint rekonstruieren
                for lead_dict in checkpoint_data.get("leads", []):
                    try:
                        lead = Lead(**lead_dict)
                        all_leads.append(lead)
                    except:
                        pass
            print(f"  Fortsetzung: {len(all_leads)} Leads geladen")
        except:
            pass

    print(f"\n  Starte Scan von {total_branchen} Branchen in {stadt}...\n")

    for idx, branche in enumerate(branchen, 1):
        # Bereits verarbeitet?
        if branche in processed_branchen:
            continue

        elapsed = time.time() - start_time
        elapsed_str = f"{int(elapsed // 3600)}h {int((elapsed % 3600) // 60)}m"

        print(f"\n[{idx}/{total_branchen}] {branche} ({elapsed_str} vergangen)")
        print("-" * 50)

        # Settings für diese Branche
        settings = Settings(
            branche=branche,
            stadt=stadt,
            max_leads=settings_template.max_leads,
            max_pages=settings_template.max_pages,
            website_check_depth=settings_template.website_check_depth,
            sources=settings_template.sources,
            verbose=settings_template.verbose,
            debug=settings_template.debug
        )

        # Übernehme alle Einstellungen
        settings.filter = settings_template.filter
        settings.google_maps = settings_template.google_maps
        settings.proxy = settings_template.proxy
        settings.stealth = settings_template.stealth
        settings.export = settings_template.export

        # Pipeline für diese Branche
        pipeline = Pipeline(settings)

        if not args.quiet:
            pipeline.set_progress_callback(print_progress)

        try:
            result = pipeline.run(branche, stadt, settings.max_leads)
            branche_leads = result.leads if result.leads else []

            print(f"\n  → {len(branche_leads)} Leads gefunden")

            # Deduplizierung gegen bestehende Leads
            if branche_leads:
                new_leads = []
                for lead in branche_leads:
                    is_duplicate = False
                    for existing in all_leads:
                        if aggregator._is_duplicate(lead, existing):
                            is_duplicate = True
                            break
                    if not is_duplicate:
                        new_leads.append(lead)

                print(f"  → {len(new_leads)} neue (nicht doppelt)")
                all_leads.extend(new_leads)

        except KeyboardInterrupt:
            print("\n\n  Abbruch durch Benutzer - speichere Zwischenstand...")
            _save_checkpoint(checkpoint_file, processed_branchen_file, all_leads, processed_branchen)
            raise
        except Exception as e:
            print(f"\n  Fehler bei {branche}: {e}")
            if args.debug:
                raise

        # Branche als verarbeitet markieren
        processed_branchen.add(branche)

        # Checkpoint alle 10 Branchen
        if idx % 10 == 0:
            _save_checkpoint(checkpoint_file, processed_branchen_file, all_leads, processed_branchen)
            print(f"\n  [Checkpoint] {len(all_leads)} Leads gespeichert")

    # Checkpoint-Dateien löschen bei Erfolg
    if checkpoint_file.exists():
        checkpoint_file.unlink()
    if processed_branchen_file.exists():
        processed_branchen_file.unlink()

    print(f"\n{'=' * 60}")
    print(f"  MULTI-BRANCHEN SCAN ABGESCHLOSSEN")
    print(f"{'=' * 60}")
    print(f"  Branchen durchsucht:  {len(processed_branchen)}")
    print(f"  Gesamt-Leads:         {len(all_leads)}")
    print(f"  Dauer:                {int((time.time() - start_time) // 3600)}h {int(((time.time() - start_time) % 3600) // 60)}m")
    print(f"{'=' * 60}")

    return all_leads


def _save_checkpoint(
    checkpoint_file: Path,
    processed_file: Path,
    leads: List[Lead],
    processed: set
) -> None:
    """Speichert Zwischenstand für Fortsetzung nach Abbruch."""
    # Leads speichern
    leads_data = []
    for lead in leads:
        try:
            leads_data.append(lead.model_dump())
        except:
            leads_data.append(lead.dict())

    with open(checkpoint_file, "w", encoding="utf-8") as f:
        json.dump({"leads": leads_data}, f, ensure_ascii=False, default=str)

    # Verarbeitete Branchen speichern
    with open(processed_file, "w", encoding="utf-8") as f:
        json.dump(list(processed), f, ensure_ascii=False)


def main() -> int:
    """Hauptfunktion."""
    parser = create_parser()
    args = parser.parse_args()

    # Validierung: entweder --branche oder --all-branchen/--kategorie
    if not args.branche and not args.all_branchen and not args.kategorie:
        parser.error("Entweder --branche, --all-branchen oder --kategorie angeben")

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
        hours = args.duration // 60
        mins = args.duration % 60
        stealth_info = f" (Stealth: {hours}h {mins}m)" if hours else f" (Stealth: {mins}m)"

    # Multi-Branchen Modus?
    multi_branchen_mode = args.all_branchen or args.kategorie
    branchen_liste = []

    if args.all_branchen:
        branchen_liste = BRANCHEN_LISTE
        branchen_display = f"ALLE ({len(branchen_liste)} Branchen)"
    elif args.kategorie:
        branchen_liste = get_branchen(args.kategorie)
        branchen_display = f"{args.kategorie.upper()} ({len(branchen_liste)} Branchen)"
    else:
        branchen_display = args.branche

    # Banner
    if not args.quiet:
        print("\n" + "=" * 60)
        print("  GELBE SEITEN LEAD SCRAPER")
        print("=" * 60)
        print(f"  Branche:        {branchen_display}")
        print(f"  Stadt:          {args.stadt}")
        if not multi_branchen_mode:
            print(f"  Max. Leads:     {args.limit}")
        else:
            print(f"  Max/Branche:    {args.limit}")
        print(f"  Quellen:        {sources_display}{stealth_info}")
        print(f"  Website-Check:  {args.website_check}")
        if args.stealth:
            print(f"  Stealth-Modus:  Aktiv (max. {args.duration} Min)")
        if multi_branchen_mode:
            print(f"  Modus:          Multi-Branchen (maximale Abdeckung)")
        print("=" * 60 + "\n")

    # Settings erstellen (Template für Multi-Branchen)
    settings = Settings(
        branche=args.branche or "Multi",
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

    # Multi-Branchen oder Single-Branche Modus
    if multi_branchen_mode:
        # Multi-Branchen Scan
        try:
            leads = run_multi_branche_scrape(branchen_liste, args.stadt, args, settings)
        except KeyboardInterrupt:
            print("\n\nAbgebrochen durch Benutzer. Zwischenstand wurde gespeichert.")
            print("Starte erneut mit den gleichen Parametern um fortzusetzen.")
            return 1
        except Exception as e:
            logging.error(f"Pipeline-Fehler: {e}")
            if args.debug:
                raise
            return 1

        if not leads:
            print("\nKeine Leads gefunden.")
            return 1

        # Für Export: Dummy-Result erstellen
        class MultiResult:
            def __init__(self, leads_list):
                self.leads = leads_list
                self.dauer_sekunden = 0

        result = MultiResult(leads)
        stats = {
            "multi_branchen": {
                "branchen_count": len(branchen_liste),
                "total_leads": len(leads)
            }
        }

    else:
        # Single-Branche Modus (wie bisher)
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

        if not result.leads:
            print("\nKeine Leads gefunden.")
            return 1

        stats = pipeline.stats.to_dict()

    # Output-Pfad bestimmen
    if args.output:
        output_base = Path(args.output).stem
        output_dir = Path(args.output).parent or Path(".")
    else:
        stadt_safe = args.stadt.lower().replace(" ", "_")
        if multi_branchen_mode:
            if args.kategorie:
                output_base = f"leads_{args.kategorie}_{stadt_safe}"
            else:
                output_base = f"leads_alle_branchen_{stadt_safe}"
        else:
            branche_safe = args.branche.lower().replace(" ", "_").replace("/", "_")
            output_base = f"leads_{branche_safe}_{stadt_safe}"
        output_dir = Path(".")

    # Export
    exported_files = []
    branche_for_export = "Alle Branchen" if multi_branchen_mode else args.branche

    if args.format in ["json", "both"]:
        json_path = output_dir / f"{output_base}.json"
        json_exporter = JSONExporter(settings.export)
        json_exporter.export(result, json_path, branche_for_export, args.stadt, settings)
        exported_files.append(str(json_path))

    if args.format in ["csv", "both"]:
        csv_path = output_dir / f"{output_base}.csv"
        csv_exporter = CSVExporter(settings.export)
        csv_exporter.export(result, csv_path)
        exported_files.append(str(csv_path))

    # Zusammenfassung
    if not args.quiet:
        if multi_branchen_mode:
            print(f"\n{'=' * 60}")
            print("EXPORT ABGESCHLOSSEN")
            print(f"{'=' * 60}")
            print(f"  Leads exportiert:  {len(result.leads)}")
        else:
            print_summary(stats, len(result.leads), result.dauer_sekunden)

        print(f"\nExportiert nach:")
        for f in exported_files:
            print(f"  → {f}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
