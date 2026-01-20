"""
HTTP Client mit Anti-Bot-Features.

Implementiert Session-Management, User-Agent Rotation,
Retry-Logik und Rate Limiting.
"""

import logging
from typing import Optional, Dict, Any
from urllib.parse import urlparse
from dataclasses import dataclass

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config.settings import Settings, ScraperConfig
from src.client.rate_limiter import RateLimiter
from src.utils.user_agents import UserAgentRotator, get_browser_headers


logger = logging.getLogger(__name__)


@dataclass
class HTTPResponse:
    """Wrapper für HTTP Response mit Zusatzinformationen."""
    success: bool
    status_code: int
    content: str
    url: str
    final_url: str  # Nach Redirects
    headers: Dict[str, str]
    elapsed_ms: int
    error: Optional[str] = None

    @property
    def was_redirected(self) -> bool:
        """Prüft ob ein Redirect stattfand."""
        return self.url != self.final_url


class HTTPClient:
    """
    Robuster HTTP Client für Web Scraping.

    Features:
    - Persistente Session mit Cookie-Management
    - User-Agent Rotation
    - Vollständige Browser-Header
    - Automatische Retries mit Backoff
    - Rate Limiting Integration
    - Timeout-Handling
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        rate_limiter: Optional[RateLimiter] = None
    ):
        """
        Initialisiert den HTTP Client.

        Args:
            settings: Konfiguration. Falls None, werden Defaults verwendet.
            rate_limiter: Rate Limiter Instanz. Falls None, wird einer erstellt.
        """
        self._settings = settings or Settings()
        self._config = self._settings.scraper
        self._rate_limiter = rate_limiter or RateLimiter(self._settings.rate_limit)
        self._ua_rotator = UserAgentRotator()

        self._session = self._create_session()
        self._request_count = 0
        self._current_ua: Optional[str] = None

        # Initiale Header setzen
        self._rotate_user_agent()

    def _create_session(self) -> requests.Session:
        """Erstellt und konfiguriert eine neue Session."""
        session = requests.Session()

        # Retry-Strategie (für Netzwerkfehler, nicht für Rate Limiting)
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["HEAD", "GET"],
            raise_on_status=False
        )

        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=10
        )

        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def _rotate_user_agent(self) -> None:
        """Rotiert den User-Agent und aktualisiert Header."""
        self._current_ua = self._ua_rotator.get_random()
        headers = get_browser_headers(self._current_ua)
        self._session.headers.update(headers)
        logger.debug(f"User-Agent rotiert: {self._current_ua[:50]}...")

    def _should_rotate_ua(self) -> bool:
        """Prüft ob User-Agent rotiert werden soll."""
        return self._request_count % self._config.rotate_ua_every_n_requests == 0

    def _extract_domain(self, url: str) -> str:
        """Extrahiert die Domain aus einer URL."""
        parsed = urlparse(url)
        return parsed.netloc

    def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        skip_rate_limit: bool = False
    ) -> HTTPResponse:
        """
        Führt einen GET Request aus.

        Args:
            url: Die Ziel-URL.
            params: Query-Parameter.
            headers: Zusätzliche Header (überschreiben Session-Header).
            timeout: Timeout in Sekunden. Falls None, wird Config verwendet.
            skip_rate_limit: Wenn True, wird Rate Limiting übersprungen.

        Returns:
            HTTPResponse mit Ergebnis.
        """
        domain = self._extract_domain(url)

        # Rate Limiting
        if not skip_rate_limit:
            self._rate_limiter.wait(domain)

        # UA Rotation prüfen
        if self._should_rotate_ua():
            self._rotate_user_agent()

        self._request_count += 1

        # Timeout
        if timeout is None:
            timeout = (self._config.connect_timeout, self._config.request_timeout)
        else:
            timeout = (self._config.connect_timeout, timeout)

        # Request Header
        request_headers = dict(self._session.headers)
        if headers:
            request_headers.update(headers)

        try:
            logger.debug(f"GET {url}")

            response = self._session.get(
                url,
                params=params,
                headers=request_headers,
                timeout=timeout,
                allow_redirects=True
            )

            elapsed_ms = int(response.elapsed.total_seconds() * 1000)

            # Erfolg melden
            if response.ok:
                self._rate_limiter.report_success(domain)

                return HTTPResponse(
                    success=True,
                    status_code=response.status_code,
                    content=response.text,
                    url=url,
                    final_url=response.url,
                    headers=dict(response.headers),
                    elapsed_ms=elapsed_ms
                )

            # Fehler melden
            self._rate_limiter.report_error(domain, response.status_code)

            return HTTPResponse(
                success=False,
                status_code=response.status_code,
                content=response.text,
                url=url,
                final_url=response.url,
                headers=dict(response.headers),
                elapsed_ms=elapsed_ms,
                error=f"HTTP {response.status_code}"
            )

        except requests.exceptions.Timeout as e:
            logger.warning(f"Timeout für {url}: {e}")
            return HTTPResponse(
                success=False,
                status_code=0,
                content="",
                url=url,
                final_url=url,
                headers={},
                elapsed_ms=int(timeout[1] * 1000) if isinstance(timeout, tuple) else int(timeout * 1000),
                error=f"Timeout: {e}"
            )

        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Verbindungsfehler für {url}: {e}")
            return HTTPResponse(
                success=False,
                status_code=0,
                content="",
                url=url,
                final_url=url,
                headers={},
                elapsed_ms=0,
                error=f"Verbindungsfehler: {e}"
            )

        except requests.exceptions.RequestException as e:
            logger.error(f"Request-Fehler für {url}: {e}")
            return HTTPResponse(
                success=False,
                status_code=0,
                content="",
                url=url,
                final_url=url,
                headers={},
                elapsed_ms=0,
                error=f"Request-Fehler: {e}"
            )

    def head(
        self,
        url: str,
        timeout: Optional[float] = None,
        skip_rate_limit: bool = False
    ) -> HTTPResponse:
        """
        Führt einen HEAD Request aus (nur Header, kein Body).

        Args:
            url: Die Ziel-URL.
            timeout: Timeout in Sekunden.
            skip_rate_limit: Wenn True, wird Rate Limiting übersprungen.

        Returns:
            HTTPResponse (content ist leer).
        """
        domain = self._extract_domain(url)

        # Rate Limiting (mit kürzerem Delay für HEAD)
        if not skip_rate_limit:
            self._rate_limiter.wait(domain)

        self._request_count += 1

        # Kürzerer Timeout für HEAD
        if timeout is None:
            timeout = (5.0, 10.0)
        else:
            timeout = (5.0, timeout)

        try:
            logger.debug(f"HEAD {url}")

            response = self._session.head(
                url,
                timeout=timeout,
                allow_redirects=True
            )

            elapsed_ms = int(response.elapsed.total_seconds() * 1000)

            return HTTPResponse(
                success=response.ok,
                status_code=response.status_code,
                content="",
                url=url,
                final_url=response.url,
                headers=dict(response.headers),
                elapsed_ms=elapsed_ms,
                error=None if response.ok else f"HTTP {response.status_code}"
            )

        except requests.exceptions.Timeout as e:
            return HTTPResponse(
                success=False,
                status_code=0,
                content="",
                url=url,
                final_url=url,
                headers={},
                elapsed_ms=int(timeout[1] * 1000) if isinstance(timeout, tuple) else int(timeout * 1000),
                error=f"Timeout: {e}"
            )

        except requests.exceptions.RequestException as e:
            return HTTPResponse(
                success=False,
                status_code=0,
                content="",
                url=url,
                final_url=url,
                headers={},
                elapsed_ms=0,
                error=f"Request-Fehler: {e}"
            )

    def get_with_retry(
        self,
        url: str,
        max_retries: Optional[int] = None,
        **kwargs
    ) -> HTTPResponse:
        """
        Führt GET mit manueller Retry-Logik aus.

        Nützlich für Rate-Limiting-Fehler (429), die nicht
        von der Session-Retry-Strategie abgedeckt werden.

        Args:
            url: Die Ziel-URL.
            max_retries: Max. Anzahl Retries. Falls None, aus Config.
            **kwargs: Weitere Argumente für get().

        Returns:
            HTTPResponse.
        """
        if max_retries is None:
            max_retries = self._settings.rate_limit.max_retries

        domain = self._extract_domain(url)
        last_response = None

        for attempt in range(max_retries + 1):
            response = self.get(url, **kwargs)
            last_response = response

            if response.success:
                return response

            # Prüfe ob Retry sinnvoll
            if not self._rate_limiter.should_retry(response.status_code, attempt):
                break

            # Warte vor Retry
            retry_delay = self._rate_limiter.get_retry_delay(attempt)
            logger.info(
                f"Retry {attempt + 1}/{max_retries} für {url} "
                f"nach {retry_delay:.1f}s (Status: {response.status_code})"
            )
            import time
            time.sleep(retry_delay)

        return last_response

    def close(self) -> None:
        """Schließt die Session und gibt Ressourcen frei."""
        self._session.close()
        logger.debug("HTTP Client Session geschlossen")

    def __enter__(self) -> "HTTPClient":
        """Context Manager Eintritt."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context Manager Austritt."""
        self.close()

    @property
    def request_count(self) -> int:
        """Anzahl der durchgeführten Requests."""
        return self._request_count

    @property
    def current_user_agent(self) -> Optional[str]:
        """Der aktuell verwendete User-Agent."""
        return self._current_ua

    def get_stats(self) -> dict:
        """Gibt Client-Statistiken zurück."""
        return {
            "request_count": self._request_count,
            "current_user_agent": self._current_ua,
            "rate_limiter_stats": self._rate_limiter.get_stats()
        }
