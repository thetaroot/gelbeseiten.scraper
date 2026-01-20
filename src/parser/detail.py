"""
Parser für Gelbe Seiten Firmen-Detailseiten.

Extrahiert vollständige Informationen aus einer Firmen-Detailseite.
"""

import re
import logging
from typing import Optional, Dict, List, Tuple
from urllib.parse import urljoin, unquote

from bs4 import BeautifulSoup, Tag

from src.models.lead import Lead, Address, WebsiteAnalysis, WebsiteStatus


logger = logging.getLogger(__name__)


class DetailParser:
    """
    Parser für Gelbe Seiten Firmen-Detailseiten.

    Extrahiert vollständige Informationen:
    - Firmenname
    - Vollständige Adresse (strukturiert)
    - Alle Kontaktdaten (Telefon, Fax, E-Mail)
    - Website-URL
    - Öffnungszeiten
    - Bewertungen
    - Beschreibung
    """

    BASE_URL = "https://www.gelbeseiten.de"

    def __init__(self):
        """Initialisiert den Parser."""
        self._parsed_count = 0
        self._error_count = 0

    def parse(self, html: str, source_url: str, stadt: str, branche: str = "") -> Optional[Lead]:
        """
        Parst eine Firmen-Detailseite.

        Args:
            html: Der HTML-Content der Seite.
            source_url: Die URL der Seite.
            stadt: Die gesuchte Stadt (für Fallback).
            branche: Die gesuchte Branche (für Fallback).

        Returns:
            Lead Objekt oder None wenn Parsing fehlschlägt.
        """
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception as e:
            logger.error(f"Fehler beim Parsen von HTML: {e}")
            self._error_count += 1
            return None

        try:
            # Firmenname (required)
            firmenname = self._extract_name(soup)
            if not firmenname:
                logger.warning(f"Kein Firmenname gefunden auf {source_url}")
                self._error_count += 1
                return None

            # Adresse
            adresse = self._extract_address(soup, stadt)

            # Kontaktdaten
            telefon, telefon_zusatz = self._extract_phone(soup)
            fax = self._extract_fax(soup)
            email = self._extract_email(soup)
            website_url = self._extract_website(soup)

            # Branche
            extracted_branche = self._extract_branche(soup) or branche

            # Zusatzinfos
            bewertung, bewertung_anzahl = self._extract_rating(soup)
            oeffnungszeiten = self._extract_opening_hours(soup)
            beschreibung = self._extract_description(soup)

            # Website-Analyse initialisieren
            website_analyse = WebsiteAnalysis()
            if website_url:
                website_analyse.status = WebsiteStatus.NICHT_GEPRUEFT
            else:
                website_analyse.status = WebsiteStatus.KEINE

            lead = Lead(
                firmenname=firmenname,
                branche=extracted_branche,
                beschreibung=beschreibung,
                adresse=adresse,
                telefon=telefon,
                telefon_zusatz=telefon_zusatz,
                fax=fax,
                email=email,
                website_url=website_url,
                website_analyse=website_analyse,
                bewertung=bewertung,
                bewertung_anzahl=bewertung_anzahl,
                oeffnungszeiten=oeffnungszeiten,
                gelbe_seiten_url=source_url
            )

            self._parsed_count += 1
            return lead

        except Exception as e:
            logger.error(f"Fehler beim Parsen der Detailseite {source_url}: {e}")
            self._error_count += 1
            return None

    def _extract_name(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrahiert den Firmennamen."""
        selectors = [
            "h1[itemprop='name']",
            "h1.mod-TeilnehmerKopf__name",
            "h1.firma-name",
            "h1",
            "[data-wipe='name']"
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                name = elem.get_text(strip=True)
                name = self._clean_text(name)
                if name and len(name) > 1:
                    return name

        return None

    def _extract_address(self, soup: BeautifulSoup, fallback_stadt: str) -> Address:
        """Extrahiert die strukturierte Adresse."""
        strasse = None
        hausnummer = None
        plz = None
        stadt = fallback_stadt
        bundesland = None

        # Strukturierte Adress-Elemente
        address_container = soup.select_one(
            "address, [itemprop='address'], .mod-TeilnehmerKopf__adresse, .adresse"
        )

        if address_container:
            # Straße
            street_elem = address_container.select_one(
                "[itemprop='streetAddress'], .street, .strasse"
            )
            if street_elem:
                street_text = street_elem.get_text(strip=True)
                strasse, hausnummer = self._parse_street(street_text)

            # PLZ
            plz_elem = address_container.select_one(
                "[itemprop='postalCode'], .plz, .zip"
            )
            if plz_elem:
                plz_text = plz_elem.get_text(strip=True)
                plz_match = re.search(r"(\d{5})", plz_text)
                if plz_match:
                    plz = plz_match.group(1)

            # Stadt
            city_elem = address_container.select_one(
                "[itemprop='addressLocality'], .city, .stadt, .ort"
            )
            if city_elem:
                stadt = city_elem.get_text(strip=True)

            # Bundesland
            region_elem = address_container.select_one(
                "[itemprop='addressRegion'], .bundesland, .region"
            )
            if region_elem:
                bundesland = region_elem.get_text(strip=True)

        # Fallback: Text-Parsing
        if not strasse or not plz:
            address_text = ""
            if address_container:
                address_text = address_container.get_text(separator=" ", strip=True)
            else:
                # Suche im gesamten Dokument
                for text in soup.stripped_strings:
                    if re.search(r"\d{5}", text):
                        address_text = text
                        break

            if address_text:
                parsed = self._parse_address_text(address_text)
                if parsed:
                    if not strasse and parsed.get("strasse"):
                        strasse = parsed["strasse"]
                        hausnummer = parsed.get("hausnummer")
                    if not plz and parsed.get("plz"):
                        plz = parsed["plz"]
                    if parsed.get("stadt"):
                        stadt = parsed["stadt"]

        return Address(
            strasse=strasse,
            hausnummer=hausnummer,
            plz=plz,
            stadt=stadt,
            bundesland=bundesland
        )

    def _parse_street(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Trennt Straße und Hausnummer."""
        if not text:
            return None, None

        # Pattern: "Hauptstraße 42" oder "Hauptstr. 42a"
        match = re.match(r"^(.+?)\s+(\d+\s*[a-zA-Z]?)$", text.strip())
        if match:
            return match.group(1).strip(), match.group(2).strip()

        return text.strip(), None

    def _parse_address_text(self, text: str) -> Optional[Dict[str, str]]:
        """Parst einen Adress-String in Komponenten."""
        result = {}

        # PLZ + Stadt
        plz_match = re.search(r"(\d{5})\s+([A-Za-zäöüßÄÖÜ\-\s]+)", text)
        if plz_match:
            result["plz"] = plz_match.group(1)
            result["stadt"] = plz_match.group(2).strip()

        # Straße (vor der PLZ)
        street_match = re.search(
            r"([A-Za-zäöüßÄÖÜ\.\-]+(?:str\.|straße|weg|platz|allee|ring|gasse|damm|ufer)?)\s*(\d+\s*[a-zA-Z]?)?",
            text,
            re.IGNORECASE
        )
        if street_match:
            result["strasse"] = street_match.group(1).strip()
            if street_match.group(2):
                result["hausnummer"] = street_match.group(2).strip()

        return result if result else None

    def _extract_phone(self, soup: BeautifulSoup) -> Tuple[Optional[str], Optional[str]]:
        """Extrahiert Telefonnummer und optionalen Zusatz."""
        phone = None
        zusatz = None

        phone_selectors = [
            "a[href^='tel:']",
            "[itemprop='telephone']",
            ".mod-TeilnehmerKopf__telefon",
            ".telefon",
            ".phone"
        ]

        for selector in phone_selectors:
            elem = soup.select_one(selector)
            if elem:
                if elem.name == "a" and elem.get("href", "").startswith("tel:"):
                    phone = elem.get("href")[4:]  # Entferne "tel:"
                else:
                    phone = elem.get_text(strip=True)

                # Zusatz extrahieren (z.B. "Zentrale", "Mobil")
                parent = elem.parent
                if parent:
                    label = parent.find(["span", "label"], class_=re.compile(r"label|typ", re.I))
                    if label:
                        zusatz = label.get_text(strip=True)

                if phone:
                    phone = self._clean_phone(phone)
                    if phone:
                        break

        return phone, zusatz

    def _extract_fax(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrahiert die Faxnummer."""
        fax_selectors = [
            "[itemprop='faxNumber']",
            ".fax",
            "a[href^='fax:']"
        ]

        for selector in fax_selectors:
            elem = soup.select_one(selector)
            if elem:
                fax = elem.get_text(strip=True)
                fax = self._clean_phone(fax)
                if fax:
                    return fax

        # Fallback: Suche nach "Fax" Label
        for label in soup.find_all(string=re.compile(r"Fax", re.I)):
            parent = label.find_parent()
            if parent:
                fax_text = parent.get_text()
                fax_match = re.search(r"Fax[:\s]*([\d\s\-/+]+)", fax_text, re.I)
                if fax_match:
                    fax = self._clean_phone(fax_match.group(1))
                    if fax:
                        return fax

        return None

    def _extract_email(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrahiert die E-Mail-Adresse."""
        email_selectors = [
            "a[href^='mailto:']",
            "[itemprop='email']",
            ".email",
            ".mail"
        ]

        for selector in email_selectors:
            elem = soup.select_one(selector)
            if elem:
                if elem.name == "a" and elem.get("href", "").startswith("mailto:"):
                    email = elem.get("href")[7:]  # Entferne "mailto:"
                    # Entferne Query-Parameter
                    email = email.split("?")[0]
                else:
                    email = elem.get_text(strip=True)

                email = email.strip().lower()
                if self._is_valid_email(email):
                    return email

        # Fallback: Regex im gesamten Text
        text = soup.get_text()
        email_match = re.search(
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            text
        )
        if email_match:
            email = email_match.group(0).lower()
            if self._is_valid_email(email):
                return email

        return None

    def _extract_website(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrahiert die Website-URL."""
        website_selectors = [
            "a[data-wipe-name='Website']",
            "a.mod-TeilnehmerKopf__website",
            "[itemprop='url']",
            "a.website"
        ]

        for selector in website_selectors:
            elem = soup.select_one(selector)
            if elem:
                href = elem.get("href", "")

                # Gelbe Seiten Redirect-URL
                if "redirect" in href or "url=" in href:
                    url_match = re.search(r"[?&]url=([^&]+)", href)
                    if url_match:
                        website_url = unquote(url_match.group(1))
                        if self._is_valid_website(website_url):
                            return website_url

                elif href.startswith("http") and "gelbeseiten.de" not in href:
                    if self._is_valid_website(href):
                        return href

        return None

    def _extract_branche(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrahiert die Branche/Kategorie."""
        branche_selectors = [
            ".mod-TeilnehmerKopf__branchen",
            "[itemprop='description']",
            ".branchen",
            ".kategorie",
            ".branche"
        ]

        for selector in branche_selectors:
            elem = soup.select_one(selector)
            if elem:
                branche = elem.get_text(strip=True)
                branche = self._clean_text(branche)
                if branche and len(branche) > 2:
                    # Kürze lange Branchenbeschreibungen
                    if len(branche) > 100:
                        branche = branche[:97] + "..."
                    return branche

        return None

    def _extract_rating(self, soup: BeautifulSoup) -> Tuple[Optional[float], Optional[int]]:
        """Extrahiert Bewertungsinformationen."""
        rating = None
        count = None

        rating_container = soup.select_one(
            ".mod-Bewertung, .bewertung, [itemprop='aggregateRating']"
        )

        if rating_container:
            # Bewertungswert
            value_elem = rating_container.select_one(
                "[itemprop='ratingValue'], .wert, .value"
            )
            if value_elem:
                try:
                    value_text = value_elem.get_text(strip=True)
                    rating = float(value_text.replace(",", "."))
                    rating = min(5.0, max(0.0, rating))
                except ValueError:
                    pass

            # Anzahl
            count_elem = rating_container.select_one(
                "[itemprop='reviewCount'], .anzahl, .count"
            )
            if count_elem:
                try:
                    count_text = count_elem.get_text(strip=True)
                    count_match = re.search(r"(\d+)", count_text)
                    if count_match:
                        count = int(count_match.group(1))
                except ValueError:
                    pass

        return rating, count

    def _extract_opening_hours(self, soup: BeautifulSoup) -> Optional[Dict[str, str]]:
        """Extrahiert Öffnungszeiten."""
        hours = {}

        hours_container = soup.select_one(
            ".mod-Oeffnungszeiten, .oeffnungszeiten, [itemprop='openingHours']"
        )

        if hours_container:
            # Suche nach Tabellenzeilen oder Liste
            rows = hours_container.select("tr, li, .row")

            for row in rows:
                text = row.get_text(separator=" ", strip=True)
                # Pattern: "Montag: 09:00 - 18:00" oder "Mo-Fr 9-18"
                day_match = re.search(
                    r"(Mo(?:ntag)?|Di(?:enstag)?|Mi(?:ttwoch)?|Do(?:nnerstag)?|Fr(?:eitag)?|Sa(?:mstag)?|So(?:nntag)?)",
                    text,
                    re.I
                )
                time_match = re.search(r"(\d{1,2}[:.]\d{2})\s*[-–]\s*(\d{1,2}[:.]\d{2})", text)

                if day_match and time_match:
                    day = self._normalize_day(day_match.group(1))
                    hours[day] = f"{time_match.group(1)} - {time_match.group(2)}"

        return hours if hours else None

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrahiert die Firmenbeschreibung."""
        desc_selectors = [
            ".mod-TeilnehmerInfo__beschreibung",
            ".beschreibung",
            "[itemprop='description']",
            ".about"
        ]

        for selector in desc_selectors:
            elem = soup.select_one(selector)
            if elem:
                desc = elem.get_text(strip=True)
                desc = self._clean_text(desc)
                if desc and len(desc) > 20:
                    # Kürze sehr lange Beschreibungen
                    if len(desc) > 500:
                        desc = desc[:497] + "..."
                    return desc

        return None

    def _clean_text(self, text: str) -> str:
        """Bereinigt Text."""
        if not text:
            return ""
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _clean_phone(self, phone: str) -> Optional[str]:
        """Bereinigt Telefonnummer."""
        if not phone:
            return None
        # Behalte nur Ziffern, +, -, /, Leerzeichen
        cleaned = re.sub(r"[^\d+\-/\s]", "", phone)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        # Mindestens 6 Ziffern
        if len(re.sub(r"\D", "", cleaned)) >= 6:
            return cleaned
        return None

    def _is_valid_email(self, email: str) -> bool:
        """Prüft ob E-Mail-Format valide."""
        if not email:
            return False
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))

    def _is_valid_website(self, url: str) -> bool:
        """Prüft ob Website-URL valide."""
        if not url:
            return False
        # Muss mit http:// oder https:// beginnen
        if not url.startswith(("http://", "https://")):
            return False
        # Nicht die eigene Domain
        if "gelbeseiten.de" in url:
            return False
        return True

    def _normalize_day(self, day: str) -> str:
        """Normalisiert Wochentag-Abkürzungen."""
        day_map = {
            "mo": "Montag", "montag": "Montag",
            "di": "Dienstag", "dienstag": "Dienstag",
            "mi": "Mittwoch", "mittwoch": "Mittwoch",
            "do": "Donnerstag", "donnerstag": "Donnerstag",
            "fr": "Freitag", "freitag": "Freitag",
            "sa": "Samstag", "samstag": "Samstag",
            "so": "Sonntag", "sonntag": "Sonntag"
        }
        return day_map.get(day.lower(), day)

    @property
    def stats(self) -> dict:
        """Gibt Parser-Statistiken zurück."""
        return {
            "parsed_count": self._parsed_count,
            "error_count": self._error_count
        }
