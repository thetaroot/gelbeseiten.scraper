# Gelbe Seiten Scraper

Ein Python-Scraper für gelbeseiten.de - findet Unternehmen nach Branche und Stadt.

## Installation

```bash
pip install -r requirements.txt
```

## Verwendung

```bash
python scraper.py --branche "Friseur" --stadt "Berlin"
```

## Output

CSV-Datei mit:
- Firmenname
- Adresse
- Telefon
- Website (ja/nein)
- E-Mail (falls vorhanden)
