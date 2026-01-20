"""
Lead-Filter für die Pipeline.

Filtert und bewertet Leads basierend auf konfigurierbaren Kriterien.
"""

import logging
from typing import List, Optional, Callable
from dataclasses import dataclass

from src.models.lead import Lead, WebsiteStatus
from config.settings import FilterConfig, Settings


logger = logging.getLogger(__name__)


@dataclass
class FilterResult:
    """Ergebnis der Filterung."""
    included: bool
    reason: Optional[str] = None


class LeadFilter:
    """
    Filtert Leads basierend auf konfigurierbaren Kriterien.

    Filter-Kriterien:
    - Website-Status (keine, alt, modern, unbekannt)
    - Mindest-Qualitätsscore
    - Pflichtfelder (Telefon, E-Mail, Adresse)
    - Custom Filter-Funktionen
    """

    def __init__(self, config: Optional[FilterConfig] = None):
        """
        Initialisiert den Lead-Filter.

        Args:
            config: Filter-Konfiguration. Falls None, werden Defaults verwendet.
        """
        self._config = config or FilterConfig()
        self._custom_filters: List[Callable[[Lead], FilterResult]] = []

        # Statistiken
        self._total_processed = 0
        self._total_included = 0
        self._exclusion_reasons = {}

    def should_include(self, lead: Lead) -> FilterResult:
        """
        Prüft ob ein Lead inkludiert werden soll.

        Args:
            lead: Der zu prüfende Lead.

        Returns:
            FilterResult mit Entscheidung und Begründung.
        """
        self._total_processed += 1

        # 1. Website-Status Filter
        status_result = self._check_website_status(lead)
        if not status_result.included:
            self._record_exclusion(status_result.reason)
            return status_result

        # 2. Qualitätsscore Filter
        quality_result = self._check_quality_score(lead)
        if not quality_result.included:
            self._record_exclusion(quality_result.reason)
            return quality_result

        # 3. Pflichtfelder Filter
        required_result = self._check_required_fields(lead)
        if not required_result.included:
            self._record_exclusion(required_result.reason)
            return required_result

        # 4. Custom Filter
        for custom_filter in self._custom_filters:
            custom_result = custom_filter(lead)
            if not custom_result.included:
                self._record_exclusion(custom_result.reason)
                return custom_result

        self._total_included += 1
        return FilterResult(included=True)

    def _check_website_status(self, lead: Lead) -> FilterResult:
        """Prüft Website-Status gegen Konfiguration."""
        status = lead.website_status

        if status == WebsiteStatus.KEINE:
            if self._config.include_no_website:
                return FilterResult(included=True)
            return FilterResult(included=False, reason="website_status_keine")

        if status == WebsiteStatus.ALT:
            if self._config.include_old_website:
                return FilterResult(included=True)
            return FilterResult(included=False, reason="website_status_alt")

        if status == WebsiteStatus.MODERN:
            if self._config.include_modern_website:
                return FilterResult(included=True)
            return FilterResult(included=False, reason="website_status_modern")

        if status == WebsiteStatus.UNBEKANNT:
            if self._config.include_unknown_website:
                return FilterResult(included=True)
            return FilterResult(included=False, reason="website_status_unbekannt")

        if status == WebsiteStatus.NICHT_GEPRUEFT:
            # Noch nicht geprüft = durchlassen
            return FilterResult(included=True)

        return FilterResult(included=True)

    def _check_quality_score(self, lead: Lead) -> FilterResult:
        """Prüft Qualitätsscore gegen Minimum."""
        if lead.qualitaet_score < self._config.min_quality_score:
            return FilterResult(
                included=False,
                reason=f"quality_score_too_low_{lead.qualitaet_score}"
            )
        return FilterResult(included=True)

    def _check_required_fields(self, lead: Lead) -> FilterResult:
        """Prüft Pflichtfelder."""
        if self._config.require_phone and not lead.telefon:
            return FilterResult(included=False, reason="missing_phone")

        if self._config.require_email and not lead.email:
            return FilterResult(included=False, reason="missing_email")

        if self._config.require_address:
            if not lead.adresse.strasse or not lead.adresse.plz:
                return FilterResult(included=False, reason="missing_address")

        return FilterResult(included=True)

    def _record_exclusion(self, reason: Optional[str]) -> None:
        """Zeichnet Ausschluss-Grund auf."""
        if reason:
            self._exclusion_reasons[reason] = self._exclusion_reasons.get(reason, 0) + 1

    def add_custom_filter(self, filter_func: Callable[[Lead], FilterResult]) -> None:
        """
        Fügt einen Custom Filter hinzu.

        Args:
            filter_func: Funktion die Lead → FilterResult mappt.
        """
        self._custom_filters.append(filter_func)

    def filter_leads(self, leads: List[Lead]) -> List[Lead]:
        """
        Filtert eine Liste von Leads.

        Args:
            leads: Liste von Leads.

        Returns:
            Gefilterte Liste.
        """
        filtered = []
        for lead in leads:
            result = self.should_include(lead)
            if result.included:
                filtered.append(lead)

        logger.info(
            f"Gefiltert: {len(filtered)}/{len(leads)} Leads inkludiert "
            f"({len(leads) - len(filtered)} ausgeschlossen)"
        )

        return filtered

    def sort_leads(
        self,
        leads: List[Lead],
        by: str = "quality",
        reverse: bool = True
    ) -> List[Lead]:
        """
        Sortiert Leads nach verschiedenen Kriterien.

        Args:
            leads: Liste von Leads.
            by: Sortier-Kriterium ("quality", "name", "rating").
            reverse: Absteigend sortieren.

        Returns:
            Sortierte Liste.
        """
        if by == "quality":
            return sorted(leads, key=lambda l: l.qualitaet_score, reverse=reverse)
        elif by == "name":
            return sorted(leads, key=lambda l: l.firmenname.lower(), reverse=reverse)
        elif by == "rating":
            return sorted(
                leads,
                key=lambda l: (l.bewertung or 0, l.bewertung_anzahl or 0),
                reverse=reverse
            )
        else:
            return leads

    @property
    def stats(self) -> dict:
        """Gibt Filter-Statistiken zurück."""
        return {
            "total_processed": self._total_processed,
            "total_included": self._total_included,
            "total_excluded": self._total_processed - self._total_included,
            "inclusion_rate": (
                self._total_included / self._total_processed
                if self._total_processed > 0 else 0
            ),
            "exclusion_reasons": dict(self._exclusion_reasons)
        }

    def reset_stats(self) -> None:
        """Setzt Statistiken zurück."""
        self._total_processed = 0
        self._total_included = 0
        self._exclusion_reasons = {}


def create_blacklist_filter(blacklist: List[str]) -> Callable[[Lead], FilterResult]:
    """
    Erstellt einen Blacklist-Filter für Firmennamen.

    Args:
        blacklist: Liste von Strings die nicht im Namen vorkommen dürfen.

    Returns:
        Filter-Funktion.
    """
    blacklist_lower = [b.lower() for b in blacklist]

    def filter_func(lead: Lead) -> FilterResult:
        name_lower = lead.firmenname.lower()
        for blocked in blacklist_lower:
            if blocked in name_lower:
                return FilterResult(included=False, reason=f"blacklist_{blocked}")
        return FilterResult(included=True)

    return filter_func


def create_whitelist_filter(
    branche_whitelist: List[str]
) -> Callable[[Lead], FilterResult]:
    """
    Erstellt einen Whitelist-Filter für Branchen.

    Args:
        branche_whitelist: Liste von erlaubten Branchen-Begriffen.

    Returns:
        Filter-Funktion.
    """
    whitelist_lower = [w.lower() for w in branche_whitelist]

    def filter_func(lead: Lead) -> FilterResult:
        branche_lower = lead.branche.lower()
        for allowed in whitelist_lower:
            if allowed in branche_lower:
                return FilterResult(included=True)
        return FilterResult(included=False, reason="branche_not_in_whitelist")

    return filter_func


def create_region_filter(
    allowed_plz_prefixes: List[str]
) -> Callable[[Lead], FilterResult]:
    """
    Erstellt einen Filter für PLZ-Regionen.

    Args:
        allowed_plz_prefixes: Liste von erlaubten PLZ-Präfixen (z.B. ["10", "12", "13"]).

    Returns:
        Filter-Funktion.
    """
    def filter_func(lead: Lead) -> FilterResult:
        if not lead.adresse.plz:
            return FilterResult(included=True)  # Kein PLZ = durchlassen

        for prefix in allowed_plz_prefixes:
            if lead.adresse.plz.startswith(prefix):
                return FilterResult(included=True)

        return FilterResult(included=False, reason="plz_not_in_region")

    return filter_func
