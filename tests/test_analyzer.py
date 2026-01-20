"""
Tests für Website-Analyzer Module.
"""

import pytest

from src.analyzer.url_heuristic import (
    URLHeuristic, HeuristicResult, quick_check
)


class TestURLHeuristic:
    """Tests für URL-Heuristik."""

    @pytest.fixture
    def heuristic(self):
        """Erstellt URLHeuristic Instanz."""
        return URLHeuristic()

    # Definitiv alte URLs
    def test_geocities_url(self, heuristic):
        """Test Geocities URL (definitiv alt)."""
        result = heuristic.analyze("http://www.geocities.com/user/page")
        assert result.result == HeuristicResult.DEFINITIV_ALT
        assert "geocities" in str(result.signals).lower()

    def test_bplaced_url(self, heuristic):
        """Test bplaced URL."""
        result = heuristic.analyze("http://firma.bplaced.net")
        assert result.result in [HeuristicResult.DEFINITIV_ALT, HeuristicResult.WAHRSCHEINLICH_ALT]

    def test_t_online_home(self, heuristic):
        """Test T-Online Home URL."""
        result = heuristic.analyze("http://home.t-online.de/home/user")
        assert result.result == HeuristicResult.DEFINITIV_ALT

    def test_de_vu_domain(self, heuristic):
        """Test .de.vu Domain."""
        result = heuristic.analyze("http://firma.de.vu")
        assert result.result == HeuristicResult.DEFINITIV_ALT

    # Baukasten URLs
    def test_jimdo_url(self, heuristic):
        """Test Jimdo URL."""
        result = heuristic.analyze("https://firma.jimdo.com")
        assert result.result == HeuristicResult.BAUKASTEN
        assert "jimdo" in str(result.signals).lower()

    def test_wix_url(self, heuristic):
        """Test Wix URL."""
        result = heuristic.analyze("https://user.wixsite.com/firma")
        assert result.result == HeuristicResult.BAUKASTEN

    def test_wordpress_com_url(self, heuristic):
        """Test WordPress.com URL (Free-Tier)."""
        result = heuristic.analyze("https://firma.wordpress.com")
        assert result.result == HeuristicResult.BAUKASTEN

    # Moderne URLs
    def test_vercel_url(self, heuristic):
        """Test Vercel URL."""
        result = heuristic.analyze("https://firma.vercel.app")
        assert result.result == HeuristicResult.WAHRSCHEINLICH_MODERN

    def test_netlify_url(self, heuristic):
        """Test Netlify URL."""
        result = heuristic.analyze("https://firma.netlify.app")
        assert result.result == HeuristicResult.WAHRSCHEINLICH_MODERN

    def test_github_pages_url(self, heuristic):
        """Test GitHub Pages URL."""
        result = heuristic.analyze("https://firma.github.io")
        assert result.result == HeuristicResult.WAHRSCHEINLICH_MODERN

    # Normale URLs (unklar)
    def test_normal_domain(self, heuristic):
        """Test normale Domain."""
        result = heuristic.analyze("https://firma-berlin.de")
        assert result.result == HeuristicResult.UNKLAR

    def test_normal_domain_with_https(self, heuristic):
        """Test normale Domain mit HTTPS."""
        result = heuristic.analyze("https://www.friseur-mueller.de")
        assert result.is_https is True

    # HTTP vs HTTPS
    def test_http_detection(self, heuristic):
        """Test HTTP-Erkennung."""
        result = heuristic.analyze("http://firma.de")
        assert result.is_https is False
        assert "kein_https" in result.signals

    def test_https_detection(self, heuristic):
        """Test HTTPS-Erkennung."""
        result = heuristic.analyze("https://firma.de")
        assert result.is_https is True

    # URL-Normalisierung
    def test_url_without_scheme(self, heuristic):
        """Test URL ohne Schema."""
        result = heuristic.analyze("firma.de")
        assert result.domain == "firma.de"

    # Verdächtige Pfad-Muster
    def test_tilde_path(self, heuristic):
        """Test Tilde-Pfad (~user)."""
        result = heuristic.analyze("https://uni.de/~professor/page")
        assert "tilde_user_path" in result.signals

    def test_cgi_bin_path(self, heuristic):
        """Test CGI-BIN Pfad."""
        result = heuristic.analyze("https://firma.de/cgi-bin/form.pl")
        assert "cgi_bin_path" in result.signals

    # Hilfsmethoden
    def test_is_definitely_old(self, heuristic):
        """Test is_definitely_old Methode."""
        assert heuristic.is_definitely_old("http://site.geocities.com") is True
        assert heuristic.is_definitely_old("https://modern.de") is False

    def test_is_baukasten(self, heuristic):
        """Test is_baukasten Methode."""
        assert heuristic.is_baukasten("https://site.jimdo.com") is True
        assert heuristic.is_baukasten("https://eigenedomain.de") is False

    def test_needs_further_check(self, heuristic):
        """Test needs_further_check Methode."""
        # Normale Domain braucht weiteren Check
        assert heuristic.needs_further_check("https://firma.de") is True
        # Definitiv alte Domain braucht keinen weiteren Check
        assert heuristic.needs_further_check("http://site.geocities.com") is False


class TestQuickCheck:
    """Tests für quick_check Funktion."""

    def test_quick_check_old(self):
        """Test quick_check mit alter URL."""
        is_old, signals = quick_check("http://site.geocities.com")
        assert is_old is True
        assert len(signals) > 0

    def test_quick_check_modern(self):
        """Test quick_check mit moderner URL."""
        is_old, signals = quick_check("https://firma.vercel.app")
        assert is_old is False

    def test_quick_check_baukasten(self):
        """Test quick_check mit Baukasten."""
        is_old, signals = quick_check("https://firma.jimdo.com")
        assert is_old is True  # Baukasten gilt als "alt"

    def test_quick_check_normal(self):
        """Test quick_check mit normaler URL."""
        is_old, signals = quick_check("https://www.normale-firma.de")
        assert is_old is False


class TestAnalyzedCount:
    """Tests für Statistik-Tracking."""

    def test_analyzed_count_increments(self):
        """Test dass analyzed_count inkrementiert wird."""
        heuristic = URLHeuristic()
        initial = heuristic.analyzed_count

        heuristic.analyze("https://test1.de")
        heuristic.analyze("https://test2.de")
        heuristic.analyze("https://test3.de")

        assert heuristic.analyzed_count == initial + 3
