"""
Gelbe Seiten Scraper - Stage 1 der Pipeline.

Scraped Suchergebnisse und Detailseiten von gelbeseiten.de
"""

import logging
import time
from typing import List, Optional, Generator
from urllib.parse import quote_plus

from src.client.http import HTTPClient, HTTPResponse
from src.client.rate_limiter import SessionLimitReached
from src.parser.listing import ListingParser
from src.parser.detail import DetailParser
from src.models.lead import Lead, RawListing
from config.settings import Settings


logger = logging.getLogger(__name__)


class GelbeSeitenScraper:
    """
    Scraper für gelbeseiten.de

    Zwei-Stufen-Prozess:
    1. Suchergebnis-Seiten scrapen → Liste von Basis-Infos
    2. Detail-Seiten scrapen → Vollständige Lead-Daten
    """

    BASE_URL = "https://www.gelbeseiten.de"
    SEARCH_URL = "https://www.gelbeseiten.de/suche"

    def __init__(
        self,
        http_client: HTTPClient,
        settings: Optional[Settings] = None
    ):
        """
        Initialisiert den Scraper.

        Args:
            http_client: Konfigurierter HTTP Client.
            settings: Scraper-Einstellungen.
        """
        self._client = http_client
        self._settings = settings or Settings()
        self._listing_parser = ListingParser()
        self._detail_parser = DetailParser()

        # Statistiken
        self._pages_scraped = 0
        self._listings_found = 0
        self._details_scraped = 0
        self._errors = []

        # Partial Results (für SessionLimitReached)
        self._partial_leads: List[Lead] = []

    def search(
        self,
        branche: str,
        stadt: str,
        max_pages: Optional[int] = None,
        max_results: Optional[int] = None
    ) -> Generator[RawListing, None, None]:
        """
        Durchsucht Gelbe Seiten nach Branche und Stadt.

        Generiert RawListing Objekte für jeden gefundenen Eintrag.

        Args:
            branche: Suchbegriff/Branche (z.B. "Friseur")
            stadt: Stadt/Region (z.B. "Berlin")
            max_pages: Maximale Anzahl Seiten (None = unbegrenzt)
            max_results: Maximale Anzahl Ergebnisse (None = unbegrenzt)

        Yields:
            RawListing Objekte
        """
        if max_pages is None:
            max_pages = self._settings.max_pages
        if max_results is None:
            max_results = self._settings.max_leads

        results_count = 0
        page = 1

        logger.info(f"Starte Suche: '{branche}' in '{stadt}' (max {max_pages} Seiten, {max_results} Ergebnisse)")

        while page <= max_pages:
            # Prüfe ob wir genug Ergebnisse haben
            if results_count >= max_results:
                logger.info(f"Maximale Ergebnisanzahl erreicht ({max_results})")
                break

            # Baue Such-URL
            search_url = self._build_search_url(branche, stadt, page)
            logger.debug(f"Scrape Seite {page}: {search_url}")

            # Hole Seite
            response = self._client.get_with_retry(search_url)

            if not response.success:
                error_msg = f"Fehler beim Laden von Seite {page}: {response.error}"
                logger.error(error_msg)
                self._errors.append(error_msg)
                # Bei erstem Fehler abbrechen, sonst versuchen weiterzumachen
                if page == 1:
                    break
                page += 1
                continue

            self._pages_scraped += 1

            # Parse Listings
            listings = self._listing_parser.parse(response.content, search_url)

            if not listings:
                logger.info(f"Keine weiteren Ergebnisse auf Seite {page}")
                break

            # Yield Listings
            for listing in listings:
                if results_count >= max_results:
                    break
                self._listings_found += 1
                results_count += 1
                yield listing

            # Prüfe Pagination
            _, total_pages, has_next = self._listing_parser.extract_pagination_info(response.content)

            if not has_next and page >= total_pages:
                logger.info(f"Letzte Seite erreicht (Seite {page} von {total_pages})")
                break

            page += 1

        logger.info(
            f"Suche abgeschlossen: {results_count} Listings von {self._pages_scraped} Seiten"
        )

    def scrape_leads(
        self,
        branche: str,
        stadt: str,
        max_leads: Optional[int] = None,
        include_details: bool = True
    ) -> List[Lead]:
        """
        Vollständiges Scraping: Listings + Detailseiten.

        Args:
            branche: Suchbegriff/Branche
            stadt: Stadt/Region
            max_leads: Maximale Anzahl Leads
            include_details: Wenn True, werden auch Detailseiten gescraped

        Returns:
            Liste von Lead Objekten
        """
        if max_leads is None:
            max_leads = self._settings.max_leads

        leads = []
        start_time = time.time()

        logger.info(f"Starte vollständiges Scraping: '{branche}' in '{stadt}'")

        # Sammle Listings
        listings = list(self.search(branche, stadt, max_results=max_leads))
        logger.info(f"Gefunden: {len(listings)} Listings")

        if not include_details:
            # Ohne Details: Konvertiere Listings direkt zu Leads
            for listing in listings:
                lead = self._listing_to_lead(listing, stadt, branche)
                if lead:
                    leads.append(lead)
            return leads

        # Mit Details: Scrape jede Detailseite
        try:
            for i, listing in enumerate(listings):
                if len(leads) >= max_leads:
                    break

                logger.debug(f"Scrape Detail {i+1}/{len(listings)}: {listing.name}")

                lead = self.scrape_detail(listing.detail_url, stadt, branche)

                if lead:
                    # Ergänze Daten aus Listing falls im Detail nicht vorhanden
                    lead = self._merge_listing_data(lead, listing)
                    leads.append(lead)
                    self._details_scraped += 1
                else:
                    # Fallback: Verwende Listing-Daten
                    fallback_lead = self._listing_to_lead(listing, stadt, branche)
                    if fallback_lead:
                        leads.append(fallback_lead)

                # Progress-Log alle 10 Einträge
                if (i + 1) % 10 == 0:
                    elapsed = time.time() - start_time
                    rate = (i + 1) / elapsed
                    logger.info(
                        f"Progress: {i+1}/{len(listings)} Details ({len(leads)} Leads), "
                        f"{rate:.1f} pro Sekunde"
                    )

        except SessionLimitReached:
            # Session-Limit erreicht - speichere bereits gesammelte Leads
            logger.info(f"Session-Limit erreicht - speichere {len(leads)} bereits gesammelte Leads")
            self._partial_leads = leads
            # Exception erneut werfen damit die Pipeline sie sieht
            raise

        elapsed_total = time.time() - start_time
        logger.info(
            f"Scraping abgeschlossen: {len(leads)} Leads in {elapsed_total:.1f}s"
        )

        return leads

    def scrape_detail(
        self,
        url: str,
        stadt: str,
        branche: str = ""
    ) -> Optional[Lead]:
        """
        Scraped eine einzelne Detailseite.

        Args:
            url: Die URL der Detailseite
            stadt: Die gesuchte Stadt (für Fallback)
            branche: Die gesuchte Branche (für Fallback)

        Returns:
            Lead Objekt oder None
        """
        response = self._client.get_with_retry(url)

        if not response.success:
            error_msg = f"Fehler beim Laden der Detailseite: {response.error}"
            logger.warning(error_msg)
            self._errors.append(error_msg)
            return None

        return self._detail_parser.parse(
            response.content,
            response.final_url,
            stadt,
            branche
        )

    def _build_search_url(self, branche: str, stadt: str, page: int = 1) -> str:
        """
        Baut die Such-URL.

        URL-Format: https://www.gelbeseiten.de/suche/{branche}/{stadt}/seite-{page}
        """
        # URL-encode Branche und Stadt
        branche_encoded = quote_plus(branche.lower())
        stadt_encoded = quote_plus(stadt.lower())

        if page == 1:
            return f"{self.SEARCH_URL}/{branche_encoded}/{stadt_encoded}"
        else:
            return f"{self.SEARCH_URL}/{branche_encoded}/{stadt_encoded}/seite-{page}"

    def _listing_to_lead(
        self,
        listing: RawListing,
        stadt: str,
        branche: str
    ) -> Optional[Lead]:
        """
        Konvertiert ein RawListing zu einem Lead (ohne Detailseite).
        """
        from src.models.lead import Address, WebsiteAnalysis, WebsiteStatus

        # Parse Adresse aus Roh-String
        adresse = self._parse_raw_address(listing.adresse_raw, stadt)

        # Website-Analyse
        website_analyse = WebsiteAnalysis()
        if listing.website_url:
            website_analyse.status = WebsiteStatus.NICHT_GEPRUEFT
        elif listing.hat_website:
            website_analyse.status = WebsiteStatus.NICHT_GEPRUEFT
        else:
            website_analyse.status = WebsiteStatus.KEINE

        try:
            return Lead(
                firmenname=listing.name,
                branche=listing.branche or branche,
                adresse=adresse,
                telefon=listing.telefon,
                website_url=listing.website_url,
                website_analyse=website_analyse,
                bewertung=listing.bewertung,
                bewertung_anzahl=listing.bewertung_anzahl,
                gelbe_seiten_url=listing.detail_url
            )
        except Exception as e:
            logger.warning(f"Fehler beim Konvertieren von Listing zu Lead: {e}")
            return None

    def _parse_raw_address(self, raw: Optional[str], fallback_stadt: str) -> "Address":
        """Parst einen Roh-Adress-String."""
        from src.models.lead import Address
        import re

        if not raw:
            return Address(stadt=fallback_stadt)

        strasse = None
        hausnummer = None
        plz = None
        stadt = fallback_stadt

        # PLZ + Stadt
        plz_match = re.search(r"(\d{5})\s+([A-Za-zäöüßÄÖÜ\-\s]+)", raw)
        if plz_match:
            plz = plz_match.group(1)
            stadt = plz_match.group(2).strip()

        # Straße (Text vor PLZ)
        if plz_match:
            pre_plz = raw[:plz_match.start()].strip().rstrip(",")
            if pre_plz:
                # Trenne Hausnummer
                street_match = re.match(r"^(.+?)\s+(\d+\s*[a-zA-Z]?)$", pre_plz)
                if street_match:
                    strasse = street_match.group(1)
                    hausnummer = street_match.group(2)
                else:
                    strasse = pre_plz

        return Address(
            strasse=strasse,
            hausnummer=hausnummer,
            plz=plz,
            stadt=stadt
        )

    def _merge_listing_data(self, lead: Lead, listing: RawListing) -> Lead:
        """
        Ergänzt Lead-Daten mit Listing-Daten wo nötig.
        """
        # Telefon aus Listing wenn nicht in Detail
        if not lead.telefon and listing.telefon:
            lead.telefon = listing.telefon

        # Website aus Listing wenn nicht in Detail
        if not lead.website_url and listing.website_url:
            lead.website_url = listing.website_url

        # Bewertung aus Listing wenn nicht in Detail
        if lead.bewertung is None and listing.bewertung is not None:
            lead.bewertung = listing.bewertung
            lead.bewertung_anzahl = listing.bewertung_anzahl

        return lead

    def get_total_results(self, branche: str, stadt: str) -> Optional[int]:
        """
        Ermittelt die Gesamtanzahl der Suchergebnisse.

        Args:
            branche: Suchbegriff
            stadt: Stadt

        Returns:
            Anzahl oder None wenn nicht ermittelbar
        """
        search_url = self._build_search_url(branche, stadt, 1)
        response = self._client.get(search_url)

        if not response.success:
            return None

        return self._listing_parser.extract_total_results(response.content)

    @property
    def stats(self) -> dict:
        """Gibt Scraper-Statistiken zurück."""
        return {
            "pages_scraped": self._pages_scraped,
            "listings_found": self._listings_found,
            "details_scraped": self._details_scraped,
            "errors": len(self._errors),
            "error_messages": self._errors[-10:],  # Letzte 10 Fehler
            "listing_parser_stats": self._listing_parser.stats,
            "detail_parser_stats": self._detail_parser.stats
        }

    def reset_stats(self) -> None:
        """Setzt Statistiken zurück."""
        self._pages_scraped = 0
        self._listings_found = 0
        self._details_scraped = 0
        self._errors = []
        self._partial_leads = []

    @property
    def partial_leads(self) -> List[Lead]:
        """Gibt teilweise gesammelte Leads zurück (nach SessionLimitReached)."""
        return self._partial_leads

    def clear_partial_leads(self) -> None:
        """Löscht gespeicherte Partial Leads."""
        self._partial_leads = []
