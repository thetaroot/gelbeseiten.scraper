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
class Settings:
    """Hauptkonfiguration - kombiniert alle Teilkonfigurationen."""

    # Suchparameter
    branche: str = ""
    stadt: str = ""
    max_leads: int = 100
    max_pages: int = 50

    # Website-Check
    website_check_depth: WebsiteCheckDepth = WebsiteCheckDepth.NORMAL

    # Teilkonfigurationen
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    scraper: ScraperConfig = field(default_factory=ScraperConfig)
    filter: FilterConfig = field(default_factory=FilterConfig)
    export: ExportConfig = field(default_factory=ExportConfig)

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
        verbose: bool = False
    ) -> "Settings":
        """Erstellt Settings aus CLI-Argumenten."""

        settings = cls(
            branche=branche,
            stadt=stadt,
            max_leads=limit,
            website_check_depth=WebsiteCheckDepth(website_check),
            verbose=verbose
        )

        # Export-Konfiguration
        settings.export.output_format = OutputFormat(format)
        if output:
            settings.export.output_dir = Path(output).parent

        # Filter-Konfiguration
        settings.filter.min_quality_score = min_quality
        settings.filter.include_modern_website = include_modern

        return settings

    def get_output_filename(self) -> str:
        """Generiert den Output-Dateinamen."""
        branche_safe = self.branche.lower().replace(" ", "_").replace("/", "_")
        stadt_safe = self.stadt.lower().replace(" ", "_")
        extension = self.export.output_format.value
        return f"leads_{branche_safe}_{stadt_safe}.{extension}"
