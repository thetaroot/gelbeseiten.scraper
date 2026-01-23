"""
Parser für Gelbe Seiten Suchergebnis-Seiten (Listings).

Extrahiert Basis-Informationen aus den Suchergebnis-Karten.
"""

import re
import logging
from typing import List, Optional, Tuple
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from src.models.lead import RawListing


logger = logging.getLogger(__name__)


class ListingParser:
    """
    Parser für Gelbe Seiten Suchergebnis-Seiten.

    Extrahiert aus jeder Ergebniskarte:
    - Firmenname
    - Detail-URL
    - Telefon (falls sichtbar)
    - Adresse (Roh-String)
    - Branche
    - Website (ja/nein + URL)
    - Bewertung
    """

    BASE_URL = "https://www.gelbeseiten.de"

    def __init__(self):
        """Initialisiert den Parser."""
        self._parsed_count = 0
        self._error_count = 0

    def parse(self, html: str, source_url: str = "") -> List[RawListing]:
        """
        Parst eine Suchergebnis-Seite.

        Args:
            html: Der HTML-Content der Seite.
            source_url: Die URL der Seite (für Logging).

        Returns:
            Liste von RawListing Objekten.
        """
        listings = []

        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception as e:
            logger.error(f"Fehler beim Parsen von HTML: {e}")
            return listings

        # Finde alle Ergebniskarten
        # Gelbe Seiten verwendet verschiedene Selektoren
        article_selectors = [
            "article[data-realid]",
            "article.mod-Treffer",
            "article.teilnehmer",
            "div.mod-Treffer",
            "[data-teilnehmerid]"
        ]

        articles = []
        for selector in article_selectors:
            articles = soup.select(selector)
            if articles:
                logger.debug(f"Gefunden mit Selector '{selector}': {len(articles)} Einträge")
                break

        if not articles:
            # Fallback: Suche nach typischen Strukturen
            articles = self._find_articles_fallback(soup)

        for article in articles:
            try:
                listing = self._parse_article(article)
                if listing:
                    listings.append(listing)
                    self._parsed_count += 1
            except Exception as e:
                logger.warning(f"Fehler beim Parsen eines Artikels: {e}")
                self._error_count += 1

        logger.info(f"Geparst: {len(listings)} Listings von {source_url}")
        return listings

    def _find_articles_fallback(self, soup: BeautifulSoup) -> List[Tag]:
        """
        Fallback-Methode um Artikel zu finden.

        Sucht nach typischen Mustern in der Struktur.
        """
        articles = []

        # Suche nach Containern mit typischen Klassen
        for container in soup.find_all(["article", "div", "li"]):
            # Prüfe ob es wie ein Eintrag aussieht
            has_name = container.find(["h2", "h3", "a"], class_=re.compile(r"name|title|firma", re.I))
            has_address = container.find(string=re.compile(r"\d{5}"))  # PLZ
            has_phone = container.find(string=re.compile(r"(\d[\d\s\-/]+){6,}"))

            if has_name and (has_address or has_phone):
                articles.append(container)

        return articles

    def _parse_article(self, article: Tag) -> Optional[RawListing]:
        """
        Parst einen einzelnen Artikel/Eintrag.

        Args:
            article: Das BeautifulSoup Tag des Artikels.

        Returns:
            RawListing oder None wenn Parsing fehlschlägt.
        """
        # Firmenname und Detail-URL
        name, detail_url = self._extract_name_and_url(article)
        if not name or not detail_url:
            return None

        # Telefon
        telefon = self._extract_phone(article)

        # Adresse
        adresse_raw = self._extract_address(article)

        # Branche
        branche = self._extract_branche(article)

        # Website
        hat_website, website_url = self._extract_website(article)

        # Bewertung
        bewertung, bewertung_anzahl = self._extract_rating(article)

        return RawListing(
            name=name,
            detail_url=detail_url,
            telefon=telefon,
            adresse_raw=adresse_raw,
            branche=branche,
            hat_website=hat_website,
            website_url=website_url,
            bewertung=bewertung,
            bewertung_anzahl=bewertung_anzahl
        )

    def _extract_name_and_url(self, article: Tag) -> Tuple[Optional[str], Optional[str]]:
        """Extrahiert Firmennamen und Detail-URL."""
        name = None
        url = None

        # Verschiedene Selektoren für den Namen
        name_selectors = [
            "h2 a",
            "h2.mod-Treffer__name a",
            "a.mod-Treffer--bestEntryLink",
            "a.gs-name",
            "a[data-wipe-name='Name']",
            ".name a",
            "h2",
            "h3 a"
        ]

        for selector in name_selectors:
            elem = article.select_one(selector)
            if elem:
                name = elem.get_text(strip=True)
                if elem.name == "a" and elem.get("href"):
                    url = elem.get("href")
                elif elem.find("a"):
                    url = elem.find("a").get("href")
                else:
                    # Prüfe ob Parent ein <a> mit href ist (z.B. <a><h2>Name</h2></a>)
                    parent = elem.parent
                    if parent and parent.name == "a" and parent.get("href"):
                        url = parent.get("href")
                break

        # Falls URL immer noch None, suche nach Detail-Link im Article
        if name and not url:
            # Suche nach dem Haupt-Link zum Firmeneintrag
            link_selectors = [
                "a[href*='/gsbiz/']",
                "a[data-realid]",
                "a[data-tnid]",
                "a[href*='gelbeseiten.de']"
            ]
            for selector in link_selectors:
                link = article.select_one(selector)
                if link and link.get("href"):
                    href = link.get("href")
                    # Nur Detail-Links, keine externen oder Redirect-Links
                    if "/gsbiz/" in href or (href.startswith("/") and "redirect" not in href):
                        url = href
                        break

        # URL normalisieren
        if url and not url.startswith("http"):
            url = urljoin(self.BASE_URL, url)

        # Name bereinigen
        if name:
            name = self._clean_text(name)

        return name, url

    def _extract_phone(self, article: Tag) -> Optional[str]:
        """Extrahiert die Telefonnummer."""
        phone_selectors = [
            "a[href^='tel:']",
            "span.mod-Treffer__phoneNumber",
            "[data-wipe-name='Anruf']",
            ".phone",
            ".telefon"
        ]

        for selector in phone_selectors:
            elem = article.select_one(selector)
            if elem:
                phone = elem.get_text(strip=True)
                # Bereinigen
                phone = re.sub(r"[^\d\s\+\-/()]", "", phone)
                phone = phone.strip()
                if len(phone) >= 6:  # Mindestlänge für Telefonnummer
                    return phone

        # Fallback: Regex-Suche
        text = article.get_text()
        phone_match = re.search(r"(?:Tel\.?|Telefon)?[:\s]*([\d\s\-/]+\d)", text)
        if phone_match:
            phone = phone_match.group(1).strip()
            if len(re.sub(r"\D", "", phone)) >= 6:
                return phone

        return None

    def _extract_address(self, article: Tag) -> Optional[str]:
        """Extrahiert die Adresse als Roh-String."""
        address_selectors = [
            "address",
            ".mod-Treffer__address",
            ".address",
            ".adresse",
            "[itemprop='address']"
        ]

        for selector in address_selectors:
            elem = article.select_one(selector)
            if elem:
                address = elem.get_text(separator=" ", strip=True)
                address = self._clean_text(address)
                if address:
                    return address

        # Fallback: Suche nach PLZ-Pattern
        text = article.get_text()
        # Deutsches Adress-Pattern: Straße Nr, PLZ Stadt
        address_match = re.search(
            r"([A-Za-zäöüßÄÖÜ\.\-]+\s*(?:str\.|straße|weg|platz|allee|gasse)?\s*\d+[a-zA-Z]?)[,\s]+(\d{5})\s+([A-Za-zäöüßÄÖÜ\-]+)",
            text,
            re.IGNORECASE
        )
        if address_match:
            return f"{address_match.group(1)}, {address_match.group(2)} {address_match.group(3)}"

        # Nur PLZ + Stadt
        plz_match = re.search(r"(\d{5})\s+([A-Za-zäöüßÄÖÜ\-]+)", text)
        if plz_match:
            return f"{plz_match.group(1)} {plz_match.group(2)}"

        return None

    def _extract_branche(self, article: Tag) -> Optional[str]:
        """Extrahiert die Branche/Kategorie."""
        branche_selectors = [
            ".mod-Treffer__branchen",
            ".branchen",
            ".branche",
            ".category",
            "[itemprop='description']"
        ]

        for selector in branche_selectors:
            elem = article.select_one(selector)
            if elem:
                branche = elem.get_text(strip=True)
                branche = self._clean_text(branche)
                if branche:
                    return branche

        return None

    def _extract_website(self, article: Tag) -> Tuple[bool, Optional[str]]:
        """
        Extrahiert Website-Information.

        Returns:
            Tuple (hat_website, website_url)
        """
        website_selectors = [
            "a[data-wipe-name='Website']",
            "a.mod-Treffer__link--website",
            "a.website",
            "a[href*='redirect']",  # Gelbe Seiten leitet oft um
        ]

        for selector in website_selectors:
            elem = article.select_one(selector)
            if elem:
                href = elem.get("href", "")
                # Gelbe Seiten verwendet oft Redirect-URLs
                # Format: /redirect?...url=ECHTE_URL...
                if "redirect" in href or "url=" in href:
                    url_match = re.search(r"[?&]url=([^&]+)", href)
                    if url_match:
                        from urllib.parse import unquote
                        website_url = unquote(url_match.group(1))
                        return True, website_url
                elif href.startswith("http"):
                    # Direkte URL (selten)
                    if "gelbeseiten.de" not in href:
                        return True, href

                # Hat Website-Link, URL aber nicht extrahierbar
                return True, None

        # Prüfe ob "Website" Text vorhanden
        text = article.get_text().lower()
        if "website" in text or "homepage" in text:
            return True, None

        return False, None

    def _extract_rating(self, article: Tag) -> Tuple[Optional[float], Optional[int]]:
        """
        Extrahiert Bewertungsinformationen.

        Returns:
            Tuple (bewertung, anzahl)
        """
        rating = None
        count = None

        rating_selectors = [
            ".mod-Treffer__bewertung",
            ".bewertung",
            ".rating",
            "[itemprop='ratingValue']"
        ]

        for selector in rating_selectors:
            elem = article.select_one(selector)
            if elem:
                # Versuche Stern-Bewertung zu extrahieren
                rating_text = elem.get_text(strip=True)

                # Pattern: "4,5" oder "4.5"
                rating_match = re.search(r"(\d[,.\d]*)", rating_text)
                if rating_match:
                    try:
                        rating = float(rating_match.group(1).replace(",", "."))
                        rating = min(5.0, max(0.0, rating))  # Clamp 0-5
                    except ValueError:
                        pass

                # Anzahl: "(123)" oder "123 Bewertungen"
                count_match = re.search(r"\((\d+)\)|(\d+)\s*Bewertung", rating_text)
                if count_match:
                    try:
                        count = int(count_match.group(1) or count_match.group(2))
                    except ValueError:
                        pass

                break

        # Alternative: Sterne zählen
        if rating is None:
            stars = article.select(".star, .stern, [class*='star']")
            filled_stars = [s for s in stars if "filled" in str(s.get("class", [])).lower()
                          or "active" in str(s.get("class", [])).lower()]
            if stars:
                rating = len(filled_stars)

        return rating, count

    def _clean_text(self, text: str) -> str:
        """Bereinigt Text von überflüssigen Whitespace etc."""
        if not text:
            return ""
        # Mehrfache Whitespace reduzieren
        text = re.sub(r"\s+", " ", text)
        # Trim
        text = text.strip()
        return text

    def extract_pagination_info(self, html: str) -> Tuple[int, int, bool]:
        """
        Extrahiert Pagination-Informationen.

        Args:
            html: Der HTML-Content.

        Returns:
            Tuple (aktuelle_seite, gesamt_seiten, hat_naechste_seite)
        """
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            return 1, 1, False

        current_page = 1
        total_pages = 1
        has_next = False

        # Suche Pagination-Element
        pagination = soup.select_one(".mod-Pagination, .pagination, nav[aria-label*='Seite']")

        if pagination:
            # Aktuelle Seite
            current = pagination.select_one(".current, .active, [aria-current='page']")
            if current:
                try:
                    current_page = int(current.get_text(strip=True))
                except ValueError:
                    pass

            # Letzte Seite
            page_links = pagination.select("a[href*='seite']")
            for link in page_links:
                try:
                    page_num = int(link.get_text(strip=True))
                    total_pages = max(total_pages, page_num)
                except ValueError:
                    pass

            # Nächste-Seite-Link
            next_link = pagination.select_one("a[rel='next'], a.next, a:contains('Weiter')")
            has_next = next_link is not None

        # Fallback: URL-basiert
        if total_pages == 1:
            next_link = soup.select_one("a[href*='seite-']")
            if next_link:
                href = next_link.get("href", "")
                page_match = re.search(r"seite-(\d+)", href)
                if page_match:
                    total_pages = max(total_pages, int(page_match.group(1)))
                    has_next = True

        return current_page, total_pages, has_next

    def extract_total_results(self, html: str) -> Optional[int]:
        """
        Extrahiert die Gesamtanzahl der Ergebnisse.

        Args:
            html: Der HTML-Content.

        Returns:
            Anzahl oder None wenn nicht gefunden.
        """
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            return None

        # Verschiedene Patterns
        result_selectors = [
            ".mod-Suche__headline",
            ".result-count",
            ".treffer-anzahl"
        ]

        for selector in result_selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text()
                # Pattern: "123 Treffer" oder "ca. 1.234 Ergebnisse"
                match = re.search(r"([\d.]+)\s*(?:Treffer|Ergebnisse|Einträge)", text)
                if match:
                    try:
                        return int(match.group(1).replace(".", ""))
                    except ValueError:
                        pass

        return None

    @property
    def stats(self) -> dict:
        """Gibt Parser-Statistiken zurück."""
        return {
            "parsed_count": self._parsed_count,
            "error_count": self._error_count
        }
