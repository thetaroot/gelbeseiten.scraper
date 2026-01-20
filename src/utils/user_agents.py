"""
User-Agent Pool und Rotation.

Enthält aktuelle Browser User-Agents für verschiedene Plattformen.
"""

import random
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class UserAgentInfo:
    """Informationen zu einem User-Agent."""
    user_agent: str
    browser: str
    platform: str
    version: str


# Aktuelle User-Agents (Stand: Januar 2024)
# Regelmäßig aktualisieren für beste Ergebnisse
USER_AGENTS: List[UserAgentInfo] = [
    # Chrome auf Windows
    UserAgentInfo(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        browser="Chrome",
        platform="Windows",
        version="120"
    ),
    UserAgentInfo(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        browser="Chrome",
        platform="Windows",
        version="119"
    ),
    UserAgentInfo(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        browser="Chrome",
        platform="Windows",
        version="121"
    ),

    # Chrome auf macOS
    UserAgentInfo(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        browser="Chrome",
        platform="macOS",
        version="120"
    ),
    UserAgentInfo(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        browser="Chrome",
        platform="macOS",
        version="119"
    ),
    UserAgentInfo(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        browser="Chrome",
        platform="macOS",
        version="120"
    ),

    # Firefox auf Windows
    UserAgentInfo(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        browser="Firefox",
        platform="Windows",
        version="121"
    ),
    UserAgentInfo(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
        browser="Firefox",
        platform="Windows",
        version="120"
    ),
    UserAgentInfo(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
        browser="Firefox",
        platform="Windows",
        version="122"
    ),

    # Firefox auf macOS
    UserAgentInfo(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
        browser="Firefox",
        platform="macOS",
        version="121"
    ),
    UserAgentInfo(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 14.2; rv:121.0) Gecko/20100101 Firefox/121.0",
        browser="Firefox",
        platform="macOS",
        version="121"
    ),

    # Safari auf macOS
    UserAgentInfo(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        browser="Safari",
        platform="macOS",
        version="17.2"
    ),
    UserAgentInfo(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
        browser="Safari",
        platform="macOS",
        version="17.2.1"
    ),

    # Edge auf Windows
    UserAgentInfo(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        browser="Edge",
        platform="Windows",
        version="120"
    ),
    UserAgentInfo(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
        browser="Edge",
        platform="Windows",
        version="119"
    ),
]


class UserAgentRotator:
    """Verwaltet User-Agent Rotation mit optionaler Gewichtung."""

    def __init__(
        self,
        agents: Optional[List[UserAgentInfo]] = None,
        prefer_chrome: bool = True
    ):
        """
        Initialisiert den Rotator.

        Args:
            agents: Liste von User-Agents. Falls None, wird der Standard-Pool verwendet.
            prefer_chrome: Wenn True, werden Chrome UAs häufiger gewählt (realistischer).
        """
        self._agents = agents or USER_AGENTS
        self._prefer_chrome = prefer_chrome
        self._current_index = 0
        self._request_count = 0

        # Erstelle gewichtete Liste wenn Chrome bevorzugt
        if prefer_chrome:
            self._weighted_agents = self._create_weighted_list()
        else:
            self._weighted_agents = self._agents

    def _create_weighted_list(self) -> List[UserAgentInfo]:
        """Erstellt gewichtete Liste (Chrome 60%, Firefox 25%, Rest 15%)."""
        weighted = []
        for agent in self._agents:
            if agent.browser == "Chrome":
                weighted.extend([agent] * 3)  # 3x Gewichtung
            elif agent.browser == "Firefox":
                weighted.extend([agent] * 2)  # 2x Gewichtung
            else:
                weighted.append(agent)  # 1x Gewichtung
        return weighted

    def get_random(self) -> str:
        """Gibt einen zufälligen User-Agent zurück."""
        agent = random.choice(self._weighted_agents)
        return agent.user_agent

    def get_next(self) -> str:
        """Gibt den nächsten User-Agent in der Rotation zurück."""
        agent = self._agents[self._current_index]
        self._current_index = (self._current_index + 1) % len(self._agents)
        return agent.user_agent

    def get_with_count(self, rotate_every: int = 10) -> str:
        """
        Gibt einen User-Agent zurück und rotiert nach n Requests.

        Args:
            rotate_every: Nach wie vielen Requests rotiert werden soll.
        """
        self._request_count += 1
        if self._request_count >= rotate_every:
            self._request_count = 0
            return self.get_next()
        return self._agents[self._current_index].user_agent

    def get_info(self, user_agent: str) -> Optional[UserAgentInfo]:
        """Gibt Informationen zu einem User-Agent zurück."""
        for agent in self._agents:
            if agent.user_agent == user_agent:
                return agent
        return None

    @property
    def count(self) -> int:
        """Anzahl der verfügbaren User-Agents."""
        return len(self._agents)


def get_browser_headers(user_agent: str) -> dict:
    """
    Generiert vollständige Browser-Header passend zum User-Agent.

    Wichtig für Glaubwürdigkeit bei Anti-Bot-Systemen.
    """
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

    # Browser-spezifische Header
    if "Firefox" in user_agent:
        headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
        # Firefox hat kein Sec-Ch-Ua
    elif "Chrome" in user_agent or "Edg" in user_agent:
        # Chrome/Edge spezifische Headers
        headers["Sec-Ch-Ua"] = '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"'
        headers["Sec-Ch-Ua-Mobile"] = "?0"
        headers["Sec-Ch-Ua-Platform"] = '"Windows"' if "Windows" in user_agent else '"macOS"'

    return headers


# Singleton-Instanz für einfachen Zugriff
_default_rotator: Optional[UserAgentRotator] = None


def get_rotator() -> UserAgentRotator:
    """Gibt die globale Rotator-Instanz zurück (Lazy Singleton)."""
    global _default_rotator
    if _default_rotator is None:
        _default_rotator = UserAgentRotator()
    return _default_rotator


def get_random_ua() -> str:
    """Shortcut: Gibt einen zufälligen User-Agent zurück."""
    return get_rotator().get_random()


def get_headers() -> dict:
    """Shortcut: Gibt vollständige Browser-Header mit zufälligem UA zurück."""
    ua = get_random_ua()
    return get_browser_headers(ua)
