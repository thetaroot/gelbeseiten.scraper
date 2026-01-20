"""
HTML-basierte Analyse zur Website-Alters-Erkennung.

Lädt die Startseite und analysiert HTML-Struktur und Meta-Tags.
"""

import re
import logging
from typing import List, Optional, Set
from dataclasses import dataclass
from enum import Enum

from bs4 import BeautifulSoup

from src.client.http import HTTPClient


logger = logging.getLogger(__name__)


class HTMLResult(str, Enum):
    """Ergebnis der HTML-Analyse."""
    DEFINITIV_ALT = "definitiv_alt"
    WAHRSCHEINLICH_ALT = "wahrscheinlich_alt"
    UNKLAR = "unklar"
    WAHRSCHEINLICH_MODERN = "wahrscheinlich_modern"
    FEHLER = "fehler"


@dataclass
class HTMLAnalysisResult:
    """Ergebnis der HTML-Analyse."""
    result: HTMLResult
    confidence: float
    signals: List[str]
    detected_cms: Optional[str]
    detected_tech: List[str]
    elapsed_ms: int


# Alte CMS-Versionen (im Generator-Tag)
OLD_CMS_PATTERNS = [
    # WordPress alt
    (r"WordPress\s+[1-3]\.", "wordpress_1_3", HTMLResult.DEFINITIV_ALT),
    (r"WordPress\s+4\.[0-5]", "wordpress_4_early", HTMLResult.WAHRSCHEINLICH_ALT),
    (r"WordPress\s+4\.[6-9]", "wordpress_4_late", HTMLResult.WAHRSCHEINLICH_ALT),

    # Joomla alt
    (r"Joomla!\s+1\.", "joomla_1", HTMLResult.DEFINITIV_ALT),
    (r"Joomla!\s+2\.", "joomla_2", HTMLResult.WAHRSCHEINLICH_ALT),
    (r"Joomla!\s+3\.[0-5]", "joomla_3_early", HTMLResult.WAHRSCHEINLICH_ALT),

    # Drupal alt
    (r"Drupal\s+[1-6]", "drupal_old", HTMLResult.DEFINITIV_ALT),
    (r"Drupal\s+7", "drupal_7", HTMLResult.WAHRSCHEINLICH_ALT),

    # TYPO3 alt
    (r"TYPO3\s+[1-5]\.", "typo3_old", HTMLResult.WAHRSCHEINLICH_ALT),
    (r"TYPO3\s+6\.", "typo3_6", HTMLResult.WAHRSCHEINLICH_ALT),

    # Andere alte CMS
    (r"Contao\s+[1-3]\.", "contao_old", HTMLResult.WAHRSCHEINLICH_ALT),
    (r"REDAXO\s+[1-4]\.", "redaxo_old", HTMLResult.WAHRSCHEINLICH_ALT),
    (r"Weblication", "weblication", HTMLResult.WAHRSCHEINLICH_ALT),
    (r"WebsiteBaker", "websitebaker", HTMLResult.WAHRSCHEINLICH_ALT),
    (r"CMSimple", "cmsimple", HTMLResult.WAHRSCHEINLICH_ALT),
    (r"phpwcms", "phpwcms", HTMLResult.WAHRSCHEINLICH_ALT),

    # Sehr alte Editoren
    (r"Microsoft FrontPage", "frontpage", HTMLResult.DEFINITIV_ALT),
    (r"Dreamweaver", "dreamweaver", HTMLResult.WAHRSCHEINLICH_ALT),
    (r"GoLive", "golive", HTMLResult.DEFINITIV_ALT),
    (r"Nvu", "nvu", HTMLResult.DEFINITIV_ALT),
    (r"KompoZer", "kompozer", HTMLResult.DEFINITIV_ALT),
    (r"Microsoft Word", "ms_word", HTMLResult.DEFINITIV_ALT),
]

# Moderne CMS/Frameworks
MODERN_CMS_PATTERNS = [
    (r"WordPress\s+[56]\.", "wordpress_modern"),
    (r"Joomla!\s+[45]\.", "joomla_modern"),
    (r"Drupal\s+([89]|10)", "drupal_modern"),
    (r"TYPO3\s+(1[0-3]|[89])\.", "typo3_modern"),
    (r"Shopify", "shopify"),
    (r"Wix\.com", "wix"),
    (r"Squarespace", "squarespace"),
    (r"Webflow", "webflow"),
    (r"Next\.js", "nextjs"),
    (r"Gatsby", "gatsby"),
]

# Alte JavaScript-Bibliotheken
OLD_JS_PATTERNS = [
    (r"jquery[.-]1\.[0-9]\.", "jquery_1_x"),
    (r"jquery\.min\.js\?ver=1\.", "jquery_1_x"),
    (r"prototype\.js", "prototype_js"),
    (r"mootools", "mootools"),
    (r"scriptaculous", "scriptaculous"),
    (r"dojo\.js", "dojo_old"),
    (r"yui-min\.js", "yui"),
    (r"swfobject", "swfobject"),  # Flash-Integration
]

# HTML-Struktur-Indikatoren für alte Websites
OLD_HTML_INDICATORS = [
    # Kein Viewport = nicht responsive
    "no_viewport_meta",
    # Tabellen-Layout
    "table_layout",
    # Inline-Styles exzessiv
    "excessive_inline_styles",
    # Frames/Iframes für Layout
    "frameset",
    # Flash-Embeds
    "flash_embed",
    # Alte Doctype
    "old_doctype",
    # Font-Tags
    "font_tags",
    # Center-Tags
    "center_tags",
    # Marquee
    "marquee_tags",
    # Blink
    "blink_tags",
]


class HTMLScanner:
    """
    Analysiert HTML-Inhalt zur Alters-Erkennung.

    Prüft:
    - Meta Generator Tag (CMS/Version)
    - Viewport Meta (Responsive)
    - JavaScript-Bibliotheken
    - HTML-Struktur (Tabellen-Layout, etc.)
    - Veraltete HTML-Elemente
    """

    def __init__(self, http_client: HTTPClient):
        """
        Initialisiert den HTML-Scanner.

        Args:
            http_client: Konfigurierter HTTP Client.
        """
        self._client = http_client
        self._scanned_count = 0

    def scan(self, url: str) -> HTMLAnalysisResult:
        """
        Lädt und analysiert die Startseite.

        Args:
            url: Die zu analysierende URL.

        Returns:
            HTMLAnalysisResult mit Ergebnis.
        """
        self._scanned_count += 1

        # GET Request
        response = self._client.get(url, timeout=15.0)

        if not response.success:
            return HTMLAnalysisResult(
                result=HTMLResult.FEHLER,
                confidence=0.0,
                signals=[f"request_failed_{response.status_code}"],
                detected_cms=None,
                detected_tech=[],
                elapsed_ms=response.elapsed_ms
            )

        return self._analyze_html(response.content, response.elapsed_ms)

    def _analyze_html(self, html: str, elapsed_ms: int) -> HTMLAnalysisResult:
        """Analysiert den HTML-Content."""
        signals = []
        detected_cms = None
        detected_tech = []

        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception as e:
            logger.warning(f"Fehler beim Parsen des HTML: {e}")
            return HTMLAnalysisResult(
                result=HTMLResult.FEHLER,
                confidence=0.0,
                signals=["html_parse_error"],
                detected_cms=None,
                detected_tech=[],
                elapsed_ms=elapsed_ms
            )

        # 1. Generator Meta Tag
        cms_result = self._check_generator(soup)
        if cms_result:
            cms_signals, detected_cms = cms_result
            signals.extend(cms_signals)

        # 2. Viewport Check
        if not self._has_viewport(soup):
            signals.append("no_viewport_meta")

        # 3. JavaScript-Bibliotheken
        js_signals = self._check_javascript(soup, html)
        signals.extend(js_signals)
        detected_tech.extend([s.replace("_", " ") for s in js_signals if "jquery" in s or "prototype" in s])

        # 4. HTML-Struktur
        structure_signals = self._check_html_structure(soup, html)
        signals.extend(structure_signals)

        # 5. Doctype
        doctype_signal = self._check_doctype(html)
        if doctype_signal:
            signals.append(doctype_signal)

        # 6. Deprecated Tags
        deprecated_signals = self._check_deprecated_tags(soup)
        signals.extend(deprecated_signals)

        # 7. Flash/ActiveX
        flash_signals = self._check_flash(soup)
        signals.extend(flash_signals)

        # 8. Moderne Signale
        modern_signals = self._check_modern_indicators(soup, html)
        if modern_signals:
            signals.extend(modern_signals)

        # Gesamtergebnis berechnen
        result, confidence = self._calculate_result(signals)

        return HTMLAnalysisResult(
            result=result,
            confidence=confidence,
            signals=signals,
            detected_cms=detected_cms,
            detected_tech=detected_tech,
            elapsed_ms=elapsed_ms
        )

    def _check_generator(self, soup: BeautifulSoup) -> Optional[tuple]:
        """Prüft Meta Generator Tag."""
        generator = soup.find("meta", attrs={"name": re.compile(r"generator", re.I)})

        if not generator:
            return None

        content = generator.get("content", "")
        signals = []
        detected_cms = None

        # Alte CMS prüfen
        for pattern, signal, result in OLD_CMS_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                signals.append(f"cms_{signal}")
                detected_cms = signal
                return signals, detected_cms

        # Moderne CMS prüfen
        for pattern, signal in MODERN_CMS_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                signals.append(f"cms_modern_{signal}")
                detected_cms = f"modern_{signal}"
                return signals, detected_cms

        # Unbekanntes CMS
        if content:
            detected_cms = "unknown"

        return signals, detected_cms

    def _has_viewport(self, soup: BeautifulSoup) -> bool:
        """Prüft ob Viewport Meta vorhanden ist."""
        viewport = soup.find("meta", attrs={"name": "viewport"})
        return viewport is not None

    def _check_javascript(self, soup: BeautifulSoup, html: str) -> List[str]:
        """Prüft auf alte JavaScript-Bibliotheken."""
        signals = []

        # Script-Tags durchsuchen
        scripts = soup.find_all("script", src=True)
        script_srcs = " ".join([s.get("src", "") for s in scripts])

        # Auch Inline-Scripts und ganzes HTML durchsuchen
        search_text = script_srcs + " " + html[:50000]  # Begrenzen für Performance

        for pattern, signal in OLD_JS_PATTERNS:
            if re.search(pattern, search_text, re.IGNORECASE):
                signals.append(f"js_{signal}")

        return signals

    def _check_html_structure(self, soup: BeautifulSoup, html: str) -> List[str]:
        """Prüft HTML-Struktur auf Alters-Indikatoren."""
        signals = []

        # Tabellen-Layout (viele nested Tables)
        tables = soup.find_all("table")
        nested_tables = sum(1 for t in tables if t.find("table"))
        if nested_tables >= 2:
            signals.append("table_layout")

        # Excessive Inline-Styles
        elements_with_style = soup.find_all(style=True)
        if len(elements_with_style) > 50:
            signals.append("excessive_inline_styles")

        # Framesets (HTML4)
        if soup.find("frameset") or soup.find("frame"):
            signals.append("frameset")

        return signals

    def _check_doctype(self, html: str) -> Optional[str]:
        """Prüft den Doctype."""
        # Erste 500 Zeichen durchsuchen
        header = html[:500].lower()

        # Alte Doctypes
        if "xhtml 1.0 transitional" in header:
            return "doctype_xhtml_transitional"
        if "xhtml 1.0 strict" in header:
            return "doctype_xhtml_strict"
        if "html 4.01" in header:
            return "doctype_html4"
        if "html 3.2" in header:
            return "doctype_html3"

        # Kein Doctype
        if "<!doctype" not in header:
            return "no_doctype"

        return None

    def _check_deprecated_tags(self, soup: BeautifulSoup) -> List[str]:
        """Prüft auf veraltete HTML-Tags."""
        signals = []

        deprecated_tags = {
            "font": "font_tags",
            "center": "center_tags",
            "marquee": "marquee_tags",
            "blink": "blink_tags",
            "basefont": "basefont_tags",
            "big": "big_tags",
            "strike": "strike_tags",
            "tt": "tt_tags",
            "applet": "applet_tags",
        }

        for tag, signal in deprecated_tags.items():
            if soup.find(tag):
                signals.append(signal)

        return signals

    def _check_flash(self, soup: BeautifulSoup) -> List[str]:
        """Prüft auf Flash/ActiveX Embeds."""
        signals = []

        # Object-Tags für Flash
        objects = soup.find_all("object")
        for obj in objects:
            classid = obj.get("classid", "").lower()
            type_attr = obj.get("type", "").lower()
            if "flash" in classid or "flash" in type_attr or "shockwave" in type_attr:
                signals.append("flash_embed")
                break

        # Embed-Tags für Flash
        embeds = soup.find_all("embed")
        for embed in embeds:
            type_attr = embed.get("type", "").lower()
            src = embed.get("src", "").lower()
            if "flash" in type_attr or ".swf" in src:
                signals.append("flash_embed")
                break

        # ActiveX
        for obj in objects:
            classid = obj.get("classid", "").lower()
            if "clsid:" in classid:
                signals.append("activex_embed")
                break

        return signals

    def _check_modern_indicators(self, soup: BeautifulSoup, html: str) -> List[str]:
        """Prüft auf moderne Web-Technologien."""
        signals = []

        # Schema.org strukturierte Daten
        if soup.find(attrs={"itemtype": re.compile(r"schema\.org", re.I)}):
            signals.append("modern_schema_org")

        # Open Graph Tags
        if soup.find("meta", property=re.compile(r"og:", re.I)):
            signals.append("modern_open_graph")

        # Twitter Cards
        if soup.find("meta", attrs={"name": re.compile(r"twitter:", re.I)}):
            signals.append("modern_twitter_cards")

        # Service Worker
        if "serviceworker" in html.lower() or "service-worker" in html.lower():
            signals.append("modern_service_worker")

        # Modern CSS (Flexbox/Grid in Style-Tags)
        styles = soup.find_all("style")
        style_content = " ".join([s.get_text() for s in styles])
        if "display: flex" in style_content or "display: grid" in style_content:
            signals.append("modern_css_layout")

        # React/Vue/Angular Signale
        if soup.find(id="__next") or soup.find(id="__nuxt"):
            signals.append("modern_spa_framework")
        if soup.find(attrs={"data-reactroot": True}):
            signals.append("modern_react")
        if soup.find(attrs={"ng-app": True}) or soup.find(attrs={"data-ng-app": True}):
            # Achtung: AngularJS (alt) vs Angular (modern)
            pass

        return signals

    def _calculate_result(self, signals: List[str]) -> tuple:
        """Berechnet das Gesamtergebnis."""
        # Kategorisiere Signale
        definite_old = [s for s in signals if any(x in s for x in [
            "frontpage", "golive", "nvu", "kompozer", "ms_word",
            "wordpress_1_3", "joomla_1", "drupal_old", "flash_embed",
            "frameset", "doctype_html3", "doctype_html4", "activex"
        ])]

        probable_old = [s for s in signals if any(x in s for x in [
            "no_viewport", "table_layout", "font_tags", "center_tags",
            "jquery_1_x", "prototype_js", "mootools", "doctype_xhtml",
            "marquee", "blink", "cms_wordpress_4", "cms_joomla_2"
        ])]

        modern = [s for s in signals if "modern_" in s]

        # Entscheide
        if definite_old:
            return HTMLResult.DEFINITIV_ALT, 0.95

        if len(probable_old) >= 3:
            return HTMLResult.WAHRSCHEINLICH_ALT, 0.8

        if len(probable_old) >= 2:
            return HTMLResult.WAHRSCHEINLICH_ALT, 0.65

        if len(probable_old) == 1 and not modern:
            return HTMLResult.WAHRSCHEINLICH_ALT, 0.5

        if len(modern) >= 3:
            return HTMLResult.WAHRSCHEINLICH_MODERN, 0.85

        if len(modern) >= 1:
            return HTMLResult.WAHRSCHEINLICH_MODERN, 0.6

        return HTMLResult.UNKLAR, 0.3

    @property
    def scanned_count(self) -> int:
        """Anzahl gescannter Seiten."""
        return self._scanned_count
