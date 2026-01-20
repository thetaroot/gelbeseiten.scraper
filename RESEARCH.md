# Research: Gelbe Seiten Scraper

## Analysierte Projekte (10+)

### Deutsche Gelbe Seiten Scraper

| Repo | Technik | Besonderheiten |
|------|---------|----------------|
| [Patrick-Vogt/yellowscrape](https://github.com/Patrick-Vogt/yellowscrape) | Scrapy | Framework-basiert, konfigurierbar |
| [Sammeeey/gelbe-seiten-crawler](https://github.com/Sammeeey/gelbe-seiten-crawler) | Scrapy | `ROBOTSTXT_OBEY = False`, Deduplizierung |
| [lamemate/yellow-spider](https://github.com/lamemate/yellow-spider) | Python | Keyword-basierte Suche |
| [C0RE1312/gelbeseiten-scraper](https://github.com/C0RE1312/gelbeseiten-scraper) | Chrome Extension | 11 Felder, JSON/CSV Export |

### US Yellow Pages Scraper (Best Practices)

| Repo | Technik | Besonderheiten |
|------|---------|----------------|
| [scrapehero/yellowpages-scraper](https://github.com/scrapehero/yellowpages-scraper) | requests + lxml | XPath Selektoren, 12 Felder |
| [sushil-rgb/YellowPage-scraper](https://github.com/sushil-rgb/YellowPage-scraper) | Playwright | User-Agent Rotation, async |
| [ZaxR/YP_scraper](https://github.com/ZaxR/YP_scraper) | Flask + Redis | Proxy + UA Rotation, Celery Tasks |
| [awcook97/yellowpages-scraper](https://github.com/awcook97/yellowpages-scraper) | Python | E-Mail Extraction von Websites |
| [adil6572/YP-business-scraper](https://github.com/adil6572/YP-business-scraper) | BeautifulSoup | CLI + Streamlit GUI |
| [abdelrhman-arnos/yellowpages-scraper](https://github.com/abdelrhman-arnos/yellowpages-scraper) | lxml + multiprocessing | Parallel Processing |

---

## Beste Ideen zum Klauen

### 1. User-Agent Rotation
```python
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

headers = {"User-Agent": random.choice(USER_AGENTS)}
```

### 2. Request Delays (Human-like)
```python
import time
import random

def human_delay():
    time.sleep(random.uniform(1.5, 3.5))
```

### 3. Retry Logic mit Backoff
```python
def fetch_with_retry(url, max_retries=5):
    for i in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                return response
        except Exception as e:
            print(f"Retry {i+1}/{max_retries}: {e}")
        time.sleep(2 ** i)  # Exponential backoff
    return None
```

### 4. XPath vs CSS Selektoren (scrapehero Beispiel)
```python
# XPath für komplexe Strukturen
XPATHS = {
    'business_name': './/a[@class="business-name"]//text()',
    'phone': './/div[@class="phones phone primary"]//text()',
    'street': './/div[@class="street-address"]//text()',
    'website': './/a[contains(@class,"website")]/@href',
}
```

### 5. Multiprocessing für Speed
```python
from multiprocessing import Pool

def scrape_page(url):
    # scraping logic
    return data

with Pool(processes=4) as pool:
    results = pool.map(scrape_page, urls)
```

### 6. CSV Export
```python
import csv

def save_to_csv(data, filename):
    if not data:
        return
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
```

### 7. Session Persistence (Cookies behalten)
```python
session = requests.Session()
session.headers.update({"User-Agent": random.choice(USER_AGENTS)})
# Alle requests über session machen
response = session.get(url)
```

---

## Gelbeseiten.de Struktur

### URL Pattern
```
https://www.gelbeseiten.de/suche/{branche}/{stadt}
https://www.gelbeseiten.de/suche/friseur/berlin
https://www.gelbeseiten.de/suche/friseur/berlin/seite-2
```

### Zu extrahierende Felder
1. Firmenname
2. Adresse (Straße, PLZ, Stadt)
3. Telefon
4. Website (ja/nein + URL)
5. E-Mail (falls vorhanden)
6. Branche/Kategorie
7. Bewertung (falls vorhanden)
8. Gelbe Seiten URL

### Herausforderung
- Keine konsistenten CSS-Klassen
- Daten in sequentiellen Text-Nodes
- Positionsbasiertes Parsing nötig

---

## Anti-Bot Best Practices

1. **User-Agent Rotation** - Chrome/Firefox auf Windows/Mac
2. **Request Delays** - 1.5-3.5 Sekunden random
3. **Session/Cookies** - Behalten für konsistente Identität
4. **Retry mit Backoff** - Exponentiell warten bei Fehlern
5. **Kein robots.txt** - `ROBOTSTXT_OBEY = False`
6. **Proxy Rotation** - Optional für große Mengen

---

## Empfohlener Tech Stack

| Komponente | Empfehlung | Grund |
|------------|------------|-------|
| HTTP | `requests` + `Session` | Einfach, stabil, Cookies |
| Parsing | `BeautifulSoup4` + `lxml` | Flexibel, schnell |
| Output | CSV | Universal, Excel-kompatibel |
| CLI | `argparse` | Standard, einfach |
| Speed | `multiprocessing` | Parallel scraping |

---

## Nächste Schritte

1. gelbeseiten.de Struktur analysieren (DevTools)
2. Basis-Scraper mit requests + BS4 bauen
3. User-Agent Rotation implementieren
4. CSV Export
5. CLI Interface
6. Testen mit verschiedenen Branchen/Städten
