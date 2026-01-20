"""
Tests für Datenmodelle.
"""

import pytest
from datetime import datetime

from src.models.lead import (
    Lead, Address, WebsiteAnalysis, WebsiteStatus,
    RawListing, ScrapingResult
)


class TestAddress:
    """Tests für Address Model."""

    def test_format_full_complete(self):
        """Test vollständige Adresse."""
        addr = Address(
            strasse="Hauptstraße",
            hausnummer="42",
            plz="10115",
            stadt="Berlin",
            bundesland="Berlin"
        )
        assert addr.format_full() == "Hauptstraße 42, 10115 Berlin"

    def test_format_full_minimal(self):
        """Test minimale Adresse."""
        addr = Address(stadt="Berlin")
        assert addr.format_full() == "Berlin"

    def test_format_full_no_hausnummer(self):
        """Test ohne Hausnummer."""
        addr = Address(
            strasse="Hauptstraße",
            plz="10115",
            stadt="Berlin"
        )
        assert addr.format_full() == "Hauptstraße, 10115 Berlin"

    def test_plz_validation_valid(self):
        """Test gültige PLZ."""
        addr = Address(plz="10115", stadt="Berlin")
        assert addr.plz == "10115"

    def test_plz_validation_with_spaces(self):
        """Test PLZ mit Leerzeichen."""
        addr = Address(plz="10 115", stadt="Berlin")
        assert addr.plz == "10115"


class TestLead:
    """Tests für Lead Model."""

    def test_create_minimal_lead(self):
        """Test minimaler Lead."""
        lead = Lead(
            firmenname="Test GmbH",
            branche="Test",
            adresse=Address(stadt="Berlin"),
            gelbe_seiten_url="https://example.com"
        )
        assert lead.firmenname == "Test GmbH"
        assert lead.qualitaet_score >= 0

    def test_quality_score_with_phone(self):
        """Test Qualitätsscore mit Telefon."""
        lead = Lead(
            firmenname="Test GmbH",
            branche="Test",
            adresse=Address(stadt="Berlin"),
            telefon="+49 30 12345",
            gelbe_seiten_url="https://example.com"
        )
        assert lead.qualitaet_score >= 20  # Telefon gibt 20 Punkte

    def test_quality_score_with_email(self):
        """Test Qualitätsscore mit E-Mail."""
        lead = Lead(
            firmenname="Test GmbH",
            branche="Test",
            adresse=Address(stadt="Berlin"),
            email="test@example.com",
            gelbe_seiten_url="https://example.com"
        )
        assert lead.qualitaet_score >= 25  # E-Mail gibt 25 Punkte

    def test_email_validation_valid(self):
        """Test gültige E-Mail."""
        lead = Lead(
            firmenname="Test GmbH",
            branche="Test",
            adresse=Address(stadt="Berlin"),
            email="test@example.com",
            gelbe_seiten_url="https://example.com"
        )
        assert lead.email == "test@example.com"

    def test_email_validation_invalid(self):
        """Test ungültige E-Mail wird None."""
        lead = Lead(
            firmenname="Test GmbH",
            branche="Test",
            adresse=Address(stadt="Berlin"),
            email="invalid-email",
            gelbe_seiten_url="https://example.com"
        )
        assert lead.email is None

    def test_phone_cleaning(self):
        """Test Telefon-Bereinigung."""
        lead = Lead(
            firmenname="Test GmbH",
            branche="Test",
            adresse=Address(stadt="Berlin"),
            telefon="Tel: +49 (30) 12345-678",
            gelbe_seiten_url="https://example.com"
        )
        assert "12345" in lead.telefon

    def test_website_url_normalization(self):
        """Test URL-Normalisierung."""
        lead = Lead(
            firmenname="Test GmbH",
            branche="Test",
            adresse=Address(stadt="Berlin"),
            website_url="example.com",
            gelbe_seiten_url="https://example.com"
        )
        assert lead.website_url.startswith("https://")

    def test_hat_website_property(self):
        """Test hat_website Computed Property."""
        lead_with = Lead(
            firmenname="Test GmbH",
            branche="Test",
            adresse=Address(stadt="Berlin"),
            website_url="https://example.com",
            gelbe_seiten_url="https://gs.de"
        )
        lead_without = Lead(
            firmenname="Test GmbH",
            branche="Test",
            adresse=Address(stadt="Berlin"),
            gelbe_seiten_url="https://gs.de"
        )
        assert lead_with.hat_website is True
        assert lead_without.hat_website is False

    def test_to_export_dict(self):
        """Test Export-Dictionary."""
        lead = Lead(
            firmenname="Test GmbH",
            branche="Test",
            adresse=Address(stadt="Berlin", plz="10115"),
            telefon="+49 30 12345",
            gelbe_seiten_url="https://example.com"
        )
        export = lead.to_export_dict()

        assert export["firmenname"] == "Test GmbH"
        assert export["telefon"] == "+49 30 12345"
        assert "adresse" in export
        assert export["adresse"]["stadt"] == "Berlin"


class TestWebsiteAnalysis:
    """Tests für WebsiteAnalysis Model."""

    def test_default_status(self):
        """Test Default-Status."""
        analysis = WebsiteAnalysis()
        assert analysis.status == WebsiteStatus.NICHT_GEPRUEFT
        assert analysis.signale == []

    def test_add_signal(self):
        """Test Signal hinzufügen."""
        analysis = WebsiteAnalysis()
        analysis.add_signal("test_signal")
        analysis.add_signal("test_signal")  # Duplikat
        assert len(analysis.signale) == 1

    def test_status_values(self):
        """Test alle Status-Werte."""
        assert WebsiteStatus.KEINE.value == "keine"
        assert WebsiteStatus.ALT.value == "alt"
        assert WebsiteStatus.MODERN.value == "modern"


class TestRawListing:
    """Tests für RawListing Model."""

    def test_create_raw_listing(self):
        """Test RawListing Erstellung."""
        listing = RawListing(
            name="Test Firma",
            detail_url="https://example.com/firma",
            telefon="+49 30 12345",
            hat_website=True
        )
        assert listing.name == "Test Firma"
        assert listing.hat_website is True


class TestScrapingResult:
    """Tests für ScrapingResult Model."""

    def test_empty_result(self):
        """Test leeres Ergebnis."""
        result = ScrapingResult()
        assert result.leads == []
        assert result.total_gefunden == 0

    def test_add_lead(self):
        """Test Lead hinzufügen."""
        result = ScrapingResult()
        lead = Lead(
            firmenname="Test",
            branche="Test",
            adresse=Address(stadt="Berlin"),
            gelbe_seiten_url="https://example.com"
        )
        result.add_lead(lead)
        assert len(result.leads) == 1

    def test_add_error(self):
        """Test Fehler hinzufügen."""
        result = ScrapingResult()
        result.add_error("Test-Fehler")
        assert "Test-Fehler" in result.fehler
