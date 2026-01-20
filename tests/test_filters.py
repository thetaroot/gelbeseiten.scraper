"""
Tests für Lead-Filter.
"""

import pytest

from src.models.lead import Lead, Address, WebsiteAnalysis, WebsiteStatus
from src.pipeline.filters import (
    LeadFilter, FilterResult,
    create_blacklist_filter, create_whitelist_filter, create_region_filter
)
from config.settings import FilterConfig


def create_test_lead(
    name: str = "Test GmbH",
    website_status: WebsiteStatus = WebsiteStatus.KEINE,
    telefon: str = None,
    email: str = None,
    plz: str = "10115"
) -> Lead:
    """Erstellt Test-Lead."""
    analysis = WebsiteAnalysis(status=website_status)
    return Lead(
        firmenname=name,
        branche="Test",
        adresse=Address(stadt="Berlin", plz=plz),
        telefon=telefon,
        email=email,
        website_analyse=analysis,
        gelbe_seiten_url="https://example.com"
    )


class TestLeadFilter:
    """Tests für LeadFilter."""

    @pytest.fixture
    def default_filter(self):
        """Filter mit Default-Einstellungen."""
        return LeadFilter()

    @pytest.fixture
    def strict_filter(self):
        """Strenger Filter."""
        config = FilterConfig(
            include_no_website=True,
            include_old_website=True,
            include_modern_website=False,
            min_quality_score=20,
            require_phone=True
        )
        return LeadFilter(config)

    # Website-Status Filter
    def test_include_no_website(self, default_filter):
        """Test: Leads ohne Website werden inkludiert."""
        lead = create_test_lead(website_status=WebsiteStatus.KEINE)
        result = default_filter.should_include(lead)
        assert result.included is True

    def test_include_old_website(self, default_filter):
        """Test: Leads mit alter Website werden inkludiert."""
        lead = create_test_lead(website_status=WebsiteStatus.ALT)
        result = default_filter.should_include(lead)
        assert result.included is True

    def test_exclude_modern_website(self, default_filter):
        """Test: Leads mit moderner Website werden ausgeschlossen."""
        lead = create_test_lead(website_status=WebsiteStatus.MODERN)
        result = default_filter.should_include(lead)
        assert result.included is False
        assert "modern" in result.reason

    # Qualitätsscore Filter
    def test_quality_score_filter(self):
        """Test: Mindest-Qualitätsscore."""
        config = FilterConfig(min_quality_score=50)
        filter = LeadFilter(config)

        low_quality = create_test_lead()  # Niedriger Score
        result = filter.should_include(low_quality)
        assert result.included is False
        assert "quality" in result.reason

    # Pflichtfelder Filter
    def test_require_phone(self, strict_filter):
        """Test: Telefon erforderlich."""
        # Ohne Telefon
        lead_no_phone = create_test_lead(telefon=None)
        result = strict_filter.should_include(lead_no_phone)
        assert result.included is False
        assert "phone" in result.reason

        # Mit Telefon
        lead_with_phone = create_test_lead(telefon="+49 30 12345")
        result = strict_filter.should_include(lead_with_phone)
        # Könnte noch am Score scheitern, aber nicht am Telefon

    def test_require_email(self):
        """Test: E-Mail erforderlich."""
        config = FilterConfig(require_email=True)
        filter = LeadFilter(config)

        lead_no_email = create_test_lead(email=None)
        result = filter.should_include(lead_no_email)
        assert result.included is False
        assert "email" in result.reason

    # Filter-Liste
    def test_filter_leads(self, default_filter):
        """Test: filter_leads Methode."""
        leads = [
            create_test_lead("Firma A", WebsiteStatus.KEINE),
            create_test_lead("Firma B", WebsiteStatus.ALT),
            create_test_lead("Firma C", WebsiteStatus.MODERN),
            create_test_lead("Firma D", WebsiteStatus.KEINE),
        ]

        filtered = default_filter.filter_leads(leads)

        assert len(filtered) == 3  # A, B, D (nicht C)
        names = [l.firmenname for l in filtered]
        assert "Firma C" not in names

    # Sortierung
    def test_sort_by_quality(self, default_filter):
        """Test: Sortierung nach Qualität."""
        leads = [
            create_test_lead("Niedrig"),
            create_test_lead("Hoch", telefon="+49 30 12345", email="test@test.de"),
            create_test_lead("Mittel", telefon="+49 30 12345"),
        ]

        sorted_leads = default_filter.sort_leads(leads, by="quality", reverse=True)

        # Hoch sollte zuerst kommen (hat Telefon + E-Mail)
        assert sorted_leads[0].firmenname == "Hoch"

    def test_sort_by_name(self, default_filter):
        """Test: Sortierung nach Name."""
        leads = [
            create_test_lead("Zebra GmbH"),
            create_test_lead("Alpha GmbH"),
            create_test_lead("Mitte GmbH"),
        ]

        sorted_leads = default_filter.sort_leads(leads, by="name", reverse=False)

        assert sorted_leads[0].firmenname == "Alpha GmbH"
        assert sorted_leads[-1].firmenname == "Zebra GmbH"

    # Statistiken
    def test_stats(self, default_filter):
        """Test: Filter-Statistiken."""
        leads = [
            create_test_lead("A", WebsiteStatus.KEINE),
            create_test_lead("B", WebsiteStatus.MODERN),
        ]

        default_filter.filter_leads(leads)
        stats = default_filter.stats

        assert stats["total_processed"] == 2
        assert stats["total_included"] == 1
        assert stats["total_excluded"] == 1

    def test_reset_stats(self, default_filter):
        """Test: Statistiken zurücksetzen."""
        default_filter.filter_leads([create_test_lead()])
        default_filter.reset_stats()

        stats = default_filter.stats
        assert stats["total_processed"] == 0


class TestCustomFilters:
    """Tests für Custom Filter."""

    def test_blacklist_filter(self):
        """Test: Blacklist-Filter."""
        blacklist_filter = create_blacklist_filter(["spam", "fake"])

        # Normaler Lead
        normal = create_test_lead("Seriöse Firma GmbH")
        result = blacklist_filter(normal)
        assert result.included is True

        # Blacklisted Lead
        spam = create_test_lead("Spam Marketing GmbH")
        result = blacklist_filter(spam)
        assert result.included is False
        assert "blacklist" in result.reason

    def test_whitelist_filter(self):
        """Test: Whitelist-Filter für Branchen."""
        whitelist_filter = create_whitelist_filter(["friseur", "kosmetik"])

        # Lead mit erlaubter Branche
        friseur = Lead(
            firmenname="Salon Test",
            branche="Friseursalon",
            adresse=Address(stadt="Berlin"),
            gelbe_seiten_url="https://example.com"
        )
        result = whitelist_filter(friseur)
        assert result.included is True

        # Lead mit nicht erlaubter Branche
        restaurant = Lead(
            firmenname="Restaurant Test",
            branche="Restaurant",
            adresse=Address(stadt="Berlin"),
            gelbe_seiten_url="https://example.com"
        )
        result = whitelist_filter(restaurant)
        assert result.included is False

    def test_region_filter(self):
        """Test: Region-Filter nach PLZ."""
        region_filter = create_region_filter(["10", "12", "13"])  # Berlin

        # Lead in Berlin
        berlin = create_test_lead(plz="10115")
        result = region_filter(berlin)
        assert result.included is True

        # Lead in München
        munich = create_test_lead(plz="80331")
        result = region_filter(munich)
        assert result.included is False

    def test_add_custom_filter(self):
        """Test: Custom Filter zum LeadFilter hinzufügen."""
        lead_filter = LeadFilter()

        # Custom Filter: Nur Firmen mit "GmbH" im Namen
        def gmbh_filter(lead: Lead) -> FilterResult:
            if "gmbh" in lead.firmenname.lower():
                return FilterResult(included=True)
            return FilterResult(included=False, reason="not_gmbh")

        lead_filter.add_custom_filter(gmbh_filter)

        leads = [
            create_test_lead("Firma GmbH"),
            create_test_lead("Einzelunternehmer"),
        ]

        filtered = lead_filter.filter_leads(leads)
        assert len(filtered) == 1
        assert filtered[0].firmenname == "Firma GmbH"
