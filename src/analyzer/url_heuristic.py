"""
URL-basierte Heuristik zur Website-Alters-Erkennung.

Analysiert URLs ohne HTTP-Request - instant und 100% sicher.
"""

import re
import logging
from typing import List, Tuple, Optional
from urllib.parse import urlparse
from dataclasses import dataclass
from enum import Enum


logger = logging.getLogger(__name__)


class HeuristicResult(str, Enum):
    """Ergebnis der URL-Heuristik."""
    DEFINITIV_ALT = "definitiv_alt"      # Klare Alt-Signale
    WAHRSCHEINLICH_ALT = "wahrscheinlich_alt"  # Starke Alt-Hinweise
    UNKLAR = "unklar"                     # Keine klaren Signale
    WAHRSCHEINLICH_MODERN = "wahrscheinlich_modern"  # Moderne Hinweise
    BAUKASTEN = "baukasten"               # Website-Baukasten erkannt


@dataclass
class URLAnalysisResult:
    """Ergebnis der URL-Analyse."""
    result: HeuristicResult
    confidence: float  # 0.0 - 1.0
    signals: List[str]
    domain: str
    is_https: bool


# Bekannte veraltete Hosting-Plattformen und Muster
OLD_HOSTING_PATTERNS = [
    # Uralt Free-Hoster (meist eingestellt oder veraltet)
    (r"\.geocities\.", "geocities_hosting", HeuristicResult.DEFINITIV_ALT),
    (r"\.tripod\.", "tripod_hosting", HeuristicResult.DEFINITIV_ALT),
    (r"\.angelfire\.", "angelfire_hosting", HeuristicResult.DEFINITIV_ALT),
    (r"\.fortunecity\.", "fortunecity_hosting", HeuristicResult.DEFINITIV_ALT),
    (r"\.homestead\.", "homestead_hosting", HeuristicResult.DEFINITIV_ALT),
    (r"\.bplaced\.", "bplaced_hosting", HeuristicResult.WAHRSCHEINLICH_ALT),
    (r"\.beepworld\.", "beepworld_hosting", HeuristicResult.DEFINITIV_ALT),
    (r"\.de\.vu$", "de_vu_domain", HeuristicResult.DEFINITIV_ALT),
    (r"\.de\.to$", "de_to_domain", HeuristicResult.DEFINITIV_ALT),
    (r"\.co\.de$", "co_de_domain", HeuristicResult.WAHRSCHEINLICH_ALT),

    # Deutsche kostenlose Hoster
    (r"\.funpic\.", "funpic_hosting", HeuristicResult.DEFINITIV_ALT),
    (r"\.ohost\.", "ohost_hosting", HeuristicResult.WAHRSCHEINLICH_ALT),
    (r"\.cwsurf\.", "cwsurf_hosting", HeuristicResult.DEFINITIV_ALT),

    # Alte Telekom/Provider-Seiten
    (r"\.t-online\.de/home/", "t_online_home", HeuristicResult.DEFINITIV_ALT),
    (r"home\.t-online\.de", "t_online_home", HeuristicResult.DEFINITIV_ALT),
    (r"\.arcor\.de/", "arcor_home", HeuristicResult.WAHRSCHEINLICH_ALT),

    # IP-basierte URLs
    (r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", "ip_based_url", HeuristicResult.WAHRSCHEINLICH_ALT),
]

# Website-Baukasten (nicht unbedingt alt, aber oft basic)
BAUKASTEN_PATTERNS = [
    (r"\.jimdo\.com", "jimdo_baukasten"),
    (r"\.jimdofree\.com", "jimdo_free"),
    (r"\.jimdosite\.com", "jimdo_site"),
    (r"\.wixsite\.com", "wix_baukasten"),
    (r"\.wix\.com", "wix_baukasten"),
    (r"\.weebly\.com", "weebly_baukasten"),
    (r"\.squarespace\.com", "squarespace_baukasten"),
    (r"\.webnode\.", "webnode_baukasten"),
    (r"\.site123\.", "site123_baukasten"),
    (r"\.strikingly\.com", "strikingly_baukasten"),
    (r"\.wordpress\.com", "wordpress_com_free"),  # .com = Free-Tier
    (r"\.blogspot\.", "blogspot"),
    (r"\.blogger\.com", "blogger"),
    (r"\.tumblr\.com", "tumblr"),
    (r"\.one\.com", "one_com"),
    (r"\.my-free-website\.", "my_free_website"),
]

# Moderne Signale (deuten auf aktuelle Website hin)
MODERN_PATTERNS = [
    (r"\.vercel\.app", "vercel_hosting"),
    (r"\.netlify\.app", "netlify_hosting"),
    (r"\.github\.io", "github_pages"),
    (r"\.pages\.dev", "cloudflare_pages"),
    (r"\.herokuapp\.com", "heroku_hosting"),
    (r"\.azurewebsites\.net", "azure_hosting"),
    (r"\.web\.app", "firebase_hosting"),
    (r"\.firebaseapp\.com", "firebase_hosting"),
]

# Verdächtige URL-Pfad-Muster
SUSPICIOUS_PATH_PATTERNS = [
    (r"/~\w+", "tilde_user_path"),  # ~/username - typisch für alte Unis/Provider
    (r"/home/\w+", "home_user_path"),
    (r"/users?/\w+", "users_path"),
    (r"/members?/\w+", "members_path"),
    (r"\.htm$", "htm_extension"),  # .htm statt .html - oft älter
    (r"/cgi-bin/", "cgi_bin_path"),  # CGI-BIN - sehr alt
    (r"\.php3$", "php3_extension"),  # PHP 3 - uralt
    (r"\.asp$", "asp_classic"),  # Classic ASP
    (r"/default\.aspx?$", "default_aspx"),  # Standard IIS
]


class URLHeuristic:
    """
    Analysiert URLs auf Alters-Indikatoren ohne HTTP-Request.

    Erkennt:
    - Veraltete Hosting-Plattformen
    - Website-Baukästen
    - Verdächtige URL-Muster
    - Fehlende HTTPS
    """

    def __init__(self):
        """Initialisiert die URL-Heuristik."""
        self._analyzed_count = 0

    def analyze(self, url: str) -> URLAnalysisResult:
        """
        Analysiert eine URL auf Alters-Indikatoren.

        Args:
            url: Die zu analysierende URL.

        Returns:
            URLAnalysisResult mit Ergebnis und Signalen.
        """
        self._analyzed_count += 1
        signals = []

        # Normalisiere URL
        url = url.strip().lower()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        try:
            parsed = urlparse(url)
        except Exception as e:
            logger.warning(f"Fehler beim Parsen der URL {url}: {e}")
            return URLAnalysisResult(
                result=HeuristicResult.UNKLAR,
                confidence=0.0,
                signals=["url_parse_error"],
                domain="",
                is_https=False
            )

        domain = parsed.netloc
        path = parsed.path
        is_https = parsed.scheme == "https"

        # HTTPS-Check
        if not is_https:
            signals.append("kein_https")

        # Prüfe auf alte Hosting-Muster
        alt_result = self._check_old_patterns(domain, path)
        if alt_result:
            result_type, pattern_signals = alt_result
            signals.extend(pattern_signals)

            confidence = 0.9 if result_type == HeuristicResult.DEFINITIV_ALT else 0.7

            return URLAnalysisResult(
                result=result_type,
                confidence=confidence,
                signals=signals,
                domain=domain,
                is_https=is_https
            )

        # Prüfe auf Baukasten
        baukasten_signals = self._check_baukasten(domain)
        if baukasten_signals:
            signals.extend(baukasten_signals)
            return URLAnalysisResult(
                result=HeuristicResult.BAUKASTEN,
                confidence=0.95,
                signals=signals,
                domain=domain,
                is_https=is_https
            )

        # Prüfe auf moderne Plattformen
        modern_signals = self._check_modern_patterns(domain)
        if modern_signals:
            signals.extend(modern_signals)
            return URLAnalysisResult(
                result=HeuristicResult.WAHRSCHEINLICH_MODERN,
                confidence=0.8,
                signals=signals,
                domain=domain,
                is_https=is_https
            )

        # Prüfe verdächtige Pfad-Muster
        path_signals = self._check_path_patterns(path)
        if path_signals:
            signals.extend(path_signals)

        # Berechne Gesamtergebnis
        if not is_https and len(signals) > 1:
            # Kein HTTPS + weitere Signale = wahrscheinlich alt
            return URLAnalysisResult(
                result=HeuristicResult.WAHRSCHEINLICH_ALT,
                confidence=0.6,
                signals=signals,
                domain=domain,
                is_https=is_https
            )

        if signals:
            # Einige Signale, aber nicht eindeutig
            return URLAnalysisResult(
                result=HeuristicResult.UNKLAR,
                confidence=0.3,
                signals=signals,
                domain=domain,
                is_https=is_https
            )

        # Keine Signale - unklar
        return URLAnalysisResult(
            result=HeuristicResult.UNKLAR,
            confidence=0.0,
            signals=signals,
            domain=domain,
            is_https=is_https
        )

    def _check_old_patterns(
        self,
        domain: str,
        path: str
    ) -> Optional[Tuple[HeuristicResult, List[str]]]:
        """Prüft auf alte Hosting-Muster."""
        signals = []
        worst_result = None

        full_url = domain + path

        for pattern, signal_name, result_type in OLD_HOSTING_PATTERNS:
            if re.search(pattern, full_url, re.IGNORECASE):
                signals.append(signal_name)
                if worst_result is None or result_type == HeuristicResult.DEFINITIV_ALT:
                    worst_result = result_type

        if signals:
            return worst_result, signals
        return None

    def _check_baukasten(self, domain: str) -> List[str]:
        """Prüft auf Website-Baukasten."""
        signals = []

        for pattern, signal_name in BAUKASTEN_PATTERNS:
            if re.search(pattern, domain, re.IGNORECASE):
                signals.append(signal_name)

        return signals

    def _check_modern_patterns(self, domain: str) -> List[str]:
        """Prüft auf moderne Hosting-Plattformen."""
        signals = []

        for pattern, signal_name in MODERN_PATTERNS:
            if re.search(pattern, domain, re.IGNORECASE):
                signals.append(f"modern_{signal_name}")

        return signals

    def _check_path_patterns(self, path: str) -> List[str]:
        """Prüft auf verdächtige Pfad-Muster."""
        signals = []

        for pattern, signal_name in SUSPICIOUS_PATH_PATTERNS:
            if re.search(pattern, path, re.IGNORECASE):
                signals.append(signal_name)

        return signals

    def is_definitely_old(self, url: str) -> bool:
        """Schnell-Check: Ist die URL definitiv alt?"""
        result = self.analyze(url)
        return result.result == HeuristicResult.DEFINITIV_ALT

    def is_baukasten(self, url: str) -> bool:
        """Schnell-Check: Ist die URL ein Baukasten?"""
        result = self.analyze(url)
        return result.result == HeuristicResult.BAUKASTEN

    def needs_further_check(self, url: str) -> bool:
        """Prüft ob weitere Checks (HEAD/HTML) nötig sind."""
        result = self.analyze(url)
        return result.result == HeuristicResult.UNKLAR

    @property
    def analyzed_count(self) -> int:
        """Anzahl analysierter URLs."""
        return self._analyzed_count


def quick_check(url: str) -> Tuple[bool, List[str]]:
    """
    Schneller Check ob URL wahrscheinlich alt ist.

    Returns:
        Tuple (ist_wahrscheinlich_alt, signale)
    """
    heuristic = URLHeuristic()
    result = heuristic.analyze(url)

    is_old = result.result in [
        HeuristicResult.DEFINITIV_ALT,
        HeuristicResult.WAHRSCHEINLICH_ALT,
        HeuristicResult.BAUKASTEN
    ]

    return is_old, result.signals
