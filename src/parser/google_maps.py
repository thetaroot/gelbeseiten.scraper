"""
Parser für Google Maps Suchergebnisse.

DSGVO-KONFORM: Extrahiert NUR Geschäftsdaten, KEINE Personendaten.
Ausgeschlossen: Reviews, Review-Autoren, Nutzerfotos, Owner-Namen.
"""

import re
import json
import logging
from typing import List, Optional, Tuple, Dict, Any
from urllib.parse import unquote

from bs4 import BeautifulSoup, Tag

from src.models.lead import RawListing, Lead, Address, WebsiteAnalysis, WebsiteStatus
from config.settings import DataSource


logger = logging.getLogger(__name__)


class GoogleMapsParser:
    """
    Parser für Google Maps Suchergebnisse.

    DSGVO-konform: Extrahiert nur Geschäftsdaten.

    Extrahierte Daten:
    - Firmenname
    - Adresse
    - Telefonnummer
    - Website-URL
    - Kategorie/Branche
    - Öffnungszeiten
    - Place-ID

    NICHT extrahiert (DSGVO):
    - Reviews/Bewertungstexte
    - Review-Autoren
    - Nutzerfotos
    - Owner-Namen
    """

    # Selektoren für verschiedene Elemente
    # Diese müssen möglicherweise angepasst werden wenn Google das Layout ändert
    SELECTORS = {
        # Suchergebnis-Karten
        "result_cards": [
            "div[data-result-index]",
            "div.Nv2PK",
            "a[data-cid]",
        ],
        # Firmenname
        "name": [
            "div.fontHeadlineSmall",
            "div.qBF1Pd",
            "h3.fontHeadlineSmall",
            "span.fontHeadlineSmall",
        ],
        # Adresse
        "address": [
            "div.W4Efsd:last-child",
            "span.W4Efsd",
            "[data-item-id*='address']",
        ],
        # Kategorie/Branche
        "category": [
            "div.W4Efsd span:first-child",
            "span.DkEaL",
            "[data-tooltip*='Kategorie']",
        ],
        # Öffnungsstatus
        "hours_status": [
            "span.ZDu9vd",
            "span[data-tooltip*='Öffnungszeiten']",
        ],
    }

    def __init__(self):
        """Initialisiert den Parser."""
        self._parsed_count = 0
        self._error_count = 0

    def parse_search_results(self, html: str) -> List[RawListing]:
        """
        Parst Google Maps Suchergebnisse.

        Args:
            html: Der HTML-Content der Suchergebnis-Seite.

        Returns:
            Liste von RawListing Objekten.
        """
        listings = []

        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception as e:
            logger.error(f"Fehler beim Parsen von HTML: {e}")
            return listings

        # Versuche verschiedene Selektoren
        results = []
        for selector in self.SELECTORS["result_cards"]:
            results = soup.select(selector)
            if results:
                logger.debug(f"Gefunden mit Selector '{selector}': {len(results)} Ergebnisse")
                break

        if not results:
            # Fallback: Suche nach data-cid Attributen (eindeutige Place IDs)
            results = soup.find_all(attrs={"data-cid": True})
            if results:
                logger.debug(f"Fallback: Gefunden {len(results)} Ergebnisse mit data-cid")

        for result in results:
            try:
                listing = self._parse_result_card(result)
                if listing:
                    listings.append(listing)
                    self._parsed_count += 1
            except Exception as e:
                logger.warning(f"Fehler beim Parsen eines Ergebnisses: {e}")
                self._error_count += 1

        logger.info(f"Google Maps: {len(listings)} Listings geparst")
        return listings

    def _parse_result_card(self, card: Tag) -> Optional[RawListing]:
        """
        Parst eine einzelne Ergebniskarte.

        Args:
            card: Das BeautifulSoup Tag der Karte.

        Returns:
            RawListing oder None.
        """
        # Firmenname
        name = self._extract_name(card)
        if not name:
            return None

        # Place ID / URL
        place_id, detail_url = self._extract_place_info(card)
        if not detail_url:
            detail_url = "https://www.google.com/maps"

        # Adresse
        address = self._extract_address(card)

        # Telefon
        phone = self._extract_phone(card)

        # Website
        has_website, website_url = self._extract_website(card)

        # Kategorie/Branche
        category = self._extract_category(card)

        # Öffnungszeiten
        hours = self._extract_hours(card)

        return RawListing(
            name=name,
            detail_url=detail_url,
            telefon=phone,
            adresse_raw=address,
            branche=category,
            hat_website=has_website,
            website_url=website_url,
            quelle=DataSource.GOOGLE_MAPS,
            place_id=place_id,
            oeffnungszeiten=hours
        )

    def _extract_name(self, card: Tag) -> Optional[str]:
        """Extrahiert den Firmennamen."""
        for selector in self.SELECTORS["name"]:
            elem = card.select_one(selector)
            if elem:
                name = elem.get_text(strip=True)
                if name and len(name) > 1:
                    return self._clean_text(name)

        # Fallback: aria-label
        aria_label = card.get("aria-label")
        if aria_label:
            return self._clean_text(str(aria_label))

        return None

    def _extract_place_info(self, card: Tag) -> Tuple[Optional[str], Optional[str]]:
        """Extrahiert Place-ID und Detail-URL."""
        place_id = None
        detail_url = None

        # data-cid enthält die CID (Customer ID)
        cid = card.get("data-cid")
        if cid:
            place_id = str(cid)

        # href enthält oft die vollständige URL
        href = card.get("href")
        if href:
            detail_url = str(href)
            # Extrahiere Place ID aus URL wenn möglich
            place_match = re.search(r"place/[^/]+/data=![\w!]+:(\w+)", href)
            if place_match and not place_id:
                place_id = place_match.group(1)

        # Suche nach Link-Element
        if not detail_url:
            link = card.find("a", href=True)
            if link:
                detail_url = link.get("href")

        return place_id, detail_url

    def _extract_address(self, card: Tag) -> Optional[str]:
        """Extrahiert die Adresse."""
        for selector in self.SELECTORS["address"]:
            elems = card.select(selector)
            for elem in elems:
                text = elem.get_text(strip=True)
                # Prüfe ob es wie eine Adresse aussieht
                if self._looks_like_address(text):
                    return self._clean_text(text)

        # Fallback: Suche nach PLZ-Pattern im gesamten Text
        full_text = card.get_text()
        plz_match = re.search(r"(\d{5})\s+([A-Za-zäöüßÄÖÜ\-]+)", full_text)
        if plz_match:
            return f"{plz_match.group(1)} {plz_match.group(2)}"

        return None

    def _looks_like_address(self, text: str) -> bool:
        """Prüft ob ein Text wie eine Adresse aussieht."""
        if not text or len(text) < 5:
            return False

        # Deutsche PLZ
        if re.search(r"\d{5}", text):
            return True

        # Straßennamen
        street_patterns = [
            r"straße", r"str\.", r"weg", r"platz", r"allee",
            r"gasse", r"ring", r"damm", r"ufer"
        ]
        for pattern in street_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True

        return False

    def _extract_phone(self, card: Tag) -> Optional[str]:
        """Extrahiert die Telefonnummer."""
        # Suche nach tel: Links
        tel_link = card.find("a", href=lambda x: x and x.startswith("tel:"))
        if tel_link:
            href = tel_link.get("href", "")
            phone = href.replace("tel:", "").strip()
            return self._clean_phone(phone)

        # Suche nach Telefon-Icon + Text
        text = card.get_text()
        phone_patterns = [
            r"(\+49[\d\s\-/]+\d)",
            r"(0\d{2,4}[\s\-/]?\d{3,}[\s\-/]?\d{2,})",
        ]
        for pattern in phone_patterns:
            match = re.search(pattern, text)
            if match:
                return self._clean_phone(match.group(1))

        return None

    def _extract_website(self, card: Tag) -> Tuple[bool, Optional[str]]:
        """
        Extrahiert Website-Information.

        Returns:
            Tuple (hat_website, website_url)
        """
        # Suche nach Website-Links (nicht google.com)
        for link in card.find_all("a", href=True):
            href = link.get("href", "")

            # Überspringe Google-Links
            if "google.com" in href or "google.de" in href:
                continue

            # Suche nach echten Website-URLs
            if href.startswith("http") and "maps" not in href:
                return True, href

            # Google Redirect-URLs
            if "url?q=" in href:
                url_match = re.search(r"url\?q=([^&]+)", href)
                if url_match:
                    website = unquote(url_match.group(1))
                    if "google.com" not in website:
                        return True, website

        # Prüfe auf Website-Button/Icon
        text = card.get_text().lower()
        if "website" in text or "webseite" in text:
            return True, None

        return False, None

    def _extract_category(self, card: Tag) -> Optional[str]:
        """Extrahiert die Kategorie/Branche."""
        for selector in self.SELECTORS["category"]:
            elem = card.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                # Filtere offensichtlich keine Kategorien
                if text and not self._looks_like_address(text):
                    if len(text) > 2 and not text.startswith("€"):
                        return self._clean_text(text)

        return None

    def _extract_hours(self, card: Tag) -> Optional[Dict[str, str]]:
        """
        Extrahiert Öffnungszeiten.

        Returns:
            Dictionary mit Wochentagen als Keys oder None.
        """
        hours = {}

        # Suche nach Öffnungsstatus
        for selector in self.SELECTORS["hours_status"]:
            elem = card.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                if "geöffnet" in text.lower() or "geschlossen" in text.lower():
                    hours["status"] = text

        # Detaillierte Öffnungszeiten sind meist nur auf Detailseite verfügbar
        return hours if hours else None

    def _clean_text(self, text: str) -> str:
        """Bereinigt Text."""
        if not text:
            return ""
        # Mehrfache Leerzeichen entfernen
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _clean_phone(self, phone: str) -> str:
        """Bereinigt Telefonnummer."""
        if not phone:
            return ""
        # Nur Ziffern, +, -, /, Leerzeichen behalten
        cleaned = re.sub(r"[^\d+\-/\s]", "", phone)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    def parse_detail_page(self, html: str, place_id: Optional[str] = None) -> Optional[Lead]:
        """
        Parst eine Google Maps Detail-Seite.

        DSGVO: Extrahiert KEINE Reviews oder Personendaten.

        Args:
            html: Der HTML-Content der Detail-Seite.
            place_id: Optional, die bekannte Place-ID.

        Returns:
            Lead oder None.
        """
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception as e:
            logger.error(f"Fehler beim Parsen der Detailseite: {e}")
            return None

        # Firmenname (aus Titel oder H1)
        name = self._extract_detail_name(soup)
        if not name:
            return None

        # Adresse
        address = self._extract_detail_address(soup)

        # Telefon
        phone = self._extract_detail_phone(soup)

        # Website
        website_url = self._extract_detail_website(soup)

        # Kategorie
        category = self._extract_detail_category(soup)

        # Öffnungszeiten
        hours = self._extract_detail_hours(soup)

        # Erstelle Lead
        address_obj = Address(stadt=address.get("stadt", "Unbekannt")) if address else Address(stadt="Unbekannt")
        if address:
            address_obj.strasse = address.get("strasse")
            address_obj.hausnummer = address.get("hausnummer")
            address_obj.plz = address.get("plz")

        lead = Lead(
            firmenname=name,
            branche=category or "Unbekannt",
            adresse=address_obj,
            telefon=phone,
            website_url=website_url,
            website_analyse=WebsiteAnalysis(
                status=WebsiteStatus.NICHT_GEPRUEFT if website_url else WebsiteStatus.KEINE
            ),
            oeffnungszeiten=hours,
            quellen=[DataSource.GOOGLE_MAPS],
            google_maps_place_id=place_id,
            google_maps_url=f"https://www.google.com/maps/place/?q=place_id:{place_id}" if place_id else None
        )

        return lead

    def _extract_detail_name(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrahiert den Namen von der Detailseite."""
        # H1 oder Titel
        h1 = soup.find("h1")
        if h1:
            return self._clean_text(h1.get_text())

        title = soup.find("title")
        if title:
            text = title.get_text()
            # Entferne " - Google Maps" Suffix
            text = re.sub(r"\s*[-–]\s*Google\s*Maps.*$", "", text, flags=re.IGNORECASE)
            return self._clean_text(text)

        return None

    def _extract_detail_address(self, soup: BeautifulSoup) -> Optional[Dict[str, str]]:
        """Extrahiert strukturierte Adresse von Detailseite."""
        # Suche nach Adress-Button/Container
        address_button = soup.find(attrs={"data-item-id": lambda x: x and "address" in str(x).lower()})

        if address_button:
            text = address_button.get_text()
            return self._parse_address_string(text)

        # Fallback: Suche im gesamten Text
        text = soup.get_text()
        plz_match = re.search(r"(\d{5})\s+([A-Za-zäöüßÄÖÜ\-]+)", text)
        if plz_match:
            return {
                "plz": plz_match.group(1),
                "stadt": plz_match.group(2)
            }

        return None

    def _parse_address_string(self, address: str) -> Dict[str, str]:
        """Parst einen Adress-String in Komponenten."""
        result = {}

        # PLZ + Stadt
        plz_match = re.search(r"(\d{5})\s+([A-Za-zäöüßÄÖÜ\-]+)", address)
        if plz_match:
            result["plz"] = plz_match.group(1)
            result["stadt"] = plz_match.group(2)

        # Straße + Hausnummer
        street_match = re.search(
            r"([A-Za-zäöüßÄÖÜ\.\-]+(?:straße|str\.|weg|platz|allee|gasse|ring|damm|ufer)?)\s*(\d+[a-zA-Z]?)",
            address,
            re.IGNORECASE
        )
        if street_match:
            result["strasse"] = street_match.group(1)
            result["hausnummer"] = street_match.group(2)

        return result

    def _extract_detail_phone(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrahiert Telefon von Detailseite."""
        phone_button = soup.find(attrs={"data-item-id": lambda x: x and "phone" in str(x).lower()})
        if phone_button:
            return self._clean_phone(phone_button.get_text())

        tel_link = soup.find("a", href=lambda x: x and x.startswith("tel:"))
        if tel_link:
            return self._clean_phone(tel_link.get("href", "").replace("tel:", ""))

        return None

    def _extract_detail_website(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrahiert Website von Detailseite."""
        website_button = soup.find(attrs={"data-item-id": lambda x: x and "authority" in str(x).lower()})
        if website_button:
            link = website_button.find("a", href=True)
            if link:
                href = link.get("href", "")
                if "url?q=" in href:
                    url_match = re.search(r"url\?q=([^&]+)", href)
                    if url_match:
                        return unquote(url_match.group(1))
                return href

        return None

    def _extract_detail_category(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrahiert Kategorie von Detailseite."""
        category_button = soup.find("button", attrs={"jsaction": lambda x: x and "category" in str(x).lower()})
        if category_button:
            return self._clean_text(category_button.get_text())

        return None

    def _extract_detail_hours(self, soup: BeautifulSoup) -> Optional[Dict[str, str]]:
        """Extrahiert Öffnungszeiten von Detailseite."""
        hours = {}

        hours_container = soup.find(attrs={"data-item-id": lambda x: x and "oh" in str(x).lower()})
        if hours_container:
            # Parse Öffnungszeiten
            rows = hours_container.find_all("tr")
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 2:
                    day = self._clean_text(cols[0].get_text())
                    time = self._clean_text(cols[1].get_text())
                    if day and time:
                        hours[day] = time

        return hours if hours else None

    @property
    def stats(self) -> Dict[str, int]:
        """Gibt Parser-Statistiken zurück."""
        return {
            "parsed_count": self._parsed_count,
            "error_count": self._error_count
        }

    def reset_stats(self) -> None:
        """Setzt Statistiken zurück."""
        self._parsed_count = 0
        self._error_count = 0
