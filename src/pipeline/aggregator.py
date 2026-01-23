"""
Lead-Aggregator für Multi-Source Deduplizierung.

Kombiniert Leads aus verschiedenen Quellen (Gelbe Seiten, Google Maps)
und entfernt Duplikate intelligent.
"""

import logging
from typing import List, Dict, Tuple
from dataclasses import dataclass, field

from src.models.lead import Lead
from src.utils.matching import is_duplicate, merge_leads, MatchResult
from config.settings import AggregatorConfig, DataSource


logger = logging.getLogger(__name__)


@dataclass
class AggregationStats:
    """Statistiken der Aggregation."""
    gelbe_seiten_input: int = 0
    google_maps_input: int = 0
    total_input: int = 0
    duplicates_found: int = 0
    merged_leads: int = 0
    unique_leads: int = 0
    output_count: int = 0


class LeadAggregator:
    """
    Kombiniert und dedupliziert Leads aus mehreren Quellen.

    Matching-Strategie (Priorität):
    1. Exakte Telefonnummer → definitiv Duplikat
    2. Name + PLZ (>85% Ähnlichkeit) → wahrscheinlich Duplikat
    3. Name + Adresse → möglicherweise Duplikat

    Merge-Strategie:
    - Gelbe Seiten = Primärquelle (vollständigere Daten)
    - Google Maps = Ergänzung (Öffnungszeiten, Place-ID)
    """

    def __init__(self, config: AggregatorConfig = None):
        """
        Initialisiert den Aggregator.

        Args:
            config: Aggregator-Konfiguration.
        """
        self._config = config or AggregatorConfig()
        self._stats = AggregationStats()

    def aggregate(
        self,
        gelbe_seiten_leads: List[Lead],
        google_maps_leads: List[Lead]
    ) -> List[Lead]:
        """
        Aggregiert Leads aus beiden Quellen.

        Gelbe Seiten hat Priorität (vollständigere Daten).
        Google Maps ergänzt fehlende Informationen.

        Args:
            gelbe_seiten_leads: Leads von Gelbe Seiten.
            google_maps_leads: Leads von Google Maps.

        Returns:
            Deduplizierte und gemergte Lead-Liste.
        """
        # Reset Stats
        self._stats = AggregationStats()
        self._stats.gelbe_seiten_input = len(gelbe_seiten_leads)
        self._stats.google_maps_input = len(google_maps_leads)
        self._stats.total_input = len(gelbe_seiten_leads) + len(google_maps_leads)

        logger.info(
            f"Aggregation: {len(gelbe_seiten_leads)} GS + "
            f"{len(google_maps_leads)} GM = {self._stats.total_input} Leads"
        )

        # Schritt 1: Gelbe Seiten als Basis
        result: List[Lead] = list(gelbe_seiten_leads)

        # Schritt 2: Google Maps Leads matchen und mergen
        for gm_lead in google_maps_leads:
            matched = False
            match_index = -1
            best_confidence = 0.0

            # Suche nach Duplikat in existierenden Leads
            for i, existing_lead in enumerate(result):
                match_result = is_duplicate(
                    existing_lead,
                    gm_lead,
                    phone_weight=self._config.phone_match_weight,
                    name_weight=self._config.name_match_weight,
                    address_weight=self._config.address_match_weight,
                    threshold=self._config.min_similarity_threshold
                )

                if match_result.is_match and match_result.confidence > best_confidence:
                    matched = True
                    match_index = i
                    best_confidence = match_result.confidence

            if matched:
                # Merge mit existierendem Lead
                self._stats.duplicates_found += 1
                existing = result[match_index]

                # GS hat Priorität, GM ergänzt
                merged = merge_leads(existing, gm_lead)
                result[match_index] = merged
                self._stats.merged_leads += 1

                logger.debug(
                    f"Merged: '{gm_lead.firmenname}' mit '{existing.firmenname}' "
                    f"(Confidence: {best_confidence:.2f})"
                )
            else:
                # Neuer Lead von Google Maps
                result.append(gm_lead)
                self._stats.unique_leads += 1

        self._stats.output_count = len(result)

        logger.info(
            f"Aggregation abgeschlossen: {self._stats.output_count} Leads "
            f"({self._stats.duplicates_found} Duplikate, "
            f"{self._stats.merged_leads} gemergt)"
        )

        return result

    def deduplicate(self, leads: List[Lead]) -> List[Lead]:
        """
        Dedupliziert eine Liste von Leads.

        Für Single-Source Szenarien.

        Args:
            leads: Liste zu deduplizierender Leads.

        Returns:
            Deduplizierte Liste.
        """
        if len(leads) <= 1:
            return leads

        result: List[Lead] = []
        duplicates = 0

        for lead in leads:
            is_dup = False

            for existing in result:
                match_result = is_duplicate(
                    existing,
                    lead,
                    phone_weight=self._config.phone_match_weight,
                    name_weight=self._config.name_match_weight,
                    address_weight=self._config.address_match_weight,
                    threshold=self._config.min_similarity_threshold
                )

                if match_result.is_match:
                    is_dup = True
                    duplicates += 1

                    # Merge falls sinnvoll
                    if self._config.prefer_newer_data:
                        idx = result.index(existing)
                        result[idx] = merge_leads(existing, lead)

                    break

            if not is_dup:
                result.append(lead)

        logger.info(f"Deduplizierung: {len(leads)} → {len(result)} ({duplicates} Duplikate)")
        return result

    def find_duplicates(self, leads: List[Lead]) -> List[Tuple[Lead, Lead, MatchResult]]:
        """
        Findet alle Duplikat-Paare in einer Liste.

        Nützlich für manuelle Überprüfung.

        Args:
            leads: Liste zu prüfender Leads.

        Returns:
            Liste von (Lead1, Lead2, MatchResult) Tupeln.
        """
        duplicates = []

        for i, lead_a in enumerate(leads):
            for lead_b in leads[i + 1:]:
                match_result = is_duplicate(
                    lead_a,
                    lead_b,
                    phone_weight=self._config.phone_match_weight,
                    name_weight=self._config.name_match_weight,
                    address_weight=self._config.address_match_weight,
                    threshold=self._config.min_similarity_threshold
                )

                if match_result.is_match:
                    duplicates.append((lead_a, lead_b, match_result))

        return duplicates

    def group_by_location(self, leads: List[Lead]) -> Dict[str, List[Lead]]:
        """
        Gruppiert Leads nach PLZ/Stadt.

        Args:
            leads: Liste zu gruppierender Leads.

        Returns:
            Dictionary mit PLZ/Stadt als Key.
        """
        groups: Dict[str, List[Lead]] = {}

        for lead in leads:
            # Gruppierung nach PLZ (präziser)
            if lead.adresse and lead.adresse.plz:
                key = lead.adresse.plz
            elif lead.adresse and lead.adresse.stadt:
                key = lead.adresse.stadt.lower()
            else:
                key = "unknown"

            if key not in groups:
                groups[key] = []
            groups[key].append(lead)

        return groups

    @property
    def stats(self) -> AggregationStats:
        """Gibt Aggregations-Statistiken zurück."""
        return self._stats

    def get_stats_dict(self) -> dict:
        """Gibt Statistiken als Dictionary zurück."""
        return {
            "gelbe_seiten_input": self._stats.gelbe_seiten_input,
            "google_maps_input": self._stats.google_maps_input,
            "total_input": self._stats.total_input,
            "duplicates_found": self._stats.duplicates_found,
            "merged_leads": self._stats.merged_leads,
            "unique_leads": self._stats.unique_leads,
            "output_count": self._stats.output_count
        }
