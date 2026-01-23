"""
Tests für Google Maps Scraper Komponenten.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.parser.google_maps import GoogleMapsParser
from src.client.proxy_manager import ProxyManager, ProxyConfig, ProxyType
from src.models.lead import RawListing, Lead, Address
from config.settings import DataSource


class TestProxyConfig:
    """Tests für ProxyConfig."""

    def test_http_proxy(self):
        """HTTP Proxy erstellen."""
        config = ProxyConfig(
            host="proxy.example.com",
            port=8080,
            proxy_type=ProxyType.HTTP
        )
        assert config.host == "proxy.example.com"
        assert config.port == 8080
        assert config.proxy_type == ProxyType.HTTP

    def test_proxy_url_without_auth(self):
        """Proxy URL ohne Auth."""
        config = ProxyConfig(
            host="proxy.example.com",
            port=8080,
            proxy_type=ProxyType.HTTP
        )
        assert config.url == "http://proxy.example.com:8080"

    def test_proxy_url_with_auth(self):
        """Proxy URL mit Auth."""
        config = ProxyConfig(
            host="proxy.example.com",
            port=8080,
            proxy_type=ProxyType.HTTP,
            username="user",
            password="pass"
        )
        assert config.url == "http://user:pass@proxy.example.com:8080"

    def test_socks5_proxy(self):
        """SOCKS5 Proxy."""
        config = ProxyConfig(
            host="proxy.example.com",
            port=1080,
            proxy_type=ProxyType.SOCKS5
        )
        assert config.url == "socks5://proxy.example.com:1080"

    def test_playwright_config(self):
        """Playwright Konfiguration."""
        config = ProxyConfig(
            host="proxy.example.com",
            port=8080,
            proxy_type=ProxyType.HTTP,
            username="user",
            password="pass"
        )
        pw_config = config.playwright_config
        assert "server" in pw_config
        assert pw_config["username"] == "user"
        assert pw_config["password"] == "pass"

    def test_requests_config(self):
        """Requests Library Konfiguration."""
        config = ProxyConfig(
            host="proxy.example.com",
            port=8080,
            proxy_type=ProxyType.HTTP
        )
        req_config = config.requests_config
        assert "http" in req_config
        assert "https" in req_config

    def test_failure_rate(self):
        """Fehlerrate berechnen."""
        config = ProxyConfig(host="proxy.com", port=8080)
        config.success_count = 8
        config.failure_count = 2
        assert config.failure_rate == 0.2


class TestProxyManager:
    """Tests für ProxyManager."""

    def test_no_proxies(self):
        """Ohne Proxies."""
        manager = ProxyManager()
        assert manager.get_next_proxy() is None

    def test_add_proxy(self):
        """Proxy hinzufügen."""
        manager = ProxyManager()
        proxy = ProxyConfig(
            host="proxy.example.com",
            port=8080,
            proxy_type=ProxyType.HTTP
        )
        manager.add_proxy(proxy)
        assert manager.get_next_proxy() is not None

    def test_proxy_rotation(self):
        """Proxy-Rotation."""
        manager = ProxyManager(rotate_every_n=1)  # Rotiere nach jedem Request
        proxy1 = ProxyConfig(host="proxy1.com", port=8080, proxy_type=ProxyType.HTTP)
        proxy2 = ProxyConfig(host="proxy2.com", port=8080, proxy_type=ProxyType.HTTP)

        manager.add_proxy(proxy1)
        manager.add_proxy(proxy2)

        # Sollte rotieren
        first = manager.get_next_proxy()
        second = manager.get_next_proxy()

        assert first is not None
        assert second is not None

    def test_report_failure_blocks_proxy(self):
        """Fehler blockiert Proxy."""
        manager = ProxyManager()
        proxy = ProxyConfig(host="bad-proxy.com", port=8080, proxy_type=ProxyType.HTTP)
        manager.add_proxy(proxy)

        retrieved = manager.get_next_proxy()
        assert retrieved is not None

        # Blockiere den Proxy
        manager.report_failure(proxy, block=True)

        # Sollte keinen Proxy mehr zurückgeben
        assert manager.get_next_proxy() is None

    def test_report_success(self):
        """Erfolg wird gezählt."""
        manager = ProxyManager()
        proxy = ProxyConfig(host="good-proxy.com", port=8080, proxy_type=ProxyType.HTTP)
        manager.add_proxy(proxy)

        manager.report_success(proxy)
        manager.report_success(proxy)

        stats = manager.get_stats()
        assert stats["success_count"] == 2

    def test_get_stats(self):
        """Statistiken abrufen."""
        manager = ProxyManager()
        proxy = ProxyConfig(host="proxy.com", port=8080, proxy_type=ProxyType.HTTP)
        manager.add_proxy(proxy)

        stats = manager.get_stats()
        assert "total_proxies" in stats
        assert "active_proxies" in stats
        assert stats["total_proxies"] == 1

    def test_enabled_property(self):
        """Enabled Property."""
        manager = ProxyManager(enabled=False)
        assert manager.enabled is False

        proxy = ProxyConfig(host="proxy.com", port=8080)
        manager.add_proxy(proxy)
        assert manager.enabled is True

    def test_reset_blocked(self):
        """Blockierte Proxies zurücksetzen."""
        manager = ProxyManager()
        proxy = ProxyConfig(host="proxy.com", port=8080)
        manager.add_proxy(proxy)

        manager.report_failure(proxy, block=True)
        assert manager.get_next_proxy() is None

        count = manager.reset_blocked()
        assert count == 1
        assert manager.get_next_proxy() is not None


class TestGoogleMapsParser:
    """Tests für GoogleMapsParser."""

    @pytest.fixture
    def parser(self):
        """Parser-Instanz."""
        return GoogleMapsParser()

    def test_parser_initialization(self, parser):
        """Parser wird initialisiert."""
        assert parser is not None

    def test_parse_empty_html(self, parser):
        """Leeres HTML."""
        result = parser.parse_search_results("")
        assert result == []

    def test_parse_no_results(self, parser):
        """HTML ohne Suchergebnisse."""
        html = "<html><body><div>No results</div></body></html>"
        result = parser.parse_search_results(html)
        assert result == []

    def test_dsgvo_compliance_no_reviews(self, parser):
        """DSGVO: Keine Reviews extrahiert."""
        # Simuliere HTML mit Reviews
        html = """
        <div class="place-result">
            <h3>Test Business</h3>
            <div class="reviews">
                <div class="review">
                    <span class="author">Max Mustermann</span>
                    <span class="text">Toller Service!</span>
                </div>
            </div>
        </div>
        """
        results = parser.parse_search_results(html)
        # Parser sollte keine personenbezogenen Review-Daten extrahieren
        for listing in results:
            # RawListing hat keine review_author oder review_text Felder
            assert not hasattr(listing, 'review_author')
            assert not hasattr(listing, 'review_text')

    def test_stats_property(self, parser):
        """Statistiken Property."""
        stats = parser.stats
        assert "parsed_count" in stats
        assert "error_count" in stats

    def test_reset_stats(self, parser):
        """Statistiken zurücksetzen."""
        parser._parsed_count = 10
        parser._error_count = 2
        parser.reset_stats()
        assert parser._parsed_count == 0
        assert parser._error_count == 0

    def test_clean_text(self, parser):
        """Text bereinigen."""
        assert parser._clean_text("  Test   Firma  ") == "Test Firma"
        assert parser._clean_text("") == ""

    def test_clean_phone(self, parser):
        """Telefon bereinigen."""
        assert parser._clean_phone("+49 30 12345678") == "+49 30 12345678"
        assert parser._clean_phone("") == ""

    def test_looks_like_address(self, parser):
        """Adress-Erkennung."""
        assert parser._looks_like_address("Hauptstraße 1, 10115 Berlin") is True
        assert parser._looks_like_address("Testweg 5") is True
        assert parser._looks_like_address("hello") is False
        assert parser._looks_like_address("") is False


class TestRawListingWithDataSource:
    """Tests für RawListing mit DataSource."""

    def test_raw_listing_default_source(self):
        """Standard-Quelle ist Gelbe Seiten."""
        listing = RawListing(
            name="Test Firma",
            detail_url="https://example.com"
        )
        assert listing.quelle == DataSource.GELBE_SEITEN

    def test_raw_listing_google_maps_source(self):
        """Google Maps als Quelle."""
        listing = RawListing(
            name="Test Firma",
            detail_url="https://maps.google.com",
            quelle=DataSource.GOOGLE_MAPS,
            place_id="ChIJ123"
        )
        assert listing.quelle == DataSource.GOOGLE_MAPS
        assert listing.place_id == "ChIJ123"

    def test_raw_listing_opening_hours(self):
        """Öffnungszeiten in RawListing."""
        listing = RawListing(
            name="Test Firma",
            detail_url="https://example.com",
            oeffnungszeiten={"Mo": "09:00-18:00", "Di": "09:00-18:00"}
        )
        assert listing.oeffnungszeiten is not None
        assert "Mo" in listing.oeffnungszeiten


class TestLeadWithMultiSource:
    """Tests für Lead mit Multi-Source Support."""

    def test_lead_default_source(self):
        """Standard-Quellen."""
        lead = Lead(
            firmenname="Test GmbH",
            branche="Test",
            adresse=Address(stadt="Berlin"),
            gelbe_seiten_url="https://gs.de/1"
        )
        assert DataSource.GELBE_SEITEN in lead.quellen

    def test_lead_google_maps_fields(self):
        """Google Maps spezifische Felder."""
        lead = Lead(
            firmenname="Test GmbH",
            branche="Test",
            adresse=Address(stadt="Berlin"),
            google_maps_place_id="ChIJ123",
            google_maps_url="https://maps.google.com/place/123",
            quellen=[DataSource.GOOGLE_MAPS],
            gelbe_seiten_url="https://gs.de/1"
        )
        assert lead.google_maps_place_id == "ChIJ123"
        assert lead.google_maps_url == "https://maps.google.com/place/123"

    def test_lead_merged_sources(self):
        """Lead mit beiden Quellen."""
        lead = Lead(
            firmenname="Test GmbH",
            branche="Test",
            adresse=Address(stadt="Berlin"),
            gelbe_seiten_url="https://gs.de/1",
            google_maps_place_id="ChIJ123",
            quellen=[DataSource.GELBE_SEITEN, DataSource.GOOGLE_MAPS]
        )
        assert len(lead.quellen) == 2
        assert DataSource.GELBE_SEITEN in lead.quellen
        assert DataSource.GOOGLE_MAPS in lead.quellen

    def test_lead_opening_hours(self):
        """Öffnungszeiten in Lead."""
        lead = Lead(
            firmenname="Test GmbH",
            branche="Test",
            adresse=Address(stadt="Berlin"),
            oeffnungszeiten={
                "Mo": "09:00-18:00",
                "Di": "09:00-18:00",
                "Mi": "09:00-18:00",
                "Do": "09:00-18:00",
                "Fr": "09:00-18:00"
            },
            gelbe_seiten_url="https://gs.de/1"
        )
        assert lead.oeffnungszeiten is not None
        assert len(lead.oeffnungszeiten) == 5


class TestDataSourceEnum:
    """Tests für DataSource Enum."""

    def test_enum_values(self):
        """Enum-Werte."""
        assert DataSource.GELBE_SEITEN.value == "gelbe_seiten"
        assert DataSource.GOOGLE_MAPS.value == "google_maps"
        assert DataSource.MERGED.value == "merged"

    def test_enum_comparison(self):
        """Enum-Vergleich."""
        source = DataSource.GOOGLE_MAPS
        assert source == DataSource.GOOGLE_MAPS
        assert source != DataSource.GELBE_SEITEN


class TestProxyManagerParsing:
    """Tests für Proxy-Parsing."""

    def test_parse_simple_proxy(self):
        """Einfaches Proxy-Format."""
        manager = ProxyManager()
        proxy = manager._parse_proxy_line("proxy.example.com:8080")

        assert proxy is not None
        assert proxy.host == "proxy.example.com"
        assert proxy.port == 8080

    def test_parse_proxy_with_protocol(self):
        """Proxy mit Protokoll."""
        manager = ProxyManager()
        proxy = manager._parse_proxy_line("http://proxy.example.com:8080")

        assert proxy is not None
        assert proxy.proxy_type == ProxyType.HTTP
        assert proxy.host == "proxy.example.com"

    def test_parse_proxy_with_auth(self):
        """Proxy mit Authentifizierung."""
        manager = ProxyManager()
        proxy = manager._parse_proxy_line("http://user:pass@proxy.example.com:8080")

        assert proxy is not None
        assert proxy.username == "user"
        assert proxy.password == "pass"

    def test_parse_socks5_proxy(self):
        """SOCKS5 Proxy."""
        manager = ProxyManager()
        proxy = manager._parse_proxy_line("socks5://proxy.example.com:1080")

        assert proxy is not None
        assert proxy.proxy_type == ProxyType.SOCKS5

    def test_parse_invalid_proxy(self):
        """Ungültiges Proxy-Format."""
        manager = ProxyManager()
        proxy = manager._parse_proxy_line("invalid")

        assert proxy is None

    def test_parse_empty_line(self):
        """Leere Zeile."""
        manager = ProxyManager()
        proxy = manager._parse_proxy_line("")

        assert proxy is None

    def test_parse_comment_line(self):
        """Kommentar-Zeile."""
        manager = ProxyManager()
        proxy = manager._parse_proxy_line("# This is a comment")

        assert proxy is None


class TestProxyType:
    """Tests für ProxyType Enum."""

    def test_proxy_types(self):
        """Alle Proxy-Typen."""
        assert ProxyType.HTTP.value == "http"
        assert ProxyType.HTTPS.value == "https"
        assert ProxyType.SOCKS5.value == "socks5"


class TestStealthRateLimiter:
    """Tests für StealthRateLimiter."""

    def test_stealth_limiter_creation(self):
        """Stealth-Limiter erstellen."""
        from src.client.rate_limiter import StealthRateLimiter
        from config.settings import StealthConfig

        config = StealthConfig(enabled=True, max_requests_per_hour=10)
        limiter = StealthRateLimiter(stealth_config=config)

        stats = limiter.get_stats()
        assert stats["stealth_mode"] is True
        assert stats["hourly_limit"] == 10

    def test_stealth_config_defaults(self):
        """Stealth-Config Standard-Werte."""
        from config.settings import StealthConfig

        config = StealthConfig()
        assert config.enabled is False
        assert config.min_delay == 30.0
        assert config.max_delay == 90.0
        assert config.requests_before_break == 12
        assert config.max_requests_per_hour == 50
        assert config.max_session_duration_minutes == 180
