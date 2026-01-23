"""
JSON Export für Lead-Daten.

Exportiert Leads in AI-ready JSON Format.
"""

import json
import logging
from typing import List, Optional, Any
from datetime import datetime
from pathlib import Path

from src.models.lead import Lead, ScrapingResult
from config.settings import Settings, ExportConfig


logger = logging.getLogger(__name__)


class JSONExporter:
    """
    Exportiert Leads nach JSON.

    Features:
    - AI-ready Format mit Meta-Informationen
    - Konfigurierbare Felder
    - Pretty-Print Option
    - Streaming für große Datenmengen
    """

    def __init__(self, config: Optional[ExportConfig] = None):
        """
        Initialisiert den JSON-Exporter.

        Args:
            config: Export-Konfiguration.
        """
        self._config = config or ExportConfig()

    def export(
        self,
        result: ScrapingResult,
        output_path: Path,
        branche: str,
        stadt: str,
        settings: Optional[Settings] = None
    ) -> Path:
        """
        Exportiert ScrapingResult nach JSON.

        Args:
            result: Das ScrapingResult mit Leads.
            output_path: Ziel-Dateipfad.
            branche: Die gesuchte Branche.
            stadt: Die gesuchte Stadt.
            settings: Optional - für Meta-Informationen.

        Returns:
            Path zur geschriebenen Datei.
        """
        # Daten aufbereiten
        data = self._build_export_data(result, branche, stadt, settings)

        # JSON schreiben
        with open(output_path, "w", encoding=self._config.encoding) as f:
            if self._config.pretty_print:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            else:
                json.dump(data, f, ensure_ascii=False, default=str)

        logger.info(f"Exportiert: {len(result.leads)} Leads nach {output_path}")
        return output_path

    def export_leads(
        self,
        leads: List[Lead],
        output_path: Path,
        branche: str = "",
        stadt: str = ""
    ) -> Path:
        """
        Exportiert eine Liste von Leads nach JSON.

        Args:
            leads: Liste von Lead-Objekten.
            output_path: Ziel-Dateipfad.
            branche: Die gesuchte Branche.
            stadt: Die gesuchte Stadt.

        Returns:
            Path zur geschriebenen Datei.
        """
        # ScrapingResult erstellen
        result = ScrapingResult(
            leads=leads,
            total_gefunden=len(leads),
            total_gefiltert=len(leads)
        )

        return self.export(result, output_path, branche, stadt)

    def _build_export_data(
        self,
        result: ScrapingResult,
        branche: str,
        stadt: str,
        settings: Optional[Settings] = None
    ) -> dict:
        """Baut die Export-Datenstruktur auf."""
        data = {}

        # Meta-Informationen
        if self._config.include_meta:
            data["meta"] = self._build_meta(result, branche, stadt, settings)

        # Leads
        data["leads"] = [self._lead_to_dict(lead) for lead in result.leads]

        # Statistiken
        if self._config.include_meta:
            data["stats"] = {
                "total_gefunden": result.total_gefunden,
                "total_exportiert": len(result.leads),
                "seiten_gescraped": result.seiten_gescraped,
                "dauer_sekunden": round(result.dauer_sekunden, 2),
                "fehler_anzahl": len(result.fehler)
            }

            if result.fehler:
                data["stats"]["fehler"] = result.fehler[:10]  # Max 10 Fehler

        return data

    def _build_meta(
        self,
        result: ScrapingResult,
        branche: str,
        stadt: str,
        settings: Optional[Settings] = None
    ) -> dict:
        """Baut Meta-Informationen auf."""
        meta = {
            "branche": branche,
            "region": stadt,
            "anzahl_leads": len(result.leads),
            "export_datum": datetime.now().isoformat(),
            "format_version": "2.0"  # Version erhöht für Multi-Source
        }

        if settings:
            # Quellenangabe
            meta["quellen"] = [s.value for s in settings.sources]

            meta["filter_kriterien"] = {
                "website_check_depth": settings.website_check_depth.value,
                "include_no_website": settings.filter.include_no_website,
                "include_old_website": settings.filter.include_old_website,
                "include_modern_website": settings.filter.include_modern_website,
                "min_quality_score": settings.filter.min_quality_score
            }

        # DSGVO-Compliance Informationen
        meta["dsgvo_konform"] = True
        meta["ausgeschlossene_daten"] = [
            "personenbezogene_reviews",
            "review_autoren",
            "nutzerfotos",
            "owner_namen",
            "mitarbeiter_namen"
        ]
        meta["rechtsgrundlage"] = "Berechtigtes Interesse (B2B-Geschäftsdaten)"

        return meta

    def _lead_to_dict(self, lead: Lead) -> dict:
        """Konvertiert Lead zu Export-Dictionary."""
        result = {
            # Identität
            "firmenname": lead.firmenname,
            "branche": lead.branche,
            "branchen_zusatz": lead.branchen_zusatz,

            # Kontakt
            "telefon": lead.telefon,
            "email": lead.email,
            "website_url": lead.website_url,

            # Website-Analyse
            "website_status": lead.website_status.value,
            "website_signale": lead.website_analyse.signale,

            # Adresse
            "adresse": {
                "strasse": lead.adresse.strasse,
                "hausnummer": lead.adresse.hausnummer,
                "plz": lead.adresse.plz,
                "stadt": lead.adresse.stadt,
                "bundesland": lead.adresse.bundesland,
                "formatiert": lead.adresse.format_full()
            },

            # Business Intelligence
            "bewertung": lead.bewertung,
            "bewertung_anzahl": lead.bewertung_anzahl,
            "oeffnungszeiten": lead.oeffnungszeiten,

            # Scores & Meta
            "qualitaet_score": lead.qualitaet_score,
            "quellen": [q.value for q in lead.quellen],
            "scrape_datum": lead.scrape_datum.isoformat()
        }

        # Quellenspezifische URLs
        if lead.gelbe_seiten_url:
            result["gelbe_seiten_url"] = lead.gelbe_seiten_url
        if lead.google_maps_url:
            result["google_maps_url"] = lead.google_maps_url
        if lead.google_maps_place_id:
            result["google_maps_place_id"] = lead.google_maps_place_id

        return result

    def to_json_string(
        self,
        result: ScrapingResult,
        branche: str = "",
        stadt: str = ""
    ) -> str:
        """
        Konvertiert zu JSON-String (für Streaming/API).

        Args:
            result: ScrapingResult.
            branche: Branche.
            stadt: Stadt.

        Returns:
            JSON-String.
        """
        data = self._build_export_data(result, branche, stadt)

        if self._config.pretty_print:
            return json.dumps(data, ensure_ascii=False, indent=2, default=str)
        return json.dumps(data, ensure_ascii=False, default=str)


def export_to_json(
    leads: List[Lead],
    output_path: str,
    branche: str = "",
    stadt: str = "",
    pretty: bool = True
) -> Path:
    """
    Convenience-Funktion für JSON-Export.

    Args:
        leads: Liste von Leads.
        output_path: Ziel-Dateipfad.
        branche: Branche.
        stadt: Stadt.
        pretty: Pretty-Print aktivieren.

    Returns:
        Path zur Datei.
    """
    config = ExportConfig(pretty_print=pretty)
    exporter = JSONExporter(config)
    return exporter.export_leads(leads, Path(output_path), branche, stadt)


def generate_ai_prompt(leads: List[Lead], branche: str, stadt: str) -> str:
    """
    Generiert einen AI-Prompt für Outreach basierend auf den Leads.

    Args:
        leads: Liste von Leads.
        branche: Branche.
        stadt: Stadt.

    Returns:
        Prompt-String für AI.
    """
    prompt = f"""# Lead-Daten für Cold Outreach

## Kontext
- Branche: {branche}
- Region: {stadt}
- Anzahl Leads: {len(leads)}
- Diese Leads haben KEINE oder VERALTETE Websites

## Aufgabe
Erstelle personalisierte Outreach-E-Mails für jeden Lead.
Berücksichtige dabei:
1. Den Firmennamen und die Branche
2. Den Standort für lokale Bezüge
3. Den Website-Status (keine Website vs. veraltete Website)
4. Verfügbare Bewertungen

## Lead-Daten (JSON)
```json
{json.dumps([{
    "firma": l.firmenname,
    "branche": l.branche,
    "stadt": l.adresse.stadt,
    "telefon": l.telefon,
    "email": l.email,
    "website": l.website_url,
    "website_status": l.website_status.value,
    "bewertung": l.bewertung
} for l in leads[:20]], ensure_ascii=False, indent=2)}
```

## Beispiel-Vorlage
Betreff: [Personalisierter Betreff mit Stadtbezug]

Sehr geehrte/r [Ansprechpartner oder "Damen und Herren"],

[Personalisierte Einleitung mit Bezug auf die Branche und den Standort]

[Wertversprechen angepasst an Website-Status]

[Call-to-Action]

Mit freundlichen Grüßen
[Name]
"""
    return prompt
