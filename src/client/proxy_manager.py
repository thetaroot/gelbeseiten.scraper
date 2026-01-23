"""
Proxy-Manager für anonymisiertes Scraping.

Unterstützt SOCKS5, HTTP und HTTPS Proxies.
Optional - System funktioniert auch ohne Proxies.
"""

import logging
import random
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from enum import Enum


logger = logging.getLogger(__name__)


class ProxyType(str, Enum):
    """Unterstützte Proxy-Typen."""
    HTTP = "http"
    HTTPS = "https"
    SOCKS5 = "socks5"


@dataclass
class ProxyConfig:
    """Konfiguration für einen einzelnen Proxy."""
    host: str
    port: int
    proxy_type: ProxyType = ProxyType.HTTP
    username: Optional[str] = None
    password: Optional[str] = None

    # Statistiken
    success_count: int = 0
    failure_count: int = 0
    is_blocked: bool = False

    @property
    def url(self) -> str:
        """Erstellt Proxy-URL."""
        auth = ""
        if self.username and self.password:
            auth = f"{self.username}:{self.password}@"
        return f"{self.proxy_type.value}://{auth}{self.host}:{self.port}"

    @property
    def playwright_config(self) -> Dict:
        """Konfiguration für Playwright."""
        config = {
            "server": f"{self.proxy_type.value}://{self.host}:{self.port}"
        }
        if self.username:
            config["username"] = self.username
        if self.password:
            config["password"] = self.password
        return config

    @property
    def requests_config(self) -> Dict[str, str]:
        """Konfiguration für requests library."""
        url = self.url
        if self.proxy_type == ProxyType.SOCKS5:
            return {
                "http": url,
                "https": url
            }
        return {
            "http": url.replace("https://", "http://") if self.proxy_type == ProxyType.HTTPS else url,
            "https": url
        }

    @property
    def failure_rate(self) -> float:
        """Berechnet Fehlerrate."""
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.0
        return self.failure_count / total


class ProxyManager:
    """
    Verwaltet Proxy-Rotation für Scraping.

    Features:
    - Lädt Proxies aus Datei
    - Round-Robin oder gewichtete Rotation
    - Markiert fehlerhafte Proxies
    - Thread-safe
    """

    def __init__(
        self,
        enabled: bool = False,
        rotate_every_n: int = 10,
        max_failures: int = 5
    ):
        """
        Initialisiert den ProxyManager.

        Args:
            enabled: Ob Proxy-Rotation aktiv ist.
            rotate_every_n: Nach wie vielen Requests rotieren.
            max_failures: Max. Fehler bevor Proxy deaktiviert wird.
        """
        self._enabled = enabled
        self._rotate_every_n = rotate_every_n
        self._max_failures = max_failures

        self._proxies: List[ProxyConfig] = []
        self._current_index = 0
        self._request_count = 0
        self._lock = threading.Lock()

        logger.info(f"ProxyManager initialisiert (enabled={enabled})")

    @property
    def enabled(self) -> bool:
        """Ob Proxy-Rotation aktiv ist."""
        return self._enabled and len(self._proxies) > 0

    def load_proxies(self, file_path: str) -> int:
        """
        Lädt Proxies aus einer Datei.

        Format pro Zeile:
        - host:port
        - type://host:port
        - type://user:pass@host:port

        Args:
            file_path: Pfad zur Proxy-Liste.

        Returns:
            Anzahl geladener Proxies.
        """
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"Proxy-Datei nicht gefunden: {file_path}")
            return 0

        count = 0
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                proxy = self._parse_proxy_line(line)
                if proxy:
                    self._proxies.append(proxy)
                    count += 1

        if count > 0:
            self._enabled = True
            logger.info(f"Geladen: {count} Proxies aus {file_path}")
        else:
            logger.warning(f"Keine gültigen Proxies in {file_path}")

        return count

    def _parse_proxy_line(self, line: str) -> Optional[ProxyConfig]:
        """Parst eine Proxy-Zeile."""
        try:
            # Format: type://user:pass@host:port oder host:port
            proxy_type = ProxyType.HTTP
            username = None
            password = None

            # Extrahiere Typ
            if "://" in line:
                type_str, rest = line.split("://", 1)
                type_str = type_str.lower()
                if type_str == "socks5":
                    proxy_type = ProxyType.SOCKS5
                elif type_str == "https":
                    proxy_type = ProxyType.HTTPS
                line = rest

            # Extrahiere Auth
            if "@" in line:
                auth, line = line.rsplit("@", 1)
                if ":" in auth:
                    username, password = auth.split(":", 1)

            # Extrahiere Host:Port
            if ":" not in line:
                return None

            host, port_str = line.rsplit(":", 1)
            port = int(port_str)

            return ProxyConfig(
                host=host,
                port=port,
                proxy_type=proxy_type,
                username=username,
                password=password
            )

        except Exception as e:
            logger.warning(f"Konnte Proxy nicht parsen: {line} - {e}")
            return None

    def add_proxy(self, proxy: ProxyConfig) -> None:
        """Fügt einen Proxy manuell hinzu."""
        with self._lock:
            self._proxies.append(proxy)
            self._enabled = True

    def get_next_proxy(self) -> Optional[ProxyConfig]:
        """
        Gibt den nächsten Proxy zurück.

        Returns:
            ProxyConfig oder None wenn keine Proxies verfügbar.
        """
        if not self.enabled:
            return None

        with self._lock:
            self._request_count += 1

            # Rotieren wenn nötig
            if self._request_count >= self._rotate_every_n:
                self._request_count = 0
                self._current_index = (self._current_index + 1) % len(self._proxies)

            # Finde nächsten nicht-blockierten Proxy
            attempts = 0
            while attempts < len(self._proxies):
                proxy = self._proxies[self._current_index]
                if not proxy.is_blocked:
                    return proxy

                self._current_index = (self._current_index + 1) % len(self._proxies)
                attempts += 1

            # Alle blockiert
            logger.warning("Alle Proxies sind blockiert!")
            return None

    def get_random_proxy(self) -> Optional[ProxyConfig]:
        """Gibt einen zufälligen nicht-blockierten Proxy zurück."""
        if not self.enabled:
            return None

        with self._lock:
            available = [p for p in self._proxies if not p.is_blocked]
            if not available:
                return None
            return random.choice(available)

    def report_success(self, proxy: ProxyConfig) -> None:
        """Meldet erfolgreichen Request."""
        with self._lock:
            proxy.success_count += 1

    def report_failure(self, proxy: ProxyConfig, block: bool = False) -> None:
        """
        Meldet fehlgeschlagenen Request.

        Args:
            proxy: Der fehlgeschlagene Proxy.
            block: Ob Proxy sofort blockiert werden soll.
        """
        with self._lock:
            proxy.failure_count += 1

            if block or proxy.failure_count >= self._max_failures:
                proxy.is_blocked = True
                logger.warning(f"Proxy blockiert: {proxy.host}:{proxy.port}")

    def reset_blocked(self) -> int:
        """
        Setzt alle blockierten Proxies zurück.

        Returns:
            Anzahl zurückgesetzter Proxies.
        """
        count = 0
        with self._lock:
            for proxy in self._proxies:
                if proxy.is_blocked:
                    proxy.is_blocked = False
                    proxy.failure_count = 0
                    count += 1
        return count

    def get_stats(self) -> Dict:
        """Gibt Statistiken zurück."""
        with self._lock:
            total = len(self._proxies)
            blocked = sum(1 for p in self._proxies if p.is_blocked)
            total_success = sum(p.success_count for p in self._proxies)
            total_failure = sum(p.failure_count for p in self._proxies)

            return {
                "total_proxies": total,
                "active_proxies": total - blocked,
                "blocked_proxies": blocked,
                "total_requests": total_success + total_failure,
                "success_count": total_success,
                "failure_count": total_failure,
                "rotation_enabled": self._enabled
            }

    def __len__(self) -> int:
        """Anzahl der Proxies."""
        return len(self._proxies)

    def __bool__(self) -> bool:
        """True wenn Proxies verfügbar."""
        return self.enabled
