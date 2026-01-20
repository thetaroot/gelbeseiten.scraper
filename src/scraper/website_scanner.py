"""
Website Scanner - Stage 2 der Pipeline.

Orchestriert die Website-Analyse zur Alters-Erkennung.
Kombiniert URL-Heuristik, Header-Check und HTML-Scan.
"""

import logging
import time
from typing import Optional, List
from dataclasses import dataclass
from enum import Enum

from src.client.http import HTTPClient
from src.analyzer.url_heuristic import URLHeuristic, HeuristicResult, URLAnalysisResult
from src.analyzer.header_check import HeaderChecker, HeaderResult, HeaderAnalysisResult
from src.analyzer.html_scanner import HTMLScanner, HTMLResult, HTMLAnalysisResult
from src.models.lead import WebsiteAnalysis, WebsiteStatus
from config.settings import Settings, WebsiteCheckDepth


logger = logging.getLogger(__name__)


class ScanResult(str, Enum):
    """Endgültiges Scan-Ergebnis."""
    ALT = "alt"
    MODERN = "modern"
    BAUKASTEN = "baukasten"
    UNKLAR = "unklar"
    FEHLER = "fehler"


@dataclass
class WebsiteScanResult:
    """Vollständiges Ergebnis des Website-Scans."""
    result: ScanResult
    website_status: WebsiteStatus
    confidence: float
    signals: List[str]
    check_methods: List[str]
    total_elapsed_ms: int

    # Detail-Ergebnisse
    url_result: Optional[URLAnalysisResult] = None
    header_result: Optional[HeaderAnalysisResult] = None
    html_result: Optional[HTMLAnalysisResult] = None


class WebsiteScanner:
    """
    Orchestriert die Website-Analyse.

    Kombiniert drei Analyse-Ebenen:
    1. URL-Heuristik (instant, 100% sicher)
    2. Header-Check (HEAD Request, ~0.5s)
    3. HTML-Scan (GET Request, ~1-2s)

    Die Tiefe wird über WebsiteCheckDepth gesteuert:
    - FAST: Nur URL-Heuristik
    - NORMAL: URL + Header
    - THOROUGH: URL + Header + HTML
    """

    def __init__(
        self,
        http_client: HTTPClient,
        settings: Optional[Settings] = None
    ):
        """
        Initialisiert den Website-Scanner.

        Args:
            http_client: Konfigurierter HTTP Client.
            settings: Scanner-Einstellungen.
        """
        self._client = http_client
        self._settings = settings or Settings()

        # Analyzer initialisieren
        self._url_heuristic = URLHeuristic()
        self._header_checker = HeaderChecker(http_client)
        self._html_scanner = HTMLScanner(http_client)

        # Statistiken
        self._scanned_count = 0
        self._results_by_type = {r: 0 for r in ScanResult}

    def scan(
        self,
        url: str,
        depth: Optional[WebsiteCheckDepth] = None
    ) -> WebsiteScanResult:
        """
        Führt Website-Scan durch.

        Args:
            url: Die zu analysierende URL.
            depth: Check-Tiefe (überschreibt Settings).

        Returns:
            WebsiteScanResult mit Analyse-Ergebnis.
        """
        if depth is None:
            depth = self._settings.website_check_depth

        self._scanned_count += 1
        start_time = time.time()

        all_signals = []
        check_methods = []

        url_result = None
        header_result = None
        html_result = None

        # === Stage 1: URL-Heuristik (immer) ===
        logger.debug(f"URL-Heuristik für {url}")
        url_result = self._url_heuristic.analyze(url)
        all_signals.extend([f"url:{s}" for s in url_result.signals])
        check_methods.append("url_heuristic")

        # Bei definitiv altem Ergebnis: Sofort zurückgeben
        if url_result.result == HeuristicResult.DEFINITIV_ALT:
            logger.debug(f"URL-Heuristik: definitiv alt - {url_result.signals}")
            elapsed_ms = int((time.time() - start_time) * 1000)
            result = self._build_result(
                ScanResult.ALT,
                WebsiteStatus.ALT,
                url_result.confidence,
                all_signals,
                check_methods,
                elapsed_ms,
                url_result=url_result
            )
            self._results_by_type[ScanResult.ALT] += 1
            return result

        # Baukasten erkannt
        if url_result.result == HeuristicResult.BAUKASTEN:
            logger.debug(f"URL-Heuristik: Baukasten erkannt - {url_result.signals}")
            elapsed_ms = int((time.time() - start_time) * 1000)
            result = self._build_result(
                ScanResult.BAUKASTEN,
                WebsiteStatus.ALT,  # Baukasten = potenziell alt/basic
                url_result.confidence,
                all_signals,
                check_methods,
                elapsed_ms,
                url_result=url_result
            )
            self._results_by_type[ScanResult.BAUKASTEN] += 1
            return result

        # Modern erkannt
        if url_result.result == HeuristicResult.WAHRSCHEINLICH_MODERN:
            # Bei FAST-Modus hier aufhören
            if depth == WebsiteCheckDepth.FAST:
                elapsed_ms = int((time.time() - start_time) * 1000)
                result = self._build_result(
                    ScanResult.MODERN,
                    WebsiteStatus.MODERN,
                    url_result.confidence,
                    all_signals,
                    check_methods,
                    elapsed_ms,
                    url_result=url_result
                )
                self._results_by_type[ScanResult.MODERN] += 1
                return result

        # FAST-Modus: Hier beenden wenn unklar
        if depth == WebsiteCheckDepth.FAST:
            elapsed_ms = int((time.time() - start_time) * 1000)
            # Wahrscheinlich alt aus URL?
            if url_result.result == HeuristicResult.WAHRSCHEINLICH_ALT:
                result = self._build_result(
                    ScanResult.ALT,
                    WebsiteStatus.ALT,
                    url_result.confidence,
                    all_signals,
                    check_methods,
                    elapsed_ms,
                    url_result=url_result
                )
                self._results_by_type[ScanResult.ALT] += 1
                return result

            result = self._build_result(
                ScanResult.UNKLAR,
                WebsiteStatus.UNBEKANNT,
                0.3,
                all_signals,
                check_methods,
                elapsed_ms,
                url_result=url_result
            )
            self._results_by_type[ScanResult.UNKLAR] += 1
            return result

        # === Stage 2: Header-Check (NORMAL und THOROUGH) ===
        logger.debug(f"Header-Check für {url}")
        header_result = self._header_checker.check(url)
        all_signals.extend([f"header:{s}" for s in header_result.signals])
        check_methods.append("header_check")

        if header_result.result == HeaderResult.FEHLER:
            # Bei Fehler: Ergebnis basierend auf URL-Heuristik
            elapsed_ms = int((time.time() - start_time) * 1000)
            if url_result.result == HeuristicResult.WAHRSCHEINLICH_ALT:
                result = self._build_result(
                    ScanResult.ALT,
                    WebsiteStatus.ALT,
                    0.5,
                    all_signals,
                    check_methods,
                    elapsed_ms,
                    url_result=url_result,
                    header_result=header_result
                )
            else:
                result = self._build_result(
                    ScanResult.UNKLAR,
                    WebsiteStatus.UNBEKANNT,
                    0.2,
                    all_signals,
                    check_methods,
                    elapsed_ms,
                    url_result=url_result,
                    header_result=header_result
                )
            self._results_by_type[result.result] += 1
            return result

        # Definitiv alt aus Header
        if header_result.result == HeaderResult.DEFINITIV_ALT:
            elapsed_ms = int((time.time() - start_time) * 1000)
            result = self._build_result(
                ScanResult.ALT,
                WebsiteStatus.ALT,
                header_result.confidence,
                all_signals,
                check_methods,
                elapsed_ms,
                url_result=url_result,
                header_result=header_result
            )
            self._results_by_type[ScanResult.ALT] += 1
            return result

        # Kombiniere URL + Header für NORMAL-Entscheidung
        combined_old_signals = (
            url_result.result in [HeuristicResult.WAHRSCHEINLICH_ALT, HeuristicResult.DEFINITIV_ALT] or
            header_result.result in [HeaderResult.WAHRSCHEINLICH_ALT, HeaderResult.DEFINITIV_ALT]
        )

        combined_modern_signals = (
            url_result.result == HeuristicResult.WAHRSCHEINLICH_MODERN or
            header_result.result == HeaderResult.WAHRSCHEINLICH_MODERN
        )

        # NORMAL-Modus: Entscheidung hier
        if depth == WebsiteCheckDepth.NORMAL:
            elapsed_ms = int((time.time() - start_time) * 1000)

            if combined_old_signals and not combined_modern_signals:
                confidence = max(url_result.confidence, header_result.confidence)
                result = self._build_result(
                    ScanResult.ALT,
                    WebsiteStatus.ALT,
                    confidence,
                    all_signals,
                    check_methods,
                    elapsed_ms,
                    url_result=url_result,
                    header_result=header_result
                )
                self._results_by_type[ScanResult.ALT] += 1
                return result

            if combined_modern_signals and not combined_old_signals:
                confidence = max(url_result.confidence, header_result.confidence)
                result = self._build_result(
                    ScanResult.MODERN,
                    WebsiteStatus.MODERN,
                    confidence,
                    all_signals,
                    check_methods,
                    elapsed_ms,
                    url_result=url_result,
                    header_result=header_result
                )
                self._results_by_type[ScanResult.MODERN] += 1
                return result

            # Unklar - aber im NORMAL-Modus machen wir HTML-Scan bei Unklarheit
            # Nur wenn wir wirklich unklar sind
            if header_result.result == HeaderResult.UNKLAR and url_result.result == HeuristicResult.UNKLAR:
                # Mache HTML-Scan auch im NORMAL-Modus bei völliger Unklarheit
                pass  # Falle durch zu THOROUGH-Logik
            else:
                result = self._build_result(
                    ScanResult.UNKLAR,
                    WebsiteStatus.UNBEKANNT,
                    0.4,
                    all_signals,
                    check_methods,
                    elapsed_ms,
                    url_result=url_result,
                    header_result=header_result
                )
                self._results_by_type[ScanResult.UNKLAR] += 1
                return result

        # === Stage 3: HTML-Scan (THOROUGH oder NORMAL bei Unklarheit) ===
        logger.debug(f"HTML-Scan für {url}")
        html_result = self._html_scanner.scan(url)
        all_signals.extend([f"html:{s}" for s in html_result.signals])
        check_methods.append("html_scan")

        elapsed_ms = int((time.time() - start_time) * 1000)

        # Finale Entscheidung
        return self._make_final_decision(
            url_result,
            header_result,
            html_result,
            all_signals,
            check_methods,
            elapsed_ms
        )

    def _make_final_decision(
        self,
        url_result: URLAnalysisResult,
        header_result: HeaderAnalysisResult,
        html_result: HTMLAnalysisResult,
        all_signals: List[str],
        check_methods: List[str],
        elapsed_ms: int
    ) -> WebsiteScanResult:
        """Trifft finale Entscheidung basierend auf allen Analysen."""

        # Gewichte die Ergebnisse
        old_score = 0
        modern_score = 0

        # URL-Heuristik
        if url_result.result == HeuristicResult.DEFINITIV_ALT:
            old_score += 3
        elif url_result.result == HeuristicResult.WAHRSCHEINLICH_ALT:
            old_score += 2
        elif url_result.result == HeuristicResult.WAHRSCHEINLICH_MODERN:
            modern_score += 2
        elif url_result.result == HeuristicResult.BAUKASTEN:
            old_score += 1.5  # Baukasten = leicht alt

        # Header-Check
        if header_result.result == HeaderResult.DEFINITIV_ALT:
            old_score += 3
        elif header_result.result == HeaderResult.WAHRSCHEINLICH_ALT:
            old_score += 2
        elif header_result.result == HeaderResult.WAHRSCHEINLICH_MODERN:
            modern_score += 2

        # HTML-Scan (stärkste Gewichtung)
        if html_result.result == HTMLResult.DEFINITIV_ALT:
            old_score += 4
        elif html_result.result == HTMLResult.WAHRSCHEINLICH_ALT:
            old_score += 2.5
        elif html_result.result == HTMLResult.WAHRSCHEINLICH_MODERN:
            modern_score += 3

        # Entscheidung
        if old_score >= 4:
            confidence = min(0.95, 0.5 + old_score * 0.1)
            result = self._build_result(
                ScanResult.ALT,
                WebsiteStatus.ALT,
                confidence,
                all_signals,
                check_methods,
                elapsed_ms,
                url_result=url_result,
                header_result=header_result,
                html_result=html_result
            )
            self._results_by_type[ScanResult.ALT] += 1
            return result

        if modern_score >= 4:
            confidence = min(0.95, 0.5 + modern_score * 0.1)
            result = self._build_result(
                ScanResult.MODERN,
                WebsiteStatus.MODERN,
                confidence,
                all_signals,
                check_methods,
                elapsed_ms,
                url_result=url_result,
                header_result=header_result,
                html_result=html_result
            )
            self._results_by_type[ScanResult.MODERN] += 1
            return result

        if old_score > modern_score:
            result = self._build_result(
                ScanResult.ALT,
                WebsiteStatus.ALT,
                0.6,
                all_signals,
                check_methods,
                elapsed_ms,
                url_result=url_result,
                header_result=header_result,
                html_result=html_result
            )
            self._results_by_type[ScanResult.ALT] += 1
            return result

        if modern_score > old_score:
            result = self._build_result(
                ScanResult.MODERN,
                WebsiteStatus.MODERN,
                0.6,
                all_signals,
                check_methods,
                elapsed_ms,
                url_result=url_result,
                header_result=header_result,
                html_result=html_result
            )
            self._results_by_type[ScanResult.MODERN] += 1
            return result

        # Gleichstand = Unklar
        result = self._build_result(
            ScanResult.UNKLAR,
            WebsiteStatus.UNBEKANNT,
            0.3,
            all_signals,
            check_methods,
            elapsed_ms,
            url_result=url_result,
            header_result=header_result,
            html_result=html_result
        )
        self._results_by_type[ScanResult.UNKLAR] += 1
        return result

    def _build_result(
        self,
        result: ScanResult,
        status: WebsiteStatus,
        confidence: float,
        signals: List[str],
        check_methods: List[str],
        elapsed_ms: int,
        url_result: Optional[URLAnalysisResult] = None,
        header_result: Optional[HeaderAnalysisResult] = None,
        html_result: Optional[HTMLAnalysisResult] = None
    ) -> WebsiteScanResult:
        """Baut das Ergebnis-Objekt."""
        return WebsiteScanResult(
            result=result,
            website_status=status,
            confidence=confidence,
            signals=signals,
            check_methods=check_methods,
            total_elapsed_ms=elapsed_ms,
            url_result=url_result,
            header_result=header_result,
            html_result=html_result
        )

    def update_lead_analysis(
        self,
        lead_analysis: WebsiteAnalysis,
        scan_result: WebsiteScanResult
    ) -> WebsiteAnalysis:
        """
        Aktualisiert eine Lead's WebsiteAnalysis mit Scan-Ergebnis.

        Args:
            lead_analysis: Das zu aktualisierende WebsiteAnalysis Objekt.
            scan_result: Das Scan-Ergebnis.

        Returns:
            Aktualisiertes WebsiteAnalysis Objekt.
        """
        lead_analysis.status = scan_result.website_status
        lead_analysis.signale = scan_result.signals
        lead_analysis.check_methode = ",".join(scan_result.check_methods)
        lead_analysis.check_dauer_ms = scan_result.total_elapsed_ms

        return lead_analysis

    @property
    def stats(self) -> dict:
        """Gibt Scanner-Statistiken zurück."""
        return {
            "scanned_count": self._scanned_count,
            "results_by_type": dict(self._results_by_type),
            "url_heuristic_count": self._url_heuristic.analyzed_count,
            "header_check_count": self._header_checker.checked_count,
            "html_scan_count": self._html_scanner.scanned_count
        }
