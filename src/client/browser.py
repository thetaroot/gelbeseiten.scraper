"""
Browser-Client für JavaScript-Rendering.

Verwendet Playwright für moderne, schnelle Browser-Automation.
Unterstützt Stealth-Mode und Proxy-Rotation.
"""

import logging
import random
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from contextlib import contextmanager

from playwright.sync_api import (
    sync_playwright,
    Browser,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeout
)

from src.client.proxy_manager import ProxyManager, ProxyConfig
from src.utils.user_agents import UserAgentRotator


logger = logging.getLogger(__name__)


@dataclass
class BrowserResponse:
    """Antwort vom Browser."""
    success: bool
    content: str
    url: str
    final_url: str
    status_code: Optional[int] = None
    error: Optional[str] = None
    elapsed_ms: int = 0


class BrowserClient:
    """
    Playwright-basierter Browser für JavaScript-Rendering.

    Features:
    - Headless Chrome/Chromium
    - Stealth-Mode (Anti-Detection)
    - Proxy-Rotation
    - User-Agent Rotation
    - Screenshot-Support für Debugging
    """

    def __init__(
        self,
        headless: bool = True,
        proxy_manager: Optional[ProxyManager] = None,
        timeout: int = 30000,
        viewport_width: int = 1920,
        viewport_height: int = 1080
    ):
        """
        Initialisiert den BrowserClient.

        Args:
            headless: Browser ohne GUI starten.
            proxy_manager: Optional, für Proxy-Rotation.
            timeout: Default-Timeout in Millisekunden.
            viewport_width: Breite des Viewports.
            viewport_height: Höhe des Viewports.
        """
        self._headless = headless
        self._proxy_manager = proxy_manager
        self._timeout = timeout
        self._viewport = {"width": viewport_width, "height": viewport_height}

        self._ua_rotator = UserAgentRotator()
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

        self._current_proxy: Optional[ProxyConfig] = None
        self._request_count = 0

        logger.info(f"BrowserClient initialisiert (headless={headless})")

    def start(self) -> None:
        """Startet den Browser."""
        if self._browser is not None:
            return

        self._playwright = sync_playwright().start()

        # Browser-Optionen
        launch_options = {
            "headless": self._headless,
        }

        self._browser = self._playwright.chromium.launch(**launch_options)
        self._create_context()

        logger.info("Browser gestartet")

    def _create_context(self, proxy: Optional[ProxyConfig] = None) -> None:
        """Erstellt einen neuen Browser-Context."""
        if self._context:
            self._context.close()

        # Context-Optionen
        context_options: Dict[str, Any] = {
            "viewport": self._viewport,
            "user_agent": self._ua_rotator.get_random(),
            "locale": "de-DE",
            "timezone_id": "Europe/Berlin",
        }

        # Proxy hinzufügen wenn vorhanden
        if proxy:
            context_options["proxy"] = proxy.playwright_config
            self._current_proxy = proxy

        # Stealth-Optionen
        context_options["java_script_enabled"] = True
        context_options["bypass_csp"] = True

        self._context = self._browser.new_context(**context_options)
        self._page = self._context.new_page()

        # Stealth-Skripte injizieren
        self._inject_stealth_scripts()

        # Event-Handler
        self._page.on("console", lambda msg: None)  # Konsolen-Logs ignorieren

    def _inject_stealth_scripts(self) -> None:
        """Injiziert Stealth-Skripte um Detection zu vermeiden."""
        if not self._page:
            return

        # WebDriver-Property verstecken
        self._page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        # Chrome-spezifische Properties
        self._page.add_init_script("""
            window.chrome = {
                runtime: {}
            };
        """)

        # Plugins simulieren
        self._page.add_init_script("""
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
        """)

        # Languages
        self._page.add_init_script("""
            Object.defineProperty(navigator, 'languages', {
                get: () => ['de-DE', 'de', 'en-US', 'en']
            });
        """)

    def _rotate_if_needed(self) -> None:
        """Rotiert Proxy/UA wenn nötig."""
        self._request_count += 1

        # Alle 10 Requests neuen Context
        if self._request_count >= 10:
            self._request_count = 0

            new_proxy = None
            if self._proxy_manager and self._proxy_manager.enabled:
                new_proxy = self._proxy_manager.get_next_proxy()

            self._create_context(new_proxy)
            logger.debug("Browser-Context rotiert")

    def navigate(self, url: str, wait_until: str = "domcontentloaded") -> BrowserResponse:
        """
        Navigiert zu einer URL.

        Args:
            url: Die Ziel-URL.
            wait_until: Warten bis Event ("load", "domcontentloaded", "networkidle").

        Returns:
            BrowserResponse mit Inhalt oder Fehler.
        """
        if not self._page:
            self.start()

        self._rotate_if_needed()

        start_time = time.time()

        try:
            response = self._page.goto(url, wait_until=wait_until, timeout=self._timeout)

            elapsed = int((time.time() - start_time) * 1000)
            content = self._page.content()
            final_url = self._page.url

            status_code = response.status if response else None

            # Erfolg melden
            if self._current_proxy:
                self._proxy_manager.report_success(self._current_proxy)

            return BrowserResponse(
                success=True,
                content=content,
                url=url,
                final_url=final_url,
                status_code=status_code,
                elapsed_ms=elapsed
            )

        except PlaywrightTimeout as e:
            elapsed = int((time.time() - start_time) * 1000)

            if self._current_proxy:
                self._proxy_manager.report_failure(self._current_proxy)

            return BrowserResponse(
                success=False,
                content="",
                url=url,
                final_url=url,
                error=f"Timeout: {e}",
                elapsed_ms=elapsed
            )

        except Exception as e:
            elapsed = int((time.time() - start_time) * 1000)

            if self._current_proxy:
                self._proxy_manager.report_failure(self._current_proxy)

            logger.error(f"Browser-Fehler bei {url}: {e}")
            return BrowserResponse(
                success=False,
                content="",
                url=url,
                final_url=url,
                error=str(e),
                elapsed_ms=elapsed
            )

    def wait_for_selector(
        self,
        selector: str,
        timeout: Optional[int] = None,
        state: str = "visible"
    ) -> bool:
        """
        Wartet auf ein Element.

        Args:
            selector: CSS-Selector.
            timeout: Timeout in ms (default: self._timeout).
            state: "visible", "hidden", "attached", "detached".

        Returns:
            True wenn Element gefunden.
        """
        if not self._page:
            return False

        try:
            self._page.wait_for_selector(
                selector,
                timeout=timeout or self._timeout,
                state=state
            )
            return True
        except PlaywrightTimeout:
            return False
        except Exception as e:
            logger.warning(f"Fehler beim Warten auf {selector}: {e}")
            return False

    def scroll_to_bottom(self, pause: float = 0.5, max_scrolls: int = 50) -> int:
        """
        Scrollt bis zum Ende der Seite (für Lazy Loading).

        Args:
            pause: Pause zwischen Scrolls in Sekunden.
            max_scrolls: Maximale Scroll-Versuche.

        Returns:
            Anzahl der Scroll-Vorgänge.
        """
        if not self._page:
            return 0

        scroll_count = 0
        last_height = 0

        for _ in range(max_scrolls):
            # Scroll nach unten
            self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(pause + random.uniform(0, 0.3))  # Menschliche Varianz

            # Prüfe ob neue Inhalte geladen wurden
            new_height = self._page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                break

            last_height = new_height
            scroll_count += 1

        return scroll_count

    def scroll_element(
        self,
        selector: str,
        pause: float = 0.5,
        max_scrolls: int = 50
    ) -> int:
        """
        Scrollt innerhalb eines Elements (z.B. Google Maps Sidebar).

        Args:
            selector: CSS-Selector des scrollbaren Elements.
            pause: Pause zwischen Scrolls.
            max_scrolls: Maximale Scroll-Versuche.

        Returns:
            Anzahl der Scroll-Vorgänge.
        """
        if not self._page:
            return 0

        scroll_count = 0

        for _ in range(max_scrolls):
            try:
                # Scroll im Element
                scrolled = self._page.evaluate(f"""
                    (() => {{
                        const el = document.querySelector('{selector}');
                        if (!el) return false;
                        const before = el.scrollTop;
                        el.scrollTop = el.scrollHeight;
                        return el.scrollTop !== before;
                    }})()
                """)

                if not scrolled:
                    break

                time.sleep(pause + random.uniform(0, 0.3))
                scroll_count += 1

            except Exception as e:
                logger.debug(f"Scroll-Fehler: {e}")
                break

        return scroll_count

    def click(self, selector: str, timeout: Optional[int] = None) -> bool:
        """
        Klickt auf ein Element.

        Args:
            selector: CSS-Selector.
            timeout: Timeout in ms.

        Returns:
            True wenn Klick erfolgreich.
        """
        if not self._page:
            return False

        try:
            self._page.click(selector, timeout=timeout or self._timeout)
            return True
        except Exception as e:
            logger.debug(f"Klick fehlgeschlagen für {selector}: {e}")
            return False

    def type_text(self, selector: str, text: str, delay: int = 50) -> bool:
        """
        Tippt Text in ein Eingabefeld.

        Args:
            selector: CSS-Selector.
            text: Zu tippender Text.
            delay: Verzögerung zwischen Tasten in ms.

        Returns:
            True wenn erfolgreich.
        """
        if not self._page:
            return False

        try:
            self._page.fill(selector, "")  # Leeren
            self._page.type(selector, text, delay=delay)
            return True
        except Exception as e:
            logger.debug(f"Tippen fehlgeschlagen: {e}")
            return False

    def get_content(self) -> str:
        """Gibt den aktuellen Seiteninhalt zurück."""
        if not self._page:
            return ""
        return self._page.content()

    def get_url(self) -> str:
        """Gibt die aktuelle URL zurück."""
        if not self._page:
            return ""
        return self._page.url

    def evaluate(self, script: str) -> Any:
        """
        Führt JavaScript aus.

        Args:
            script: JavaScript-Code.

        Returns:
            Rückgabewert des Scripts.
        """
        if not self._page:
            return None
        return self._page.evaluate(script)

    def query_selector_all(self, selector: str) -> List[Any]:
        """
        Findet alle Elemente.

        Args:
            selector: CSS-Selector.

        Returns:
            Liste von Element-Handles.
        """
        if not self._page:
            return []
        return self._page.query_selector_all(selector)

    def screenshot(self, path: str, full_page: bool = False) -> bool:
        """
        Erstellt einen Screenshot.

        Args:
            path: Speicherpfad.
            full_page: Gesamte Seite oder nur Viewport.

        Returns:
            True wenn erfolgreich.
        """
        if not self._page:
            return False

        try:
            self._page.screenshot(path=path, full_page=full_page)
            return True
        except Exception as e:
            logger.error(f"Screenshot fehlgeschlagen: {e}")
            return False

    def close(self) -> None:
        """Schließt den Browser."""
        if self._context:
            self._context.close()
            self._context = None
            self._page = None

        if self._browser:
            self._browser.close()
            self._browser = None

        if self._playwright:
            self._playwright.stop()
            self._playwright = None

        logger.info("Browser geschlossen")

    def __enter__(self) -> "BrowserClient":
        """Context Manager Eintritt."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context Manager Austritt."""
        self.close()

    def get_stats(self) -> Dict:
        """Gibt Statistiken zurück."""
        return {
            "request_count": self._request_count,
            "browser_running": self._browser is not None,
            "headless": self._headless,
            "proxy_active": self._current_proxy is not None
        }


@contextmanager
def create_browser(
    headless: bool = True,
    proxy_manager: Optional[ProxyManager] = None
):
    """
    Kontext-Manager für einfache Browser-Nutzung.

    Usage:
        with create_browser() as browser:
            response = browser.navigate("https://example.com")
    """
    browser = BrowserClient(headless=headless, proxy_manager=proxy_manager)
    try:
        browser.start()
        yield browser
    finally:
        browser.close()
