# Gelbe Seiten Lead Scraper

Ein modularer Python-Scraper für gelbeseiten.de - findet Unternehmen ohne/mit veralteter Website für Cold Outreach.

## Features

- **Zwei-Stufen-Pipeline**: Gelbe Seiten Scraping + Website-Alters-Analyse
- **Intelligente Website-Erkennung**: URL-Heuristik, Header-Check, HTML-Scan
- **Konfigurierbare Filter**: Website-Status, Qualitätsscore, Pflichtfelder
- **AI-Ready Export**: JSON-Format optimiert für automatisierte Outreach-Generierung
- **Anti-Bot-Maßnahmen**: User-Agent Rotation, Rate Limiting, Human-like Delays

## Installation

```bash
# Repository klonen
git clone git@github.com:thetaroot/gelbeseiten.scraper.git
cd gelbeseiten.scraper

# Dependencies installieren
pip install -r requirements.txt
```

### Requirements

- Python 3.9+
- requests
- beautifulsoup4
- lxml
- pydantic

## Verwendung

### Basis-Aufruf

```bash
python main.py --branche "Friseur" --stadt "Berlin"
```

### Alle Optionen

```bash
python main.py \
  --branche "Friseur" \
  --stadt "Berlin" \
  --limit 100 \
  --website-check normal \
  --format json \
  --output leads.json \
  --verbose
```

### Parameter

| Parameter | Kurz | Default | Beschreibung |
|-----------|------|---------|--------------|
| `--branche` | `-b` | *erforderlich* | Suchbegriff/Branche |
| `--stadt` | `-s` | *erforderlich* | Stadt/Region |
| `--limit` | `-l` | 100 | Max. Anzahl Leads |
| `--website-check` | `-w` | normal | Check-Tiefe: `fast`, `normal`, `thorough` |
| `--format` | `-f` | json | Ausgabeformat: `json`, `csv`, `both` |
| `--output` | `-o` | auto | Output-Dateiname |
| `--min-quality` | | 0 | Mindest-Qualitätsscore (0-100) |
| `--include-modern` | | false | Auch moderne Websites inkludieren |
| `--require-phone` | | false | Nur Leads mit Telefonnummer |
| `--require-email` | | false | Nur Leads mit E-Mail |
| `--verbose` | `-v` | false | Ausführliche Ausgabe |
| `--quiet` | `-q` | false | Nur Fehler ausgeben |

### Beispiele

```bash
# 200 Friseure in München, nur ohne Website
python main.py -b "Friseur" -s "München" -l 200

# Zahnärzte in Hamburg, gründlicher Website-Check
python main.py -b "Zahnarzt" -s "Hamburg" --website-check thorough

# Restaurants in Köln, nur mit Telefon, CSV Export
python main.py -b "Restaurant" -s "Köln" --require-phone --format csv

# Schneller Scan für große Mengen
python main.py -b "Handwerker" -s "Berlin" -l 500 --website-check fast
```

## Output-Format

### JSON (AI-Ready)

```json
{
  "meta": {
    "branche": "Friseur",
    "region": "Berlin",
    "anzahl_leads": 87,
    "export_datum": "2024-01-20T15:30:00"
  },
  "leads": [
    {
      "firmenname": "Salon Elegance",
      "branche": "Friseursalon",
      "telefon": "+49 30 1234567",
      "email": null,
      "website_url": null,
      "website_status": "keine",
      "adresse": {
        "strasse": "Hauptstraße",
        "hausnummer": "42",
        "plz": "10115",
        "stadt": "Berlin",
        "formatiert": "Hauptstraße 42, 10115 Berlin"
      },
      "qualitaet_score": 65,
      "gelbe_seiten_url": "https://..."
    }
  ],
  "stats": {
    "total_gefunden": 150,
    "total_exportiert": 87
  }
}
```

### CSV

Semikolon-getrennt (`;`) für Excel-Kompatibilität mit UTF-8 BOM.

## Website-Check Tiefen

| Tiefe | Methoden | Dauer/100 Websites | Genauigkeit |
|-------|----------|-------------------|-------------|
| `fast` | URL-Heuristik | ~0s | ~60% |
| `normal` | URL + HEAD Request | ~50s | ~80% |
| `thorough` | URL + HEAD + HTML | ~3-4min | ~90% |

### Erkannte Signale

**Alt/Veraltet:**
- Alte Hosting-Plattformen (Geocities, bplaced, T-Online Home)
- Website-Baukästen (Jimdo, Wix, wordpress.com)
- Kein HTTPS
- Alte Server-Versionen (Apache 2.2, IIS 6)
- Alte PHP/CMS-Versionen
- Keine Viewport-Meta (nicht responsive)
- Flash-Embeds, Tabellen-Layout

**Modern:**
- Moderne Hosting (Vercel, Netlify, GitHub Pages)
- Sicherheits-Header (HSTS, CSP)
- Aktuelle CMS-Versionen
- Schema.org, Open Graph Tags

## Projektstruktur

```
gelbe-seiten-scraper/
├── main.py                 # CLI Entry Point
├── config/
│   └── settings.py         # Zentrale Konfiguration
├── src/
│   ├── client/
│   │   ├── http.py         # HTTP Client
│   │   └── rate_limiter.py # Rate Limiting
│   ├── scraper/
│   │   ├── gelbe_seiten.py # GS Scraper
│   │   └── website_scanner.py
│   ├── parser/
│   │   ├── listing.py      # Suchergebnis-Parser
│   │   └── detail.py       # Detail-Parser
│   ├── analyzer/
│   │   ├── url_heuristic.py
│   │   ├── header_check.py
│   │   └── html_scanner.py
│   ├── pipeline/
│   │   ├── orchestrator.py # Pipeline-Steuerung
│   │   └── filters.py      # Lead-Filter
│   ├── export/
│   │   ├── json_export.py
│   │   └── csv_export.py
│   ├── models/
│   │   └── lead.py         # Datenmodelle
│   └── utils/
│       └── user_agents.py
└── tests/
```

## Tests

```bash
# Alle Tests ausführen
pytest tests/ -v

# Nur Model-Tests
pytest tests/test_models.py -v

# Mit Coverage
pytest tests/ --cov=src --cov-report=html
```

## API-Nutzung

```python
from src.pipeline.orchestrator import Pipeline
from config.settings import Settings, WebsiteCheckDepth

# Settings konfigurieren
settings = Settings(
    branche="Friseur",
    stadt="Berlin",
    max_leads=50,
    website_check_depth=WebsiteCheckDepth.NORMAL
)

# Pipeline ausführen
pipeline = Pipeline(settings)
result = pipeline.run("Friseur", "Berlin", max_leads=50)

# Ergebnisse verarbeiten
for lead in result.leads:
    print(f"{lead.firmenname}: {lead.website_status.value}")
```

## Konfiguration

Alle Einstellungen können über `config/settings.py` angepasst werden:

- Rate Limiting (Delays, Pausen)
- Scraper-Einstellungen (Timeouts, UA Rotation)
- Filter-Defaults
- Export-Optionen

## Hinweise

- **Respektiere die Nutzungsbedingungen** von gelbeseiten.de
- **Verwende angemessene Delays** um Server nicht zu überlasten
- **Daten sind nur für legitime Geschäftszwecke** zu verwenden
- Die Website-Alters-Erkennung ist eine Heuristik und nicht 100% genau

## Lizenz

Privates Projekt - nicht zur öffentlichen Nutzung bestimmt.
