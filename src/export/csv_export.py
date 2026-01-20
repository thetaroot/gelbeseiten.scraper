"""
CSV Export für Lead-Daten.

Exportiert Leads in flaches CSV Format.
"""

import csv
import logging
from typing import List, Optional
from pathlib import Path
from datetime import datetime

from src.models.lead import Lead, ScrapingResult
from config.settings import ExportConfig


logger = logging.getLogger(__name__)


# Standard-Spalten für CSV Export
DEFAULT_COLUMNS = [
    "firmenname",
    "branche",
    "telefon",
    "email",
    "website_url",
    "website_status",
    "strasse",
    "hausnummer",
    "plz",
    "stadt",
    "bundesland",
    "adresse_formatiert",
    "bewertung",
    "bewertung_anzahl",
    "qualitaet_score",
    "gelbe_seiten_url",
    "scrape_datum"
]

# Minimale Spalten (nur Kontaktdaten)
MINIMAL_COLUMNS = [
    "firmenname",
    "branche",
    "telefon",
    "email",
    "website_url",
    "website_status",
    "plz",
    "stadt",
    "qualitaet_score"
]

# Vollständige Spalten (alle Daten)
FULL_COLUMNS = [
    "firmenname",
    "branche",
    "branchen_zusatz",
    "beschreibung",
    "telefon",
    "telefon_zusatz",
    "fax",
    "email",
    "website_url",
    "website_status",
    "website_signale",
    "strasse",
    "hausnummer",
    "plz",
    "stadt",
    "bundesland",
    "adresse_formatiert",
    "bewertung",
    "bewertung_anzahl",
    "oeffnungszeiten",
    "qualitaet_score",
    "gelbe_seiten_url",
    "gelbe_seiten_id",
    "scrape_datum"
]


class CSVExporter:
    """
    Exportiert Leads nach CSV.

    Features:
    - Konfigurierbare Spalten
    - UTF-8 mit BOM (Excel-kompatibel)
    - Flexible Trennzeichen
    """

    def __init__(self, config: Optional[ExportConfig] = None):
        """
        Initialisiert den CSV-Exporter.

        Args:
            config: Export-Konfiguration.
        """
        self._config = config or ExportConfig()

    def export(
        self,
        result: ScrapingResult,
        output_path: Path,
        columns: Optional[List[str]] = None,
        delimiter: str = ";",
        include_bom: bool = True
    ) -> Path:
        """
        Exportiert ScrapingResult nach CSV.

        Args:
            result: Das ScrapingResult mit Leads.
            output_path: Ziel-Dateipfad.
            columns: Spalten-Liste. Falls None, werden DEFAULT_COLUMNS verwendet.
            delimiter: Trennzeichen (Standard: ; für Excel DE).
            include_bom: UTF-8 BOM hinzufügen (Excel-kompatibel).

        Returns:
            Path zur geschriebenen Datei.
        """
        return self.export_leads(
            result.leads,
            output_path,
            columns,
            delimiter,
            include_bom
        )

    def export_leads(
        self,
        leads: List[Lead],
        output_path: Path,
        columns: Optional[List[str]] = None,
        delimiter: str = ";",
        include_bom: bool = True
    ) -> Path:
        """
        Exportiert eine Liste von Leads nach CSV.

        Args:
            leads: Liste von Lead-Objekten.
            output_path: Ziel-Dateipfad.
            columns: Spalten-Liste.
            delimiter: Trennzeichen.
            include_bom: UTF-8 BOM hinzufügen.

        Returns:
            Path zur geschriebenen Datei.
        """
        if columns is None:
            columns = DEFAULT_COLUMNS

        # Datei öffnen
        mode = "w"
        encoding = "utf-8-sig" if include_bom else "utf-8"

        with open(output_path, mode, newline="", encoding=encoding) as f:
            writer = csv.DictWriter(
                f,
                fieldnames=columns,
                delimiter=delimiter,
                quoting=csv.QUOTE_MINIMAL,
                extrasaction="ignore"
            )

            # Header schreiben
            writer.writeheader()

            # Leads schreiben
            for lead in leads:
                row = self._lead_to_row(lead)
                writer.writerow(row)

        logger.info(f"Exportiert: {len(leads)} Leads nach {output_path}")
        return output_path

    def _lead_to_row(self, lead: Lead) -> dict:
        """Konvertiert Lead zu CSV-Zeile."""
        return {
            # Identität
            "firmenname": lead.firmenname,
            "branche": lead.branche,
            "branchen_zusatz": lead.branchen_zusatz or "",
            "beschreibung": (lead.beschreibung or "")[:200],  # Kürzen für CSV

            # Kontakt
            "telefon": lead.telefon or "",
            "telefon_zusatz": lead.telefon_zusatz or "",
            "fax": lead.fax or "",
            "email": lead.email or "",
            "website_url": lead.website_url or "",

            # Website-Analyse
            "website_status": lead.website_status.value,
            "website_signale": "; ".join(lead.website_analyse.signale[:5]),  # Max 5

            # Adresse
            "strasse": lead.adresse.strasse or "",
            "hausnummer": lead.adresse.hausnummer or "",
            "plz": lead.adresse.plz or "",
            "stadt": lead.adresse.stadt,
            "bundesland": lead.adresse.bundesland or "",
            "adresse_formatiert": lead.adresse.format_full(),

            # Business Intelligence
            "bewertung": str(lead.bewertung) if lead.bewertung else "",
            "bewertung_anzahl": str(lead.bewertung_anzahl) if lead.bewertung_anzahl else "",
            "oeffnungszeiten": self._format_opening_hours(lead.oeffnungszeiten),

            # Meta
            "qualitaet_score": str(lead.qualitaet_score),
            "gelbe_seiten_url": lead.gelbe_seiten_url,
            "gelbe_seiten_id": lead.gelbe_seiten_id or "",
            "scrape_datum": lead.scrape_datum.strftime("%Y-%m-%d %H:%M")
        }

    def _format_opening_hours(self, hours: Optional[dict]) -> str:
        """Formatiert Öffnungszeiten für CSV."""
        if not hours:
            return ""
        return "; ".join([f"{k}: {v}" for k, v in hours.items()])


def export_to_csv(
    leads: List[Lead],
    output_path: str,
    columns: Optional[List[str]] = None,
    delimiter: str = ";"
) -> Path:
    """
    Convenience-Funktion für CSV-Export.

    Args:
        leads: Liste von Leads.
        output_path: Ziel-Dateipfad.
        columns: Spalten (None = Standard).
        delimiter: Trennzeichen.

    Returns:
        Path zur Datei.
    """
    exporter = CSVExporter()
    return exporter.export_leads(
        leads,
        Path(output_path),
        columns,
        delimiter
    )


def export_minimal_csv(leads: List[Lead], output_path: str) -> Path:
    """
    Exportiert Leads mit minimalen Spalten.

    Args:
        leads: Liste von Leads.
        output_path: Ziel-Dateipfad.

    Returns:
        Path zur Datei.
    """
    return export_to_csv(leads, output_path, MINIMAL_COLUMNS)


def export_full_csv(leads: List[Lead], output_path: str) -> Path:
    """
    Exportiert Leads mit allen Spalten.

    Args:
        leads: Liste von Leads.
        output_path: Ziel-Dateipfad.

    Returns:
        Path zur Datei.
    """
    return export_to_csv(leads, output_path, FULL_COLUMNS)
