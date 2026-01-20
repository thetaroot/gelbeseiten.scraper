"""
Rate Limiter für kontrollierte Request-Frequenz.

Implementiert intelligente Delays und Backoff-Strategien
um Blocking durch Anti-Bot-Systeme zu vermeiden.
"""

import time
import random
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional
from threading import Lock
from enum import Enum

from config.settings import RateLimitConfig


logger = logging.getLogger(__name__)


class DomainType(str, Enum):
    """Klassifizierung von Domains für unterschiedliche Rate Limits."""
    GELBE_SEITEN = "gelbe_seiten"
    EXTERNAL = "external"


@dataclass
class DomainState:
    """Zustand für eine spezifische Domain."""
    request_count: int = 0
    last_request_time: float = 0.0
    consecutive_errors: int = 0
    is_blocked: bool = False
    blocked_until: float = 0.0


class RateLimiter:
    """
    Verwaltet Request-Frequenz mit domain-spezifischen Limits.

    Features:
    - Unterschiedliche Limits für Gelbe Seiten vs externe Sites
    - Random Delays für menschenähnliches Verhalten
    - Exponentieller Backoff bei Fehlern
    - Periodische längere Pausen
    - Thread-safe
    """

    def __init__(self, config: Optional[RateLimitConfig] = None):
        """
        Initialisiert den Rate Limiter.

        Args:
            config: Rate Limit Konfiguration. Falls None, werden Defaults verwendet.
        """
        self._config = config or RateLimitConfig()
        self._domain_states: Dict[str, DomainState] = {}
        self._lock = Lock()
        self._global_request_count = 0

    def _get_domain_state(self, domain: str) -> DomainState:
        """Holt oder erstellt den State für eine Domain."""
        if domain not in self._domain_states:
            self._domain_states[domain] = DomainState()
        return self._domain_states[domain]

    def _classify_domain(self, domain: str) -> DomainType:
        """Klassifiziert eine Domain für Rate Limiting."""
        if "gelbeseiten.de" in domain.lower():
            return DomainType.GELBE_SEITEN
        return DomainType.EXTERNAL

    def _calculate_delay(self, domain_type: DomainType, state: DomainState) -> float:
        """
        Berechnet den Delay basierend auf Domain-Typ und Zustand.

        Returns:
            Delay in Sekunden.
        """
        if domain_type == DomainType.GELBE_SEITEN:
            min_delay = self._config.gs_min_delay
            max_delay = self._config.gs_max_delay
        else:
            min_delay = self._config.ext_min_delay
            max_delay = self._config.ext_max_delay

        # Basis-Delay (random für menschenähnliches Verhalten)
        delay = random.uniform(min_delay, max_delay)

        # Erhöhe Delay bei konsekutiven Fehlern (exponentieller Backoff)
        if state.consecutive_errors > 0:
            backoff_multiplier = self._config.backoff_factor ** state.consecutive_errors
            delay *= backoff_multiplier
            # Cap bei 60 Sekunden
            delay = min(delay, 60.0)

        return delay

    def _should_take_long_pause(self, domain_type: DomainType, state: DomainState) -> bool:
        """Prüft ob eine längere Pause eingelegt werden soll."""
        if domain_type != DomainType.GELBE_SEITEN:
            return False
        return state.request_count > 0 and state.request_count % self._config.gs_pause_every_n_requests == 0

    def _get_long_pause_duration(self) -> float:
        """Gibt die Dauer einer langen Pause zurück."""
        return random.uniform(
            self._config.gs_pause_min_duration,
            self._config.gs_pause_max_duration
        )

    def wait(self, domain: str) -> float:
        """
        Wartet die angemessene Zeit vor dem nächsten Request.

        Args:
            domain: Die Ziel-Domain.

        Returns:
            Die tatsächlich gewartete Zeit in Sekunden.
        """
        with self._lock:
            state = self._get_domain_state(domain)
            domain_type = self._classify_domain(domain)

            # Prüfe ob Domain temporär blockiert
            if state.is_blocked:
                if time.time() < state.blocked_until:
                    wait_time = state.blocked_until - time.time()
                    logger.warning(f"Domain {domain} blockiert, warte {wait_time:.1f}s")
                    time.sleep(wait_time)
                    state.is_blocked = False
                else:
                    state.is_blocked = False

            # Berechne Delay
            delay = self._calculate_delay(domain_type, state)

            # Zeit seit letztem Request
            time_since_last = time.time() - state.last_request_time
            actual_delay = max(0, delay - time_since_last)

            # Prüfe ob lange Pause nötig
            if self._should_take_long_pause(domain_type, state):
                pause_duration = self._get_long_pause_duration()
                logger.info(
                    f"Periodische Pause nach {state.request_count} Requests: {pause_duration:.1f}s"
                )
                actual_delay += pause_duration

            # Warte
            if actual_delay > 0:
                time.sleep(actual_delay)

            # Update State
            state.request_count += 1
            state.last_request_time = time.time()
            self._global_request_count += 1

            return actual_delay

    def report_success(self, domain: str) -> None:
        """
        Meldet einen erfolgreichen Request.

        Args:
            domain: Die Domain des Requests.
        """
        with self._lock:
            state = self._get_domain_state(domain)
            state.consecutive_errors = 0

    def report_error(self, domain: str, status_code: int) -> None:
        """
        Meldet einen fehlgeschlagenen Request.

        Args:
            domain: Die Domain des Requests.
            status_code: Der HTTP Status Code.
        """
        with self._lock:
            state = self._get_domain_state(domain)
            state.consecutive_errors += 1

            # Bei Rate Limiting: Temporäres Blocking
            if status_code in self._config.retry_status_codes:
                block_duration = self._config.backoff_factor ** state.consecutive_errors * 5
                block_duration = min(block_duration, 300)  # Max 5 Minuten
                state.is_blocked = True
                state.blocked_until = time.time() + block_duration
                logger.warning(
                    f"Domain {domain} temporär blockiert für {block_duration:.1f}s "
                    f"nach Status {status_code}"
                )

    def should_retry(self, status_code: int, attempt: int) -> bool:
        """
        Prüft ob ein Request wiederholt werden soll.

        Args:
            status_code: Der HTTP Status Code.
            attempt: Der aktuelle Versuch (0-basiert).

        Returns:
            True wenn Retry sinnvoll.
        """
        if attempt >= self._config.max_retries:
            return False
        return status_code in self._config.retry_status_codes

    def get_retry_delay(self, attempt: int) -> float:
        """
        Berechnet den Delay vor einem Retry.

        Args:
            attempt: Der aktuelle Versuch (0-basiert).

        Returns:
            Delay in Sekunden.
        """
        base_delay = 2.0
        delay = base_delay * (self._config.backoff_factor ** attempt)
        # Jitter hinzufügen (±20%)
        jitter = delay * 0.2 * random.uniform(-1, 1)
        return delay + jitter

    def get_stats(self, domain: Optional[str] = None) -> dict:
        """
        Gibt Statistiken zurück.

        Args:
            domain: Optional - spezifische Domain. Falls None, globale Stats.

        Returns:
            Dictionary mit Statistiken.
        """
        with self._lock:
            if domain:
                state = self._get_domain_state(domain)
                return {
                    "domain": domain,
                    "request_count": state.request_count,
                    "consecutive_errors": state.consecutive_errors,
                    "is_blocked": state.is_blocked
                }
            return {
                "global_request_count": self._global_request_count,
                "tracked_domains": len(self._domain_states),
                "domains": list(self._domain_states.keys())
            }

    def reset(self, domain: Optional[str] = None) -> None:
        """
        Setzt den State zurück.

        Args:
            domain: Optional - spezifische Domain. Falls None, alles zurücksetzen.
        """
        with self._lock:
            if domain:
                if domain in self._domain_states:
                    del self._domain_states[domain]
            else:
                self._domain_states.clear()
                self._global_request_count = 0


def human_delay(min_seconds: float = 1.0, max_seconds: float = 3.0) -> float:
    """
    Einfache Hilfsfunktion für menschenähnliche Delays.

    Args:
        min_seconds: Minimale Wartezeit.
        max_seconds: Maximale Wartezeit.

    Returns:
        Die tatsächlich gewartete Zeit.
    """
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)
    return delay
