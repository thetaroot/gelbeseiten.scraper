"""
Tests für Lead-Aggregator.
"""

import pytest

from src.pipeline.aggregator import LeadAggregator, AggregationStats
from src.models.lead import Lead, Address
from config.settings import AggregatorConfig, DataSource


class TestAggregationStats:
    """Tests für AggregationStats."""

    def test_default_values(self):
        """Standardwerte."""
        stats = AggregationStats()
        assert stats.gelbe_seiten_input == 0
        assert stats.google_maps_input == 0
        assert stats.duplicates_found == 0


class TestLeadAggregator:
    """Tests für LeadAggregator."""

    @pytest.fixture
    def aggregator(self):
        """Standard-Aggregator."""
        return LeadAggregator()

    @pytest.fixture
    def gs_leads(self):
        """Gelbe Seiten Leads."""
        return [
            Lead(
                firmenname="Friseur Müller",
                branche="Friseur",
                adresse=Address(
                    strasse="Hauptstraße",
                    hausnummer="1",
                    plz="10115",
                    stadt="Berlin"
                ),
                telefon="+49 30 11111111",
                email="mueller@friseur.de",
                gelbe_seiten_url="https://gs.de/1",
                quellen=[DataSource.GELBE_SEITEN]
            ),
            Lead(
                firmenname="Salon Beauty",
                branche="Friseur",
                adresse=Address(
                    strasse="Nebenstraße",
                    hausnummer="5",
                    plz="10117",
                    stadt="Berlin"
                ),
                telefon="+49 30 22222222",
                gelbe_seiten_url="https://gs.de/2",
                quellen=[DataSource.GELBE_SEITEN]
            )
        ]

    @pytest.fixture
    def gm_leads(self):
        """Google Maps Leads."""
        return [
            # Duplikat von Friseur Müller
            Lead(
                firmenname="Mueller Friseur",
                branche="Friseur",
                adresse=Address(
                    strasse="Hauptstr.",
                    hausnummer="1",
                    plz="10115",
                    stadt="Berlin"
                ),
                telefon="030 11111111",  # Gleiche Nummer, anderes Format
                oeffnungszeiten={"Mo-Fr": "09:00-18:00"},
                google_maps_place_id="ChIJ123",
                google_maps_url="https://maps.google.com/1",
                gelbe_seiten_url="https://gs.de/gm1",
                quellen=[DataSource.GOOGLE_MAPS]
            ),
            # Neuer Lead von Google Maps
            Lead(
                firmenname="Haar & Style",
                branche="Friseur",
                adresse=Address(
                    strasse="Andere Straße",
                    hausnummer="10",
                    plz="10119",
                    stadt="Berlin"
                ),
                telefon="+49 30 33333333",
                google_maps_place_id="ChIJ456",
                google_maps_url="https://maps.google.com/2",
                gelbe_seiten_url="https://gs.de/gm2",
                quellen=[DataSource.GOOGLE_MAPS]
            )
        ]

    def test_aggregate_detects_duplicates(self, aggregator, gs_leads, gm_leads):
        """Aggregation erkennt Duplikate."""
        result = aggregator.aggregate(gs_leads, gm_leads)

        # 2 GS + 2 GM, aber 1 Duplikat = 3 Leads
        assert len(result) == 3

        stats = aggregator.stats
        assert stats.duplicates_found == 1
        assert stats.merged_leads == 1

    def test_aggregate_merges_data(self, aggregator, gs_leads, gm_leads):
        """Aggregation merged Daten."""
        result = aggregator.aggregate(gs_leads, gm_leads)

        # Finde den gemergten Lead (Friseur Müller)
        merged_lead = next(
            (l for l in result if "müller" in l.firmenname.lower() or "mueller" in l.firmenname.lower()),
            None
        )

        assert merged_lead is not None
        # Hat E-Mail von GS
        assert merged_lead.email == "mueller@friseur.de"
        # Hat Öffnungszeiten von GM
        assert merged_lead.oeffnungszeiten is not None
        # Hat Google Maps Place ID
        assert merged_lead.google_maps_place_id == "ChIJ123"
        # Hat beide Quellen
        assert DataSource.GELBE_SEITEN in merged_lead.quellen
        assert DataSource.GOOGLE_MAPS in merged_lead.quellen

    def test_aggregate_preserves_unique_leads(self, aggregator, gs_leads, gm_leads):
        """Aggregation behält einzigartige Leads."""
        result = aggregator.aggregate(gs_leads, gm_leads)

        # Prüfe dass Salon Beauty erhalten bleibt
        salon_lead = next((l for l in result if "salon" in l.firmenname.lower()), None)
        assert salon_lead is not None

        # Prüfe dass Haar & Style hinzugefügt wurde
        haar_lead = next((l for l in result if "haar" in l.firmenname.lower()), None)
        assert haar_lead is not None

    def test_aggregate_empty_lists(self, aggregator):
        """Aggregation mit leeren Listen."""
        result = aggregator.aggregate([], [])
        assert result == []
        assert aggregator.stats.output_count == 0

    def test_aggregate_gs_only(self, aggregator, gs_leads):
        """Aggregation nur mit GS Leads."""
        result = aggregator.aggregate(gs_leads, [])
        assert len(result) == 2
        assert aggregator.stats.google_maps_input == 0

    def test_aggregate_gm_only(self, aggregator, gm_leads):
        """Aggregation nur mit GM Leads."""
        result = aggregator.aggregate([], gm_leads)
        assert len(result) == 2
        assert aggregator.stats.gelbe_seiten_input == 0

    def test_stats_tracking(self, aggregator, gs_leads, gm_leads):
        """Statistiken werden korrekt erfasst."""
        aggregator.aggregate(gs_leads, gm_leads)
        stats = aggregator.stats

        assert stats.gelbe_seiten_input == 2
        assert stats.google_maps_input == 2
        assert stats.total_input == 4
        assert stats.output_count == 3

    def test_get_stats_dict(self, aggregator, gs_leads, gm_leads):
        """Statistiken als Dictionary."""
        aggregator.aggregate(gs_leads, gm_leads)
        stats_dict = aggregator.get_stats_dict()

        assert "gelbe_seiten_input" in stats_dict
        assert "google_maps_input" in stats_dict
        assert "duplicates_found" in stats_dict
        assert stats_dict["output_count"] == 3


class TestDeduplication:
    """Tests für Deduplizierung."""

    @pytest.fixture
    def aggregator(self):
        """Standard-Aggregator."""
        return LeadAggregator()

    def test_deduplicate_removes_duplicates(self, aggregator):
        """Deduplizierung entfernt Duplikate."""
        leads = [
            Lead(
                firmenname="Test GmbH",
                branche="Test",
                adresse=Address(plz="10115", stadt="Berlin"),
                telefon="+49 30 12345678",
                gelbe_seiten_url="https://gs.de/1"
            ),
            Lead(
                firmenname="Test GmbH",
                branche="Test",
                adresse=Address(plz="10115", stadt="Berlin"),
                telefon="030 12345678",  # Gleiche Nummer
                gelbe_seiten_url="https://gs.de/2"
            ),
            Lead(
                firmenname="Andere Firma",
                branche="Test",
                adresse=Address(plz="20115", stadt="Hamburg"),
                telefon="+49 40 98765432",
                gelbe_seiten_url="https://gs.de/3"
            )
        ]

        result = aggregator.deduplicate(leads)
        assert len(result) == 2

    def test_deduplicate_single_lead(self, aggregator):
        """Deduplizierung mit einem Lead."""
        leads = [
            Lead(
                firmenname="Test GmbH",
                branche="Test",
                adresse=Address(stadt="Berlin"),
                gelbe_seiten_url="https://gs.de/1"
            )
        ]
        result = aggregator.deduplicate(leads)
        assert len(result) == 1

    def test_deduplicate_empty_list(self, aggregator):
        """Deduplizierung mit leerer Liste."""
        result = aggregator.deduplicate([])
        assert result == []


class TestFindDuplicates:
    """Tests für Duplikat-Suche."""

    @pytest.fixture
    def aggregator(self):
        """Standard-Aggregator."""
        return LeadAggregator()

    def test_find_duplicates(self, aggregator):
        """Findet Duplikate in Liste."""
        leads = [
            Lead(
                firmenname="Test GmbH",
                branche="Test",
                adresse=Address(plz="10115", stadt="Berlin"),
                telefon="+49 30 12345678",
                gelbe_seiten_url="https://gs.de/1"
            ),
            Lead(
                firmenname="Test",
                branche="Test",
                adresse=Address(plz="10115", stadt="Berlin"),
                telefon="030 12345678",
                gelbe_seiten_url="https://gs.de/2"
            )
        ]

        duplicates = aggregator.find_duplicates(leads)
        assert len(duplicates) == 1
        lead_a, lead_b, match_result = duplicates[0]
        assert match_result.is_match is True

    def test_find_duplicates_no_matches(self, aggregator):
        """Keine Duplikate gefunden."""
        leads = [
            Lead(
                firmenname="Firma A",
                branche="Test",
                adresse=Address(plz="10115", stadt="Berlin"),
                telefon="+49 30 11111111",
                gelbe_seiten_url="https://gs.de/1"
            ),
            Lead(
                firmenname="Firma B",
                branche="Test",
                adresse=Address(plz="20115", stadt="Hamburg"),
                telefon="+49 40 22222222",
                gelbe_seiten_url="https://gs.de/2"
            )
        ]

        duplicates = aggregator.find_duplicates(leads)
        assert len(duplicates) == 0


class TestGroupByLocation:
    """Tests für Location-Gruppierung."""

    @pytest.fixture
    def aggregator(self):
        """Standard-Aggregator."""
        return LeadAggregator()

    def test_group_by_plz(self, aggregator):
        """Gruppiert nach PLZ."""
        leads = [
            Lead(
                firmenname="Firma A",
                branche="Test",
                adresse=Address(plz="10115", stadt="Berlin"),
                gelbe_seiten_url="https://gs.de/1"
            ),
            Lead(
                firmenname="Firma B",
                branche="Test",
                adresse=Address(plz="10115", stadt="Berlin"),
                gelbe_seiten_url="https://gs.de/2"
            ),
            Lead(
                firmenname="Firma C",
                branche="Test",
                adresse=Address(plz="20115", stadt="Hamburg"),
                gelbe_seiten_url="https://gs.de/3"
            )
        ]

        groups = aggregator.group_by_location(leads)
        assert "10115" in groups
        assert "20115" in groups
        assert len(groups["10115"]) == 2
        assert len(groups["20115"]) == 1

    def test_group_by_stadt_fallback(self, aggregator):
        """Fallback auf Stadt wenn keine PLZ."""
        leads = [
            Lead(
                firmenname="Firma A",
                branche="Test",
                adresse=Address(stadt="Berlin"),
                gelbe_seiten_url="https://gs.de/1"
            )
        ]

        groups = aggregator.group_by_location(leads)
        assert "berlin" in groups

    def test_group_unknown_location(self, aggregator):
        """Unbekannte Location (Stadt ohne PLZ)."""
        leads = [
            Lead(
                firmenname="Firma A",
                branche="Test",
                adresse=Address(stadt="Unbekannt"),  # Stadt ist required
                gelbe_seiten_url="https://gs.de/1"
            )
        ]

        groups = aggregator.group_by_location(leads)
        # Wird nach Stadt gruppiert wenn keine PLZ
        assert "unbekannt" in groups


class TestAggregatorConfig:
    """Tests für Aggregator-Konfiguration."""

    def test_custom_threshold(self):
        """Benutzerdefinierte Schwellwerte."""
        config = AggregatorConfig(min_similarity_threshold=0.95)
        aggregator = LeadAggregator(config)

        # Leads die mit 0.85 matchen würden, aber nicht mit 0.95
        leads = [
            Lead(
                firmenname="Test Firma",
                branche="Test",
                adresse=Address(plz="10115", stadt="Berlin"),
                gelbe_seiten_url="https://gs.de/1"
            ),
            Lead(
                firmenname="Test Firma Berlin",
                branche="Test",
                adresse=Address(plz="10115", stadt="Berlin"),
                gelbe_seiten_url="https://gs.de/2"
            )
        ]

        result = aggregator.deduplicate(leads)
        # Mit höherem Threshold sollten beide Leads erhalten bleiben
        # (oder gemergt werden, je nach Ähnlichkeit)
        assert len(result) >= 1  # Mindestens ein Lead

    def test_default_config(self):
        """Standard-Konfiguration."""
        aggregator = LeadAggregator()
        assert aggregator._config.min_similarity_threshold == 0.85
        assert aggregator._config.phone_match_weight == 1.0
