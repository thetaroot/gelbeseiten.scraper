# Implementierungsplan: Gelbe Seiten Lead Scraper

## Projektziel

Eine modulare, erweiterbare **Sales Intelligence Pipeline**, die:
1. Firmen von gelbeseiten.de scraped (Branche + Region)
2. Firmen **ohne Website** oder mit **veralteter Website** identifiziert
3. Maximale Kontaktdaten extrahiert
4. AI-ready JSON exportiert für automatisierte Cold-Outreach

---

## Architektur

```
gelbe-seiten-scraper/
├── src/
│   ├── __init__.py
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── orchestrator.py      # Steuert gesamten Scrape-Flow
│   │   └── filters.py           # Lead-Qualifikations-Logik
│   ├── scraper/
│   │   ├── __init__.py
│   │   ├── gelbe_seiten.py      # Stage 1: Listing + Detail Scraping
│   │   └── website_scanner.py   # Stage 2: Website Age Detection
│   ├── parser/
│   │   ├── __init__.py
│   │   ├── listing.py           # Parse Suchergebnis-Seiten
│   │   └── detail.py            # Parse Firmen-Detailseiten
│   ├── analyzer/
│   │   ├── __init__.py
│   │   ├── url_heuristic.py     # Instant URL-Pattern Analyse
│   │   ├── header_check.py      # HTTP HEAD Request Analyse
│   │   └── html_scanner.py      # Minimaler HTML-Scan
│   ├── models/
│   │   ├── __init__.py
│   │   └── lead.py              # Pydantic Lead-Datenmodell
│   ├── client/
│   │   ├── __init__.py
│   │   ├── http.py              # HTTP Client mit Session, UA Rotation
│   │   └── rate_limiter.py      # Smart Delays & Throttling
│   ├── export/
│   │   ├── __init__.py
│   │   ├── json_export.py       # JSON Export
│   │   └── csv_export.py        # CSV Export (optional)
│   └── utils/
│       ├── __init__.py
│       ├── user_agents.py       # UA Pool
│       └── validators.py        # E-Mail/Telefon Validierung
├── config/
│   ├── __init__.py
│   └── settings.py              # Zentrale Konfiguration
├── tests/
│   ├── __init__.py
│   ├── test_parser.py
│   ├── test_analyzer.py
│   └── test_pipeline.py
├── main.py                      # CLI Entry Point
├── requirements.txt
├── PLAN.md
├── RESEARCH.md
└── README.md
```

---

## Datenmodell: Lead

```python
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum

class WebsiteStatus(str, Enum):
    KEINE = "keine"              # Kein Website-Eintrag
    ALT = "alt"                  # Als veraltet erkannt
    MODERN = "modern"            # Moderne Website
    UNBEKANNT = "unbekannt"      # Check fehlgeschlagen
    NICHT_GEPRUEFT = "nicht_geprueft"

class Lead(BaseModel):
    # Identität
    firmenname: str
    branche: str
    beschreibung: Optional[str] = None

    # Standort
    strasse: Optional[str] = None
    hausnummer: Optional[str] = None
    plz: Optional[str] = None
    stadt: str
    bundesland: Optional[str] = None

    # Kontakt
    telefon: Optional[str] = None
    fax: Optional[str] = None
    email: Optional[str] = None
    website_url: Optional[str] = None

    # Website-Analyse
    website_status: WebsiteStatus = WebsiteStatus.NICHT_GEPRUEFT
    website_signale: List[str] = []  # z.B. ["kein_https", "php_5", "no_viewport"]

    # Business Intelligence
    bewertung: Optional[float] = None
    bewertung_anzahl: Optional[int] = None
    oeffnungszeiten: Optional[dict] = None

    # Meta
    gelbe_seiten_url: str
    scrape_datum: datetime
    qualitaet_score: int = 0  # 0-100, berechnet aus Datenvollständigkeit
```

---

## Module im Detail

### 1. client/http.py - HTTP Client

**Funktionen:**
- `HTTPClient` Klasse mit `requests.Session`
- User-Agent Rotation (Pool von 15+ aktuellen UAs)
- Vollständige Browser-Header (Accept, Accept-Language, etc.)
- Retry-Logik mit exponentiellem Backoff
- Timeout-Handling

```python
class HTTPClient:
    def __init__(self, config: Settings)
    def get(self, url: str) -> Response
    def head(self, url: str) -> Response
    def rotate_ua(self) -> None
```

### 2. client/rate_limiter.py - Rate Limiting

**Strategie:**
- Basis-Delay: 2-3 Sekunden (random)
- Jede 20. Request: Längere Pause (15-30s)
- Bei 429/503: Exponentieller Backoff
- Domain-spezifische Limits (GS strenger als externe)

```python
class RateLimiter:
    def __init__(self, config: Settings)
    def wait(self, domain: str) -> None
    def report_error(self, domain: str, status_code: int) -> None
```

### 3. scraper/gelbe_seiten.py - Stage 1 Scraper

**Funktionen:**
- Suchergebnis-URLs generieren (Pagination)
- Listing-Seiten abrufen
- Detail-Seiten abrufen (für mehr Daten)
- Parser aufrufen

```python
class GelbeSeitenScraper:
    def __init__(self, client: HTTPClient, parser: ListingParser)
    def search(self, branche: str, stadt: str, max_seiten: int) -> List[RawListing]
    def get_detail(self, url: str) -> RawDetail
```

### 4. parser/listing.py - Listing Parser

**Extrahiert von Suchergebnis-Seiten:**
- Firmenname
- Adresse (oft zusammengefasst)
- Telefon
- Website (ja/nein + URL)
- Detail-URL
- Branche

### 5. parser/detail.py - Detail Parser

**Extrahiert von Firmen-Detailseiten:**
- Vollständige Adresse (getrennt)
- E-Mail (falls vorhanden)
- Öffnungszeiten
- Bewertungen
- Beschreibung
- Fax

### 6. analyzer/url_heuristic.py - URL Analyse (Instant)

**Prüft ohne Request:**

| Pattern | Bedeutung |
|---------|-----------|
| `*.jimdo.com`, `*.wixsite.com` | Baukasten |
| `*.bplaced.net`, `*.de.vu` | Uralt-Hoster |
| `http://` (kein HTTPS) | Veraltet |
| IP-Adresse als Domain | Sehr alt |
| `*.wordpress.com` (Subdomain) | Free-Tier |

### 7. analyzer/header_check.py - HEAD Request Analyse

**Prüft HTTP Header:**

| Header | Alt-Signal |
|--------|------------|
| `Server: Apache/2.2` | PHP 5 Ära |
| `X-Powered-By: PHP/5.x` | Unsupported |
| Kein `Strict-Transport-Security` | Kein HSTS |
| `Server: Microsoft-IIS/7` | Windows 2008 |

### 8. analyzer/html_scanner.py - HTML Scan

**Prüft HTML (nur wenn HEAD unklar):**

| Element | Alt-Signal |
|---------|------------|
| `<meta name="generator" content="WordPress 4.x">` | Alt |
| Kein `<meta name="viewport">` | Nicht responsive |
| jQuery 1.x im Source | Veraltet |
| `<table>` Layout | Uralt |
| Flash/Silverlight Embeds | Tot |

### 9. scraper/website_scanner.py - Stage 2 Scanner

**Orchestriert die Website-Analyse:**

```python
class WebsiteScanner:
    def __init__(self, client: HTTPClient, config: Settings)

    def check(self, url: str, depth: CheckDepth) -> WebsiteResult:
        # 1. URL Heuristik (immer)
        # 2. HEAD Request (wenn depth >= NORMAL)
        # 3. HTML Scan (wenn depth == THOROUGH oder HEAD unklar)
```

### 10. pipeline/orchestrator.py - Hauptsteuerung

**Steuert den gesamten Flow:**

```python
class Pipeline:
    def __init__(self, config: Settings)

    def run(self, branche: str, stadt: str, limit: int) -> List[Lead]:
        # 1. Stage 1: Gelbe Seiten scrapen
        # 2. Filter: Ohne Website → direkt Lead
        # 3. Stage 2: Website-Check für Rest
        # 4. Filter: Nur alte/keine Website behalten
        # 5. Qualitäts-Score berechnen
        # 6. Return sortiert nach Score
```

### 11. pipeline/filters.py - Lead-Filter

**Konfigurierbare Filter:**

```python
class LeadFilter:
    def __init__(self, config: Settings)

    def should_include(self, lead: Lead) -> bool:
        # Website-Status Check
        # Mindest-Datenqualität Check
        # Blacklist Check (optional)

    def calculate_score(self, lead: Lead) -> int:
        # Punkte für: Telefon, E-Mail, Adresse, etc.
```

### 12. export/json_export.py - AI-Ready Export

**Ausgabeformat:**

```json
{
  "meta": {
    "branche": "Friseur",
    "region": "Berlin",
    "anzahl_leads": 150,
    "anzahl_gescraped": 460,
    "filter_kriterien": {
      "website_status": ["keine", "alt"],
      "min_qualitaet": 30
    },
    "export_datum": "2024-01-20T14:30:00",
    "scrape_dauer_sekunden": 320
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
        "stadt": "Berlin"
      },
      "bewertung": 4.8,
      "qualitaet_score": 75,
      "gelbe_seiten_url": "https://..."
    }
  ]
}
```

---

## CLI Interface

```bash
# Basis-Aufruf
python main.py --branche "Friseur" --stadt "Berlin" --limit 100

# Alle Optionen
python main.py \
  --branche "Friseur" \
  --stadt "Berlin" \
  --limit 100 \
  --output leads.json \
  --format json \
  --website-check normal \
  --min-quality 30 \
  --include-modern false \
  --verbose
```

**Parameter:**

| Flag | Default | Beschreibung |
|------|---------|--------------|
| `--branche` | required | Suchbegriff/Branche |
| `--stadt` | required | Stadt/Region |
| `--limit` | 100 | Max. Anzahl Leads |
| `--output` | `leads_{branche}_{stadt}.json` | Output-Datei |
| `--format` | `json` | `json` oder `csv` |
| `--website-check` | `normal` | `fast`, `normal`, `thorough` |
| `--min-quality` | 0 | Mindest-Qualitätsscore (0-100) |
| `--include-modern` | `false` | Auch moderne Websites? |
| `--verbose` | `false` | Ausführliche Logs |

---

## Anti-Block Strategie

### Gelbe Seiten (strenger)

| Maßnahme | Wert |
|----------|------|
| Delay zwischen Requests | 2-4s (random) |
| Pause alle 20 Requests | 15-30s |
| User-Agent Rotation | Alle 10 Requests |
| Session Cookies | Beibehalten |
| Max Requests/Minute | ~15 |

### Externe Websites (lockerer)

| Maßnahme | Wert |
|----------|------|
| Delay zwischen Requests | 1-2s (random) |
| Timeout | 10s (schnell aufgeben) |
| Bei Fehler | Überspringen, nicht retry |
| Max parallele Requests | 1 (sequentiell) |

---

## Implementierungsreihenfolge

### Phase 1: Foundation
1. [ ] Projektstruktur erstellen (alle Ordner + `__init__.py`)
2. [ ] `config/settings.py` - Zentrale Konfiguration
3. [ ] `models/lead.py` - Pydantic Datenmodell
4. [ ] `utils/user_agents.py` - UA Pool

### Phase 2: HTTP Layer
5. [ ] `client/rate_limiter.py` - Delay-Logik
6. [ ] `client/http.py` - HTTP Client mit allen Features

### Phase 3: Gelbe Seiten (Stage 1)
7. [ ] `parser/listing.py` - Listing Parser
8. [ ] `parser/detail.py` - Detail Parser
9. [ ] `scraper/gelbe_seiten.py` - GS Scraper

### Phase 4: Website Scanner (Stage 2)
10. [ ] `analyzer/url_heuristic.py` - URL Analyse
11. [ ] `analyzer/header_check.py` - HEAD Check
12. [ ] `analyzer/html_scanner.py` - HTML Scan
13. [ ] `scraper/website_scanner.py` - Scanner Orchestrator

### Phase 5: Pipeline & Export
14. [ ] `pipeline/filters.py` - Lead Filter
15. [ ] `pipeline/orchestrator.py` - Hauptsteuerung
16. [ ] `export/json_export.py` - JSON Export
17. [ ] `export/csv_export.py` - CSV Export

### Phase 6: CLI & Finishing
18. [ ] `main.py` - CLI mit argparse
19. [ ] Tests schreiben
20. [ ] README.md aktualisieren

---

## Testplan

### Unit Tests
- Parser: Mit gespeicherten HTML-Samples testen
- Analyzer: Bekannte URLs/Header gegen erwartete Ergebnisse
- Filter: Edge Cases für Qualitäts-Scoring

### Integration Tests
- Echter Request an Gelbe Seiten (1 Seite)
- Website-Check an bekannte alte/neue Sites

### Manual Testing
- Verschiedene Branchen/Städte
- Edge Cases: Keine Treffer, viele Seiten
- Performance bei 100+ Leads

---

## Offene Entscheidungen

1. **Parallelisierung**: Später mit `asyncio` oder `multiprocessing`?
2. **Caching**: Ergebnisse cachen für wiederholte Läufe?
3. **Proxy-Support**: Optional für große Mengen?
4. **GUI**: Später Streamlit-Interface?

---

## Geschätzte Zeiten (pro 100 Leads)

| Website-Check | Dauer | Genauigkeit |
|---------------|-------|-------------|
| `fast` | ~2-3 Min | ~60% |
| `normal` | ~4-5 Min | ~80% |
| `thorough` | ~8-10 Min | ~90% |
