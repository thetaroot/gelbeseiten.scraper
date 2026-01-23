"""
Google Maps Scraper.

DSGVO-KONFORM: Extrahiert NUR Geschäftsdaten.
Verwendet Browser-Automation für JavaScript-Rendering.
"""

import logging
import time
import random
from typing import Generator, List, Optional
from urllib.parse import quote_plus

from src.client.browser import BrowserClient
from src.client.rate_limiter import RateLimiter
from src.parser.google_maps import GoogleMapsParser
from src.models.lead import Lead, RawListing, Address, WebsiteAnalysis, WebsiteStatus
from config.settings import Settings, DataSource


logger = logging.getLogger(__name__)


class GoogleMapsScraper:
    """
    Scrapt Google Maps Suchergebnisse.

    DSGVO-konform:
    - Extrahiert nur Geschäftsdaten
    - Keine Reviews/Personendaten
    - Keine Nutzerfotos

    Features:
    - Browser-Automation (Playwright)
    - Scroll-basiertes Laden
    - Rate Limiting
    - Stealth-Mode
    """

    BASE_URL = "https://www.google.com/maps/search"

    def __init__(
        self,
        browser: BrowserClient,
        rate_limiter: RateLimiter,
        settings: Settings
    ):
        """
        Initialisiert den Scraper.

        Args:
            browser: BrowserClient für Navigation.
            rate_limiter: RateLimiter für Request-Throttling.
            settings: Konfiguration.
        """
        self._browser = browser
        self._rate_limiter = rate_limiter
        self._settings = settings
        self._parser = GoogleMapsParser()

        # Statistiken
        self._pages_scraped = 0
        self._listings_found = 0
        self._leads_created = 0
        self._errors = 0

    def search(
        self,
        branche: str,
        stadt: str,
        max_results: int = 100
    ) -> Generator[RawListing, None, None]:
        """
        Sucht auf Google Maps und gibt Listings zurück.

        Args:
            branche: Branche/Suchbegriff.
            stadt: Stadt/Region.
            max_results: Maximale Anzahl Ergebnisse.

        Yields:
            RawListing Objekte.
        """
        query = f"{branche} in {stadt}"
        search_url = f"{self.BASE_URL}/{quote_plus(query)}"

        logger.info(f"Google Maps Suche: '{query}'")

        # Rate Limiting
        self._rate_limiter.wait("google.com")

        # Navigiere zur Suchseite
        response = self._browser.navigate(search_url, wait_until="networkidle")

        if not response.success:
            logger.error(f"Fehler beim Laden der Suche: {response.error}")
            self._errors += 1
            return

        self._pages_scraped += 1

        # Warte auf Suchergebnisse
        results_loaded = self._browser.wait_for_selector(
            "div[data-result-index], div.Nv2PK",
            timeout=10000
        )

        if not results_loaded:
            logger.warning("Keine Suchergebnisse gefunden")
            return

        # Scroll um mehr Ergebnisse zu laden
        scroll_count = 0
        max_scrolls = self._settings.google_maps.max_scroll_attempts
        pause_time = self._settings.google_maps.scroll_pause_time

        # Finde das scrollbare Panel
        scroll_panel_selector = "div[role='feed'], div.m6QErb"

        yielded_count = 0
        seen_names = set()

        while yielded_count < max_results and scroll_count < max_scrolls:
            # Parse aktuelle Ergebnisse
            html = self._browser.get_content()
            listings = self._parser.parse_search_results(html)

            for listing in listings:
                # Deduplizierung innerhalb der Suche
                if listing.name in seen_names:
                    continue
                seen_names.add(listing.name)

                yield listing
                yielded_count += 1
                self._listings_found += 1

                if yielded_count >= max_results:
                    break

            if yielded_count >= max_results:
                break

            # Scroll für mehr Ergebnisse
            scrolled = self._browser.scroll_element(
                scroll_panel_selector,
                pause=pause_time,
                max_scrolls=1
            )

            if scrolled == 0:
                # Versuche alternative Scroll-Methode
                self._browser.scroll_to_bottom(pause=pause_time, max_scrolls=1)

            scroll_count += 1

            # Kleine Pause zwischen Scrolls
            time.sleep(pause_time + random.uniform(0, 0.5))

        logger.info(f"Google Maps: {yielded_count} Listings gefunden nach {scroll_count} Scrolls")

    def scrape_leads(
        self,
        branche: str,
        stadt: str,
        max_leads: int = 100,
        include_details: bool = True
    ) -> List[Lead]:
        """
        Scrapt vollständige Lead-Daten.

        Args:
            branche: Branche/Suchbegriff.
            stadt: Stadt/Region.
            max_leads: Maximale Anzahl Leads.
            include_details: Ob Detail-Seiten gescrapt werden sollen.

        Returns:
            Liste von Lead Objekten.
        """
        leads = []
        start_time = time.time()

        logger.info(f"Starte Google Maps Scraping: '{branche}' in '{stadt}'")

        for listing in self.search(branche, stadt, max_leads):
            try:
                if include_details and listing.place_id:
                    # Detail-Seite scrapen
                    lead = self._scrape_detail(listing)
                else:
                    # Konvertiere RawListing direkt zu Lead
                    lead = self._listing_to_lead(listing, stadt, branche)

                if lead:
                    leads.append(lead)
                    self._leads_created += 1

                    if len(leads) >= max_leads:
                        break

            except Exception as e:
                logger.warning(f"Fehler bei Lead '{listing.name}': {e}")
                self._errors += 1

        duration = time.time() - start_time
        logger.info(f"Google Maps Scraping abgeschlossen: {len(leads)} Leads in {duration:.1f}s")

        return leads

    def _scrape_detail(self, listing: RawListing) -> Optional[Lead]:
        """
        Scrapt die Detail-Seite eines Listings.

        Args:
            listing: Das RawListing mit Detail-URL.

        Returns:
            Lead oder None.
        """
        if not listing.detail_url:
            return self._listing_to_lead(listing, "", listing.branche or "")

        # Rate Limiting
        self._rate_limiter.wait("google.com")

        # Navigiere zur Detail-Seite
        response = self._browser.navigate(listing.detail_url, wait_until="domcontentloaded")

        if not response.success:
            logger.debug(f"Detail-Seite nicht ladbar: {listing.name}")
            return self._listing_to_lead(listing, "", listing.branche or "")

        # Warte kurz auf Rendering
        time.sleep(0.5 + random.uniform(0, 0.3))

        # Parse Detail-Seite
        html = self._browser.get_content()
        lead = self._parser.parse_detail_page(html, listing.place_id)

        if lead:
            # Übernehme Daten aus Listing falls nicht in Details
            if not lead.telefon and listing.telefon:
                lead.telefon = listing.telefon
            if not lead.website_url and listing.website_url:
                lead.website_url = listing.website_url

            return lead

        return self._listing_to_lead(listing, "", listing.branche or "")

    def _listing_to_lead(
        self,
        listing: RawListing,
        stadt: str,
        branche: str
    ) -> Lead:
        """
        Konvertiert ein RawListing zu einem Lead.

        Args:
            listing: Das RawListing.
            stadt: Stadt für Adresse.
            branche: Branche falls nicht im Listing.

        Returns:
            Lead Objekt.
        """
        # Parse Adresse wenn vorhanden
        address = Address(stadt=stadt or "Unbekannt")

        if listing.adresse_raw:
            # Versuche Adresse zu parsen
            import re
            plz_match = re.search(r"(\d{5})\s+([A-Za-zäöüßÄÖÜ\-]+)", listing.adresse_raw)
            if plz_match:
                address.plz = plz_match.group(1)
                address.stadt = plz_match.group(2)

            street_match = re.search(
                r"([A-Za-zäöüßÄÖÜ\.\-\s]+(?:straße|str\.|weg|platz|allee))\s*(\d+[a-zA-Z]?)",
                listing.adresse_raw,
                re.IGNORECASE
            )
            if street_match:
                address.strasse = street_match.group(1).strip()
                address.hausnummer = street_match.group(2)

        # Website-Status bestimmen
        website_status = WebsiteStatus.KEINE
        if listing.hat_website or listing.website_url:
            website_status = WebsiteStatus.NICHT_GEPRUEFT

        return Lead(
            firmenname=listing.name,
            branche=listing.branche or branche or "Unbekannt",
            adresse=address,
            telefon=listing.telefon,
            website_url=listing.website_url,
            website_analyse=WebsiteAnalysis(status=website_status),
            bewertung=listing.bewertung,
            bewertung_anzahl=listing.bewertung_anzahl,
            oeffnungszeiten=listing.oeffnungszeiten,
            quellen=[DataSource.GOOGLE_MAPS],
            google_maps_place_id=listing.place_id,
            google_maps_url=listing.detail_url if listing.detail_url and "google.com" in listing.detail_url else None
        )

    def get_stats(self) -> dict:
        """Gibt Scraper-Statistiken zurück."""
        return {
            "pages_scraped": self._pages_scraped,
            "listings_found": self._listings_found,
            "leads_created": self._leads_created,
            "errors": self._errors,
            "parser_stats": self._parser.stats
        }

    def reset_stats(self) -> None:
        """Setzt Statistiken zurück."""
        self._pages_scraped = 0
        self._listings_found = 0
        self._leads_created = 0
        self._errors = 0
        self._parser.reset_stats()
