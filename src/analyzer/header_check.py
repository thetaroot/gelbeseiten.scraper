"""
HTTP Header Analyse zur Website-Alters-Erkennung.

Analysiert HTTP Response Header via HEAD Request.
"""

import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from src.client.http import HTTPClient, HTTPResponse


logger = logging.getLogger(__name__)


class HeaderResult(str, Enum):
    """Ergebnis der Header-Analyse."""
    DEFINITIV_ALT = "definitiv_alt"
    WAHRSCHEINLICH_ALT = "wahrscheinlich_alt"
    UNKLAR = "unklar"
    WAHRSCHEINLICH_MODERN = "wahrscheinlich_modern"
    FEHLER = "fehler"


@dataclass
class HeaderAnalysisResult:
    """Ergebnis der Header-Analyse."""
    result: HeaderResult
    confidence: float
    signals: List[str]
    server: Optional[str]
    powered_by: Optional[str]
    elapsed_ms: int


# Alte Server-Versionen
OLD_SERVER_PATTERNS = [
    # Apache alt
    (r"Apache/1\.", "apache_1_x", HeaderResult.DEFINITIV_ALT),
    (r"Apache/2\.0", "apache_2_0", HeaderResult.WAHRSCHEINLICH_ALT),
    (r"Apache/2\.2", "apache_2_2", HeaderResult.WAHRSCHEINLICH_ALT),

    # IIS alt
    (r"Microsoft-IIS/[1-5]\.", "iis_old", HeaderResult.DEFINITIV_ALT),
    (r"Microsoft-IIS/6\.", "iis_6", HeaderResult.DEFINITIV_ALT),
    (r"Microsoft-IIS/7\.", "iis_7", HeaderResult.WAHRSCHEINLICH_ALT),

    # nginx alt (selten, aber möglich)
    (r"nginx/0\.", "nginx_0_x", HeaderResult.DEFINITIV_ALT),
    (r"nginx/1\.[0-9]\.?[0-9]?$", "nginx_1_early", HeaderResult.WAHRSCHEINLICH_ALT),

    # Andere alte Server
    (r"lighttpd/1\.[0-3]", "lighttpd_old", HeaderResult.WAHRSCHEINLICH_ALT),
    (r"Zeus", "zeus_server", HeaderResult.DEFINITIV_ALT),
    (r"Netscape", "netscape_server", HeaderResult.DEFINITIV_ALT),
    (r"Oracle-HTTP-Server", "oracle_http", HeaderResult.WAHRSCHEINLICH_ALT),
]

# Alte X-Powered-By Versionen
OLD_POWERED_BY_PATTERNS = [
    # PHP alt
    (r"PHP/[1-4]\.", "php_1_4", HeaderResult.DEFINITIV_ALT),
    (r"PHP/5\.[0-3]", "php_5_early", HeaderResult.DEFINITIV_ALT),
    (r"PHP/5\.[4-6]", "php_5_late", HeaderResult.WAHRSCHEINLICH_ALT),

    # ASP.NET alt
    (r"ASP\.NET/[1-2]\.", "asp_net_old", HeaderResult.WAHRSCHEINLICH_ALT),
    (r"ASP\.NET/3\.", "asp_net_3", HeaderResult.WAHRSCHEINLICH_ALT),

    # Perl/CGI (fast immer alt)
    (r"Perl", "perl_cgi", HeaderResult.WAHRSCHEINLICH_ALT),
    (r"mod_perl", "mod_perl", HeaderResult.WAHRSCHEINLICH_ALT),

    # ColdFusion
    (r"ColdFusion", "coldfusion", HeaderResult.WAHRSCHEINLICH_ALT),
]

# Moderne Server/Framework-Signale
MODERN_PATTERNS = [
    (r"nginx/1\.(1[89]|2[0-9])", "nginx_modern"),
    (r"Apache/2\.4", "apache_2_4"),
    (r"cloudflare", "cloudflare"),
    (r"Vercel", "vercel"),
    (r"Netlify", "netlify"),
    (r"PHP/[78]\.", "php_modern"),
    (r"Express", "expressjs"),
    (r"Next\.js", "nextjs"),
    (r"gunicorn", "gunicorn"),
    (r"uvicorn", "uvicorn"),
]

# Sicherheits-Header (moderne Websites haben diese)
SECURITY_HEADERS = [
    "strict-transport-security",
    "content-security-policy",
    "x-content-type-options",
    "x-frame-options",
    "x-xss-protection",
    "referrer-policy",
    "permissions-policy",
]


class HeaderChecker:
    """
    Analysiert HTTP Header zur Alters-Erkennung.

    Prüft:
    - Server-Version
    - X-Powered-By
    - Sicherheits-Header
    - Andere Indikatoren
    """

    def __init__(self, http_client: HTTPClient):
        """
        Initialisiert den Header-Checker.

        Args:
            http_client: Konfigurierter HTTP Client.
        """
        self._client = http_client
        self._checked_count = 0

    def check(self, url: str) -> HeaderAnalysisResult:
        """
        Führt HEAD Request durch und analysiert Header.

        Args:
            url: Die zu prüfende URL.

        Returns:
            HeaderAnalysisResult mit Ergebnis.
        """
        self._checked_count += 1

        # HEAD Request
        response = self._client.head(url, timeout=10.0)

        if not response.success:
            return HeaderAnalysisResult(
                result=HeaderResult.FEHLER,
                confidence=0.0,
                signals=[f"request_failed_{response.status_code}"],
                server=None,
                powered_by=None,
                elapsed_ms=response.elapsed_ms
            )

        return self._analyze_headers(response)

    def _analyze_headers(self, response: HTTPResponse) -> HeaderAnalysisResult:
        """Analysiert die Response-Header."""
        headers = {k.lower(): v for k, v in response.headers.items()}
        signals = []

        # Server Header
        server = headers.get("server", "")
        server_result = self._check_server(server)
        if server_result:
            result_type, signal = server_result
            signals.append(signal)

        # X-Powered-By Header
        powered_by = headers.get("x-powered-by", "")
        powered_result = self._check_powered_by(powered_by)
        if powered_result:
            result_type, signal = powered_result
            signals.append(signal)

        # Sicherheits-Header Check
        security_score = self._check_security_headers(headers)
        if security_score == 0:
            signals.append("keine_security_header")
        elif security_score >= 4:
            signals.append("gute_security_header")

        # Moderne Signale prüfen
        modern_signals = self._check_modern_signals(headers)
        if modern_signals:
            signals.extend(modern_signals)

        # Zusätzliche Header-Checks
        extra_signals = self._check_extra_headers(headers)
        signals.extend(extra_signals)

        # Gesamtergebnis berechnen
        result, confidence = self._calculate_result(signals, security_score)

        return HeaderAnalysisResult(
            result=result,
            confidence=confidence,
            signals=signals,
            server=server or None,
            powered_by=powered_by or None,
            elapsed_ms=response.elapsed_ms
        )

    def _check_server(self, server: str) -> Optional[Tuple[HeaderResult, str]]:
        """Prüft Server-Header auf alte Versionen."""
        if not server:
            return None

        for pattern, signal, result in OLD_SERVER_PATTERNS:
            if re.search(pattern, server, re.IGNORECASE):
                return result, f"server_{signal}"

        return None

    def _check_powered_by(self, powered_by: str) -> Optional[Tuple[HeaderResult, str]]:
        """Prüft X-Powered-By Header auf alte Versionen."""
        if not powered_by:
            return None

        for pattern, signal, result in OLD_POWERED_BY_PATTERNS:
            if re.search(pattern, powered_by, re.IGNORECASE):
                return result, f"powered_by_{signal}"

        return None

    def _check_security_headers(self, headers: Dict[str, str]) -> int:
        """
        Zählt vorhandene Sicherheits-Header.

        Returns:
            Anzahl gefundener Sicherheits-Header (0-7)
        """
        count = 0
        for header in SECURITY_HEADERS:
            if header in headers:
                count += 1
        return count

    def _check_modern_signals(self, headers: Dict[str, str]) -> List[str]:
        """Prüft auf moderne Server/Framework-Signale."""
        signals = []

        # Server Header
        server = headers.get("server", "")
        for pattern, signal in MODERN_PATTERNS:
            if re.search(pattern, server, re.IGNORECASE):
                signals.append(f"modern_{signal}")

        # X-Powered-By
        powered_by = headers.get("x-powered-by", "")
        for pattern, signal in MODERN_PATTERNS:
            if re.search(pattern, powered_by, re.IGNORECASE):
                signals.append(f"modern_{signal}")

        # Bekannte CDN/Proxy-Header
        if "cf-ray" in headers or "cf-cache-status" in headers:
            signals.append("modern_cloudflare")
        if "x-vercel-id" in headers:
            signals.append("modern_vercel")
        if "x-nf-request-id" in headers:
            signals.append("modern_netlify")
        if "x-amz-" in " ".join(headers.keys()):
            signals.append("modern_aws")

        return signals

    def _check_extra_headers(self, headers: Dict[str, str]) -> List[str]:
        """Prüft auf zusätzliche relevante Header."""
        signals = []

        # Kein Cache-Control = oft älter
        if "cache-control" not in headers:
            signals.append("kein_cache_control")

        # Pragma: no-cache = oft älterer Code
        if headers.get("pragma") == "no-cache":
            signals.append("pragma_no_cache")

        # Alte Content-Type ohne charset
        content_type = headers.get("content-type", "")
        if "text/html" in content_type and "charset" not in content_type:
            signals.append("html_ohne_charset")

        # X-AspNet-Version (oft exponiert bei alten Sites)
        if "x-aspnet-version" in headers:
            version = headers["x-aspnet-version"]
            if re.match(r"[1-3]\.", version):
                signals.append("aspnet_version_alt")

        # X-Powered-By-Plesk
        if "x-powered-by-plesk" in headers:
            signals.append("plesk_header")

        return signals

    def _calculate_result(
        self,
        signals: List[str],
        security_score: int
    ) -> Tuple[HeaderResult, float]:
        """Berechnet das Gesamtergebnis basierend auf Signalen."""

        # Zähle Signal-Typen
        old_signals = [s for s in signals if any(
            x in s for x in ["alt", "old", "php_1", "php_5", "apache_2_0", "apache_2_2", "iis_"]
        )]
        modern_signals = [s for s in signals if "modern_" in s]

        # Definitiv alt
        definitiv_alt_signals = [
            s for s in signals if any(
                x in s for x in ["php_1_4", "php_5_early", "apache_1", "iis_old", "iis_6"]
            )
        ]

        if definitiv_alt_signals:
            return HeaderResult.DEFINITIV_ALT, 0.9

        # Wahrscheinlich alt
        if len(old_signals) >= 2 or (len(old_signals) >= 1 and security_score == 0):
            return HeaderResult.WAHRSCHEINLICH_ALT, 0.7

        if len(old_signals) == 1:
            return HeaderResult.WAHRSCHEINLICH_ALT, 0.5

        # Wahrscheinlich modern
        if modern_signals and security_score >= 3:
            return HeaderResult.WAHRSCHEINLICH_MODERN, 0.8

        if modern_signals:
            return HeaderResult.WAHRSCHEINLICH_MODERN, 0.6

        if security_score >= 4:
            return HeaderResult.WAHRSCHEINLICH_MODERN, 0.5

        # Unklar
        return HeaderResult.UNKLAR, 0.3

    @property
    def checked_count(self) -> int:
        """Anzahl durchgeführter Checks."""
        return self._checked_count
