# Gelbe Seiten Lead Scraper

Lead-Generierung für Cold Outreach: Findet Unternehmen ohne Website oder mit veralteter Website.

## Features

- **Multi-Source Scraping**: Gelbe Seiten + Google Maps kombiniert
- **Website-Analyse**: Erkennt alte/veraltete Websites automatisch
- **Stealth-Modus**: Sicheres Scraping ohne Proxy (3h Sessions)
- **DSGVO-konform**: Nur Geschäftsdaten, keine Personendaten
- **Deduplizierung**: Automatischer Abgleich zwischen Quellen
- **Export**: JSON und CSV

## Installation

```bash
# Repository klonen
git clone git@github.com-thetaroot:thetaroot/gelbe-seiten-scraper.git
cd gelbe-seiten-scraper

# Dependencies installieren
pip install -r requirements.txt

# Playwright Browser installieren (für Google Maps)
playwright install chromium
```

## Schnellstart

```bash
# Einfache Suche (nur Gelbe Seiten)
python main.py -b "Friseur" -s "Berlin" -l 50

# Beide Quellen (vollständige Marktabdeckung)
python main.py -b "Friseur" -s "Essen" --sources all -l 100

# Stealth-Modus (sicher, ohne Proxy, 3 Stunden)
python main.py -b "Friseur" -s "München" --sources all --stealth
```

## Parameter

### Pflicht-Parameter

| Parameter | Kurz | Beschreibung |
|-----------|------|--------------|
| `--branche` | `-b` | Branche/Suchbegriff (z.B. "Friseur", "Zahnarzt") |
| `--stadt` | `-s` | Stadt/Region (z.B. "Berlin", "NRW") |

### Such-Optionen

| Parameter | Default | Beschreibung |
|-----------|---------|--------------|
| `--limit` | 100 | Maximale Anzahl Leads |
| `--sources` | gelbe-seiten | Quellen: `gelbe-seiten`, `google-maps`, `all` |
| `--max-pages` | 50 | Max. Suchergebnis-Seiten |

### Stealth-Modus (sicheres Scraping ohne Proxy)

| Parameter | Default | Beschreibung |
|-----------|---------|--------------|
| `--stealth` | - | Aktiviert sicheres Scraping |
| `--duration` | 180 | Max. Laufzeit in Minuten |

**Was macht der Stealth-Modus?**
- Lange, zufällige Delays (30-90 Sekunden zwischen Requests)
- Kaffeepausen alle 12 Requests (3-8 Minuten)
- Max. 50 Requests pro Stunde
- Automatischer Stop nach Session-Limit

**Empfohlene Nutzung:**
```bash
# Morgens 3 Stunden laufen lassen
python main.py -b "Friseur" -s "Berlin" --sources all --stealth

# Über Nacht 6 Stunden
python main.py -b "Friseur" -s "Hamburg" --sources all --stealth --duration 360
```

### Website-Analyse

| Parameter | Default | Beschreibung |
|-----------|---------|--------------|
| `--website-check` | normal | Tiefe: `fast`, `normal`, `thorough` |
| `--include-modern` | false | Auch moderne Websites inkludieren |

### Filter

| Parameter | Default | Beschreibung |
|-----------|---------|--------------|
| `--min-quality` | 0 | Mindest-Qualitätsscore (0-100) |
| `--require-phone` | false | Nur Leads mit Telefonnummer |
| `--require-email` | false | Nur Leads mit E-Mail |

### Proxy (optional)

| Parameter | Beschreibung |
|-----------|--------------|
| `--use-proxy` | Proxy-Rotation aktivieren |
| `--proxy-file` | Pfad zur Proxy-Liste |

### Export

| Parameter | Default | Beschreibung |
|-----------|---------|--------------|
| `--output` | auto | Output-Dateiname |
| `--format` | json | Format: `json`, `csv`, `both` |

### Sonstige

| Parameter | Beschreibung |
|-----------|--------------|
| `--verbose` | Ausführliche Ausgabe |
| `--debug` | Debug-Modus |
| `--quiet` | Nur Fehler ausgeben |
| `--no-headless` | Browser sichtbar (Debugging) |

## Beispiele

```bash
# Kleine Stadt, schnell
python main.py -b "Zahnarzt" -s "Bottrop" -l 30

# Große Stadt, sicher über Nacht
python main.py -b "Friseur" -s "Berlin" --sources all --stealth --duration 360

# Nur Leads mit Kontaktdaten
python main.py -b "Restaurant" -s "Hamburg" --require-phone --min-quality 50

# Export in beide Formate
python main.py -b "Handwerker" -s "Köln" --format both -o leads_handwerker

# Mit Proxy-Rotation
python main.py -b "Friseur" -s "München" --sources all --use-proxy --proxy-file proxies.txt
```

## Output

### JSON-Format

```json
{
  "meta": {
    "branche": "Friseur",
    "region": "Berlin",
    "quellen": ["gelbe_seiten", "google_maps"],
    "dsgvo_konform": true
  },
  "leads": [
    {
      "firmenname": "Salon Müller",
      "telefon": "+49 30 12345678",
      "email": "info@salon-mueller.de",
      "website_url": null,
      "website_status": "keine",
      "adresse": {
        "strasse": "Hauptstraße",
        "hausnummer": "1",
        "plz": "10115",
        "stadt": "Berlin"
      },
      "quellen": ["gelbe_seiten", "google_maps"],
      "oeffnungszeiten": {"Mo-Fr": "09:00-18:00"}
    }
  ]
}
```

## Limits & Empfehlungen

| Szenario | Empfehlung |
|----------|------------|
| Kleine Stadt (<50 Leads) | Ohne Stealth, ohne Proxy |
| Mittlere Stadt (50-200) | Mit `--stealth` |
| Große Stadt (>200) | Mit `--stealth --duration 360` |
| Sehr große Stadt (>500) | Auf mehrere Tage verteilen oder Proxy |

## DSGVO-Compliance

Der Scraper extrahiert **nur öffentliche Geschäftsdaten**:
- Firmennamen, Adressen, Telefonnummern
- Geschäfts-E-Mails, Website-URLs
- Öffnungszeiten, Branchenkategorien

**Nicht extrahiert** (DSGVO):
- Reviews/Bewertungstexte
- Review-Autoren/Personennamen
- Nutzerfotos
- Inhabernamen

Details: `docs/DSGVO_COMPLIANCE.md`

## Projektstruktur

```
gelbe-seiten-scraper/
├── main.py                 # CLI Entry Point
├── config/
│   └── settings.py         # Konfiguration
├── src/
│   ├── client/             # HTTP, Browser, Proxy, Rate Limiting
│   ├── scraper/            # Gelbe Seiten, Google Maps
│   ├── parser/             # HTML Parser
│   ├── analyzer/           # Website-Analyse
│   ├── pipeline/           # Orchestrierung, Aggregation, Filter
│   ├── export/             # JSON, CSV Export
│   └── utils/              # Hilfsfunktionen
├── tests/                  # Unit Tests
└── docs/                   # Dokumentation
```

## Tests

```bash
pytest tests/ -v
```

## Troubleshooting

### "Playwright nicht installiert"
```bash
pip install playwright
playwright install chromium
```

### "Keine Leads gefunden"
- Stadt/Branche Schreibweise prüfen
- `--verbose` für Details aktivieren

### "Google blockiert"
- `--stealth` aktivieren
- Session auf mehrere Tage verteilen
- Proxy verwenden

## Lizenz

MIT License
