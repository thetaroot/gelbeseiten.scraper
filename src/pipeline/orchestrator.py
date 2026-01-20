"""
Pipeline Orchestrator - Hauptsteuerung des Scraping-Prozesses.

Koordiniert alle Komponenten: Scraper, Analyzer, Filter, Export.
"""

import logging
import time
from typing import List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

from src.client.http import HTTPClient
from src.client.rate_limiter import RateLimiter
from src.scraper.gelbe_seiten import GelbeSeitenScraper
from src.scraper.website_scanner import WebsiteScanner, ScanResult
from src.pipeline.filters import LeadFilter
from src.models.lead import Lead, WebsiteStatus, ScrapingResult
from config.settings import Settings, WebsiteCheckDepth


logger = logging.getLogger(__name__)


@dataclass
class PipelineStats:
    """Statistiken des Pipeline-Durchlaufs."""
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None

    # Stage 1
    gs_pages_scraped: int = 0
    gs_listings_found: int = 0
    gs_leads_created: int = 0

    # Stage 2
    websites_checked: int = 0
    websites_old: int = 0
    websites_modern: int = 0
    websites_unknown: int = 0
    websites_no_website: int = 0

    # Final
    leads_after_filter: int = 0
    leads_exported: int = 0

    @property
    def duration_seconds(self) -> float:
        """Dauer in Sekunden."""
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()

    def to_dict(self) -> dict:
        """Konvertiert zu Dictionary."""
        return {
            "duration_seconds": self.duration_seconds,
            "stage1": {
                "pages_scraped": self.gs_pages_scraped,
                "listings_found": self.gs_listings_found,
                "leads_created": self.gs_leads_created
            },
            "stage2": {
                "websites_checked": self.websites_checked,
                "websites_old": self.websites_old,
                "websites_modern": self.websites_modern,
                "websites_unknown": self.websites_unknown,
                "no_website": self.websites_no_website
            },
            "final": {
                "leads_after_filter": self.leads_after_filter,
                "leads_exported": self.leads_exported
            }
        }


class Pipeline:
    """
    Orchestriert den gesamten Scraping-Prozess.

    Flow:
    1. Gelbe Seiten scrapen → Leads mit Basis-Daten
    2. Leads ohne Website direkt markieren
    3. Leads mit Website → Website-Scan
    4. Filter anwenden
    5. Ergebnis zurückgeben
    """

    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialisiert die Pipeline.

        Args:
            settings: Pipeline-Einstellungen.
        """
        self._settings = settings or Settings()

        # Komponenten initialisieren
        self._rate_limiter = RateLimiter(self._settings.rate_limit)
        self._http_client = HTTPClient(self._settings, self._rate_limiter)
        self._gs_scraper = GelbeSeitenScraper(self._http_client, self._settings)
        self._website_scanner = WebsiteScanner(self._http_client, self._settings)
        self._lead_filter = LeadFilter(self._settings.filter)

        # Callbacks
        self._progress_callback: Optional[Callable[[str, int, int], None]] = None

        # Stats
        self._stats = PipelineStats()

    def run(
        self,
        branche: str,
        stadt: str,
        max_leads: Optional[int] = None
    ) -> ScrapingResult:
        """
        Führt die komplette Pipeline aus.

        Args:
            branche: Suchbegriff/Branche.
            stadt: Stadt/Region.
            max_leads: Maximale Anzahl Leads (überschreibt Settings).

        Returns:
            ScrapingResult mit allen Leads und Statistiken.
        """
        if max_leads is None:
            max_leads = self._settings.max_leads

        self._stats = PipelineStats()
        result = ScrapingResult()

        logger.info(f"=== Pipeline Start: '{branche}' in '{stadt}' ===")
        logger.info(f"Max Leads: {max_leads}, Website-Check: {self._settings.website_check_depth.value}")

        try:
            # === Stage 1: Gelbe Seiten Scraping ===
            self._report_progress("Stage 1: Gelbe Seiten scrapen", 0, 100)
            leads = self._stage1_scrape_gelbe_seiten(branche, stadt, max_leads)
            logger.info(f"Stage 1 abgeschlossen: {len(leads)} Leads")

            if not leads:
                logger.warning("Keine Leads gefunden - Pipeline beendet")
                result.fehler.append("Keine Leads in Stage 1 gefunden")
                return result

            # === Stage 2: Website-Check ===
            self._report_progress("Stage 2: Website-Check", 30, 100)
            leads = self._stage2_check_websites(leads)
            logger.info(f"Stage 2 abgeschlossen: {len(leads)} Leads geprüft")

            # === Stage 3: Filterung ===
            self._report_progress("Stage 3: Filterung", 80, 100)
            leads = self._stage3_filter_leads(leads)
            logger.info(f"Stage 3 abgeschlossen: {len(leads)} Leads nach Filter")

            # === Ergebnis zusammenstellen ===
            self._report_progress("Fertigstellung", 95, 100)

            result.leads = leads
            result.total_gefunden = self._stats.gs_listings_found
            result.total_gefiltert = len(leads)
            result.seiten_gescraped = self._stats.gs_pages_scraped
            result.dauer_sekunden = self._stats.duration_seconds

            self._stats.leads_exported = len(leads)
            self._stats.end_time = datetime.now()

            self._report_progress("Fertig", 100, 100)
            logger.info(f"=== Pipeline abgeschlossen: {len(leads)} Leads in {self._stats.duration_seconds:.1f}s ===")

            return result

        except Exception as e:
            logger.error(f"Pipeline-Fehler: {e}")
            result.fehler.append(str(e))
            self._stats.end_time = datetime.now()
            return result

        finally:
            self._http_client.close()

    def _stage1_scrape_gelbe_seiten(
        self,
        branche: str,
        stadt: str,
        max_leads: int
    ) -> List[Lead]:
        """Stage 1: Scrape Gelbe Seiten."""
        logger.info("Stage 1: Starte Gelbe Seiten Scraping...")

        # Scrape mit Details
        leads = self._gs_scraper.scrape_leads(
            branche=branche,
            stadt=stadt,
            max_leads=max_leads,
            include_details=True
        )

        # Stats aktualisieren
        gs_stats = self._gs_scraper.stats
        self._stats.gs_pages_scraped = gs_stats["pages_scraped"]
        self._stats.gs_listings_found = gs_stats["listings_found"]
        self._stats.gs_leads_created = len(leads)

        return leads

    def _stage2_check_websites(self, leads: List[Lead]) -> List[Lead]:
        """Stage 2: Website-Alters-Check."""
        logger.info("Stage 2: Starte Website-Checks...")

        total = len(leads)
        checked = 0

        for i, lead in enumerate(leads):
            # Progress
            if (i + 1) % 10 == 0:
                progress = 30 + int((i / total) * 50)  # 30-80%
                self._report_progress(f"Website-Check {i+1}/{total}", progress, 100)

            # Leads ohne Website
            if not lead.website_url:
                lead.website_analyse.status = WebsiteStatus.KEINE
                self._stats.websites_no_website += 1
                logger.debug(f"Lead '{lead.firmenname}': keine Website")
                continue

            # Website-Scan
            try:
                scan_result = self._website_scanner.scan(
                    lead.website_url,
                    self._settings.website_check_depth
                )

                # Ergebnis auf Lead anwenden
                self._website_scanner.update_lead_analysis(
                    lead.website_analyse,
                    scan_result
                )

                # Stats aktualisieren
                self._stats.websites_checked += 1
                checked += 1

                if scan_result.result == ScanResult.ALT:
                    self._stats.websites_old += 1
                    logger.debug(f"Lead '{lead.firmenname}': Website ALT - {scan_result.signals[:3]}")
                elif scan_result.result == ScanResult.MODERN:
                    self._stats.websites_modern += 1
                    logger.debug(f"Lead '{lead.firmenname}': Website MODERN")
                elif scan_result.result == ScanResult.BAUKASTEN:
                    self._stats.websites_old += 1  # Baukasten = alt
                    logger.debug(f"Lead '{lead.firmenname}': Baukasten")
                else:
                    self._stats.websites_unknown += 1
                    logger.debug(f"Lead '{lead.firmenname}': Website UNKLAR")

            except Exception as e:
                logger.warning(f"Website-Check Fehler für '{lead.firmenname}': {e}")
                lead.website_analyse.status = WebsiteStatus.UNBEKANNT
                lead.website_analyse.fehler = str(e)
                self._stats.websites_unknown += 1

        logger.info(
            f"Website-Checks: {checked} geprüft, "
            f"{self._stats.websites_old} alt, "
            f"{self._stats.websites_modern} modern, "
            f"{self._stats.websites_no_website} ohne Website"
        )

        return leads

    def _stage3_filter_leads(self, leads: List[Lead]) -> List[Lead]:
        """Stage 3: Filterung."""
        logger.info("Stage 3: Starte Filterung...")

        # Filtern
        filtered = self._lead_filter.filter_leads(leads)

        # Nach Qualität sortieren
        filtered = self._lead_filter.sort_leads(filtered, by="quality", reverse=True)

        self._stats.leads_after_filter = len(filtered)

        # Filter-Stats loggen
        filter_stats = self._lead_filter.stats
        logger.info(
            f"Filter-Ergebnis: {filter_stats['total_included']}/{filter_stats['total_processed']} inkludiert"
        )
        if filter_stats['exclusion_reasons']:
            logger.debug(f"Ausschluss-Gründe: {filter_stats['exclusion_reasons']}")

        return filtered

    def set_progress_callback(
        self,
        callback: Callable[[str, int, int], None]
    ) -> None:
        """
        Setzt Callback für Progress-Updates.

        Args:
            callback: Funktion mit Signatur (message, current, total).
        """
        self._progress_callback = callback

    def _report_progress(self, message: str, current: int, total: int) -> None:
        """Meldet Progress."""
        if self._progress_callback:
            self._progress_callback(message, current, total)

    @property
    def stats(self) -> PipelineStats:
        """Gibt Pipeline-Statistiken zurück."""
        return self._stats

    def get_component_stats(self) -> dict:
        """Gibt detaillierte Statistiken aller Komponenten zurück."""
        return {
            "pipeline": self._stats.to_dict(),
            "rate_limiter": self._rate_limiter.get_stats(),
            "http_client": self._http_client.get_stats(),
            "gs_scraper": self._gs_scraper.stats,
            "website_scanner": self._website_scanner.stats,
            "lead_filter": self._lead_filter.stats
        }


def run_pipeline(
    branche: str,
    stadt: str,
    max_leads: int = 100,
    website_check: str = "normal",
    min_quality: int = 0,
    include_modern: bool = False,
    verbose: bool = False
) -> ScrapingResult:
    """
    Convenience-Funktion für Pipeline-Ausführung.

    Args:
        branche: Suchbegriff/Branche.
        stadt: Stadt/Region.
        max_leads: Maximale Anzahl Leads.
        website_check: Check-Tiefe ("fast", "normal", "thorough").
        min_quality: Mindest-Qualitätsscore.
        include_modern: Auch moderne Websites inkludieren.
        verbose: Ausführliches Logging.

    Returns:
        ScrapingResult mit Leads.
    """
    # Logging konfigurieren
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # Settings erstellen
    settings = Settings.from_cli_args(
        branche=branche,
        stadt=stadt,
        limit=max_leads,
        website_check=website_check,
        min_quality=min_quality,
        include_modern=include_modern,
        verbose=verbose
    )

    # Pipeline ausführen
    pipeline = Pipeline(settings)
    return pipeline.run(branche, stadt, max_leads)
