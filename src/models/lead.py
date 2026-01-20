"""
Datenmodelle für Leads und zugehörige Strukturen.

Verwendet Pydantic für Validierung und Serialisierung.
"""

from pydantic import BaseModel, Field, field_validator, computed_field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import re


class WebsiteStatus(str, Enum):
    """Status der Website-Analyse."""
    KEINE = "keine"                    # Kein Website-Eintrag bei Gelbe Seiten
    ALT = "alt"                        # Als veraltet erkannt
    MODERN = "modern"                  # Moderne Website erkannt
    UNBEKANNT = "unbekannt"            # Check fehlgeschlagen/unklar
    NICHT_GEPRUEFT = "nicht_geprueft"  # Noch nicht geprüft


class Address(BaseModel):
    """Strukturierte Adressdaten."""
    strasse: Optional[str] = None
    hausnummer: Optional[str] = None
    plz: Optional[str] = None
    stadt: str
    bundesland: Optional[str] = None

    @field_validator("plz")
    @classmethod
    def validate_plz(cls, v: Optional[str]) -> Optional[str]:
        """Validiert deutsche PLZ (5 Ziffern)."""
        if v is None:
            return None
        cleaned = re.sub(r"\D", "", v)
        if len(cleaned) == 5:
            return cleaned
        return v  # Behalte Original wenn nicht valide

    def format_full(self) -> str:
        """Formatiert die vollständige Adresse."""
        parts = []
        if self.strasse:
            street = self.strasse
            if self.hausnummer:
                street += f" {self.hausnummer}"
            parts.append(street)
        if self.plz and self.stadt:
            parts.append(f"{self.plz} {self.stadt}")
        elif self.stadt:
            parts.append(self.stadt)
        return ", ".join(parts)


class WebsiteAnalysis(BaseModel):
    """Ergebnis der Website-Analyse."""
    status: WebsiteStatus = WebsiteStatus.NICHT_GEPRUEFT
    signale: List[str] = Field(default_factory=list)
    check_methode: Optional[str] = None  # "url_heuristic", "head_check", "html_scan"
    check_dauer_ms: Optional[int] = None
    fehler: Optional[str] = None

    def add_signal(self, signal: str) -> None:
        """Fügt ein Signal hinzu (vermeidet Duplikate)."""
        if signal not in self.signale:
            self.signale.append(signal)


class Lead(BaseModel):
    """Hauptdatenmodell für einen Lead/Geschäftskontakt."""

    # Identität
    firmenname: str
    branche: str
    branchen_zusatz: Optional[str] = None
    beschreibung: Optional[str] = None

    # Adresse
    adresse: Address

    # Kontaktdaten
    telefon: Optional[str] = None
    telefon_zusatz: Optional[str] = None  # z.B. "Zentrale", "Mobil"
    fax: Optional[str] = None
    email: Optional[str] = None
    website_url: Optional[str] = None

    # Website-Analyse
    website_analyse: WebsiteAnalysis = Field(default_factory=WebsiteAnalysis)

    # Business Intelligence
    bewertung: Optional[float] = Field(default=None, ge=0, le=5)
    bewertung_anzahl: Optional[int] = Field(default=None, ge=0)
    oeffnungszeiten: Optional[Dict[str, str]] = None

    # Meta
    gelbe_seiten_url: str
    gelbe_seiten_id: Optional[str] = None
    scrape_datum: datetime = Field(default_factory=datetime.now)

    @field_validator("telefon", "fax")
    @classmethod
    def clean_phone(cls, v: Optional[str]) -> Optional[str]:
        """Bereinigt Telefonnummern."""
        if v is None:
            return None
        # Entferne alles außer Ziffern, +, -, /, Leerzeichen
        cleaned = re.sub(r"[^\d+\-/\s]", "", v)
        # Normalisiere Leerzeichen
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned if cleaned else None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        """Basis-Validierung für E-Mail."""
        if v is None:
            return None
        v = v.strip().lower()
        # Einfache Regex für E-Mail
        if re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v):
            return v
        return None  # Ungültige E-Mail verwerfen

    @field_validator("website_url")
    @classmethod
    def normalize_url(cls, v: Optional[str]) -> Optional[str]:
        """Normalisiert Website-URL."""
        if v is None:
            return None
        v = v.strip()
        # Füge Schema hinzu wenn fehlend
        if v and not v.startswith(("http://", "https://")):
            v = "https://" + v
        return v if v else None

    @computed_field
    @property
    def qualitaet_score(self) -> int:
        """
        Berechnet einen Qualitätsscore von 0-100.

        Punkte:
        - Telefon: 20
        - E-Mail: 25
        - Website: 15
        - Vollständige Adresse: 15
        - Bewertungen: 10
        - Öffnungszeiten: 5
        - Beschreibung: 10
        """
        score = 0

        # Kontaktdaten
        if self.telefon:
            score += 20
        if self.email:
            score += 25
        if self.website_url:
            score += 15

        # Adresse
        if self.adresse.strasse and self.adresse.plz:
            score += 15
        elif self.adresse.strasse or self.adresse.plz:
            score += 7

        # Zusatzinfos
        if self.bewertung is not None and self.bewertung_anzahl:
            score += 10
        if self.oeffnungszeiten:
            score += 5
        if self.beschreibung:
            score += 10

        return min(score, 100)

    @computed_field
    @property
    def hat_website(self) -> bool:
        """Prüft ob eine Website vorhanden ist."""
        return self.website_url is not None

    @computed_field
    @property
    def website_status(self) -> WebsiteStatus:
        """Shortcut für Website-Status."""
        return self.website_analyse.status

    def to_export_dict(self) -> Dict[str, Any]:
        """Konvertiert Lead in Export-freundliches Dictionary."""
        return {
            "firmenname": self.firmenname,
            "branche": self.branche,
            "branchen_zusatz": self.branchen_zusatz,
            "telefon": self.telefon,
            "email": self.email,
            "website_url": self.website_url,
            "website_status": self.website_status.value,
            "website_signale": self.website_analyse.signale,
            "adresse": {
                "strasse": self.adresse.strasse,
                "hausnummer": self.adresse.hausnummer,
                "plz": self.adresse.plz,
                "stadt": self.adresse.stadt,
                "bundesland": self.adresse.bundesland,
                "formatiert": self.adresse.format_full()
            },
            "bewertung": self.bewertung,
            "bewertung_anzahl": self.bewertung_anzahl,
            "qualitaet_score": self.qualitaet_score,
            "gelbe_seiten_url": self.gelbe_seiten_url,
            "scrape_datum": self.scrape_datum.isoformat()
        }


class RawListing(BaseModel):
    """Rohdaten aus Suchergebnis-Listing (vor Detailseiten-Scrape)."""
    name: str
    detail_url: str
    telefon: Optional[str] = None
    adresse_raw: Optional[str] = None
    branche: Optional[str] = None
    hat_website: bool = False
    website_url: Optional[str] = None
    bewertung: Optional[float] = None
    bewertung_anzahl: Optional[int] = None


class ScrapingResult(BaseModel):
    """Ergebnis eines Scraping-Durchlaufs."""
    leads: List[Lead] = Field(default_factory=list)
    total_gefunden: int = 0
    total_gefiltert: int = 0
    seiten_gescraped: int = 0
    dauer_sekunden: float = 0.0
    fehler: List[str] = Field(default_factory=list)

    def add_lead(self, lead: Lead) -> None:
        """Fügt einen Lead hinzu."""
        self.leads.append(lead)

    def add_error(self, error: str) -> None:
        """Fügt einen Fehler hinzu."""
        self.fehler.append(error)
