"""
Zentrale Konfiguration für den Gelbe Seiten Lead Scraper.

Alle konfigurierbaren Parameter an einem Ort.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
from pathlib import Path


class WebsiteCheckDepth(str, Enum):
    """Tiefe der Website-Überprüfung."""
    FAST = "fast"           # Nur URL-Heuristik
    NORMAL = "normal"       # URL + HEAD Request
    THOROUGH = "thorough"   # URL + HEAD + HTML Scan


class OutputFormat(str, Enum):
    """Ausgabeformat für Export."""
    JSON = "json"
    CSV = "csv"


class DataSource(str, Enum):
    """Datenquellen für Leads."""
    GELBE_SEITEN = "gelbe_seiten"
    GOOGLE_MAPS = "google_maps"
    MERGED = "merged"  # Aus mehreren Quellen kombiniert


@dataclass
class RateLimitConfig:
    """Konfiguration für Rate Limiting."""

    # Gelbe Seiten (strenger)
    gs_min_delay: float = 2.0
    gs_max_delay: float = 4.0
    gs_pause_every_n_requests: int = 20
    gs_pause_min_duration: float = 15.0
    gs_pause_max_duration: float = 30.0
    gs_max_requests_per_minute: int = 15

    # Google Maps (konservativ)
    gm_min_delay: float = 3.0
    gm_max_delay: float = 6.0
    gm_pause_every_n_requests: int = 15
    gm_pause_min_duration: float = 20.0
    gm_pause_max_duration: float = 40.0
    gm_max_requests_per_minute: int = 10

    # Externe Websites (lockerer)
    ext_min_delay: float = 1.0
    ext_max_delay: float = 2.0
    ext_timeout: float = 10.0

    # Retry-Verhalten
    max_retries: int = 3
    backoff_factor: float = 2.0
    retry_status_codes: List[int] = field(default_factory=lambda: [429, 500, 502, 503, 504])


@dataclass
class ScraperConfig:
    """Konfiguration für den Scraper."""

    # Basis-URLs
    gelbe_seiten_base_url: str = "https://www.gelbeseiten.de"
    gelbe_seiten_search_url: str = "https://www.gelbeseiten.de/suche"

    # Pagination
    results_per_page: int = 25  # Geschätzt, kann variieren

    # Timeouts
    request_timeout: float = 30.0
    connect_timeout: float = 10.0

    # User-Agent Rotation
    rotate_ua_every_n_requests: int = 10


@dataclass
class FilterConfig:
    """Konfiguration für Lead-Filterung."""

    # Website-Status Filter
    include_no_website: bool = True
    include_old_website: bool = True
    include_modern_website: bool = False
    include_unknown_website: bool = True

    # Qualitäts-Filter
    min_quality_score: int = 0
    require_phone: bool = False
    require_email: bool = False
    require_address: bool = False


@dataclass
class ExportConfig:
    """Konfiguration für Export."""

    output_format: OutputFormat = OutputFormat.JSON
    output_dir: Path = field(default_factory=lambda: Path("."))
    include_meta: bool = True
    pretty_print: bool = True
    encoding: str = "utf-8"


@dataclass
class GoogleMapsConfig:
    """Konfiguration für Google Maps Scraping."""

    enabled: bool = True
    max_results_per_search: int = 100
    use_browser: bool = True
    browser_headless: bool = True
    scroll_pause_time: float = 1.5
    max_scroll_attempts: int = 50


@dataclass
class ProxyConfig:
    """Konfiguration für Proxy-Rotation."""

    enabled: bool = False
    proxy_file: Optional[str] = None
    rotate_every_n_requests: int = 10
    max_failures_before_block: int = 5


@dataclass
class AggregatorConfig:
    """Konfiguration für Lead-Aggregation/Deduplizierung."""

    phone_match_weight: float = 1.0
    name_match_weight: float = 0.8
    address_match_weight: float = 0.6
    min_similarity_threshold: float = 0.85
    prefer_newer_data: bool = True


@dataclass
class StealthConfig:
    """
    Stealth-Modus für sicheres Scraping ohne Proxy.

    Simuliert menschliches Verhalten durch lange, zufällige Pausen
    und begrenzte Request-Raten. Ideal für längere Scraping-Sessions
    ohne Risiko eines IP-Bans.
    """

    enabled: bool = False

    # Delays zwischen Requests (Sekunden)
    min_delay: float = 30.0
    max_delay: float = 90.0

    # Pausen ("Kaffeepausen") zur Simulation menschlichen Verhaltens
    requests_before_break: int = 12
    break_min_duration: float = 180.0   # 3 Minuten
    break_max_duration: float = 480.0   # 8 Minuten

    # Harte Limits
    max_requests_per_hour: int = 50
    max_session_duration_minutes: int = 180  # 3 Stunden

    # Zusätzliche Sicherheit
    randomize_scroll_speed: bool = True
    simulate_reading_time: bool = True  # Wartet auf Seite wie ein Mensch


@dataclass
class Settings:
    """Hauptkonfiguration - kombiniert alle Teilkonfigurationen."""

    # Suchparameter
    branche: str = ""
    stadt: str = ""
    max_leads: int = 100
    max_pages: int = 50

    # Website-Check
    website_check_depth: WebsiteCheckDepth = WebsiteCheckDepth.NORMAL

    # Datenquellen
    sources: List[DataSource] = field(default_factory=lambda: [DataSource.GELBE_SEITEN])

    # Teilkonfigurationen
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    scraper: ScraperConfig = field(default_factory=ScraperConfig)
    filter: FilterConfig = field(default_factory=FilterConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    google_maps: GoogleMapsConfig = field(default_factory=GoogleMapsConfig)
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    aggregator: AggregatorConfig = field(default_factory=AggregatorConfig)
    stealth: StealthConfig = field(default_factory=StealthConfig)

    # Logging
    verbose: bool = False
    debug: bool = False

    @classmethod
    def from_cli_args(
        cls,
        branche: str,
        stadt: str,
        limit: int = 100,
        output: Optional[str] = None,
        format: str = "json",
        website_check: str = "normal",
        min_quality: int = 0,
        include_modern: bool = False,
        verbose: bool = False,
        sources: str = "gelbe-seiten",
        use_proxy: bool = False,
        proxy_file: Optional[str] = None,
        headless: bool = True
    ) -> "Settings":
        """Erstellt Settings aus CLI-Argumenten."""

        # Datenquellen parsen
        source_list = []
        sources_lower = sources.lower()
        if sources_lower == "all":
            source_list = [DataSource.GELBE_SEITEN, DataSource.GOOGLE_MAPS]
        elif "gelbe" in sources_lower:
            source_list.append(DataSource.GELBE_SEITEN)
        if "google" in sources_lower or "maps" in sources_lower:
            if DataSource.GOOGLE_MAPS not in source_list:
                source_list.append(DataSource.GOOGLE_MAPS)
        if not source_list:
            source_list = [DataSource.GELBE_SEITEN]

        settings = cls(
            branche=branche,
            stadt=stadt,
            max_leads=limit,
            website_check_depth=WebsiteCheckDepth(website_check),
            sources=source_list,
            verbose=verbose
        )

        # Export-Konfiguration
        settings.export.output_format = OutputFormat(format)
        if output:
            settings.export.output_dir = Path(output).parent

        # Filter-Konfiguration
        settings.filter.min_quality_score = min_quality
        settings.filter.include_modern_website = include_modern

        # Google Maps Konfiguration
        settings.google_maps.enabled = DataSource.GOOGLE_MAPS in source_list
        settings.google_maps.browser_headless = headless

        # Proxy-Konfiguration
        settings.proxy.enabled = use_proxy
        settings.proxy.proxy_file = proxy_file

        return settings

    def get_output_filename(self) -> str:
        """Generiert den Output-Dateinamen."""
        branche_safe = self.branche.lower().replace(" ", "_").replace("/", "_")
        stadt_safe = self.stadt.lower().replace(" ", "_")
        extension = self.export.output_format.value
        return f"leads_{branche_safe}_{stadt_safe}.{extension}"
