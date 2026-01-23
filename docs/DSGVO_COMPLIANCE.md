# DSGVO-Compliance Dokumentation

## Übersicht

Dieses Dokument beschreibt die DSGVO-konformen Praktiken des Gelbe Seiten Lead Scrapers. Der Scraper wurde entwickelt, um ausschließlich öffentlich zugängliche Geschäftsdaten zu extrahieren und dabei die Datenschutz-Grundverordnung (DSGVO) einzuhalten.

---

## 1. Rechtsgrundlage

### Berechtigtes Interesse (Art. 6 Abs. 1 lit. f DSGVO)

Die Verarbeitung von Geschäftsdaten erfolgt auf Grundlage des berechtigten Interesses an B2B-Geschäftskontakten. Dies umfasst:

- **Öffentliche Geschäftsdaten**: Firmennamen, Geschäftsadressen, Telefonnummern, E-Mail-Adressen, Websites
- **Geschäftsrelevante Informationen**: Branche, Öffnungszeiten, Standort
- **Keine personenbezogenen Daten**: Keine Namen von Einzelpersonen, keine privaten Kontaktdaten

### Abwägung der Interessen

| Aspekt | Bewertung |
|--------|-----------|
| Art der Daten | Öffentliche Geschäftsdaten |
| Erwartung der Betroffenen | Unternehmen erwarten Kontaktaufnahme |
| Verhältnismäßigkeit | Minimal-invasive Datenerhebung |
| Schutzmaßnahmen | Rate Limiting, keine Personendaten |

---

## 2. Erhobene Daten

### Erlaubte Geschäftsdaten

✅ Diese Daten werden extrahiert:

| Datenfeld | Quelle | Zweck |
|-----------|--------|-------|
| Firmenname | Gelbe Seiten, Google Maps | Identifikation |
| Geschäftsadresse | Gelbe Seiten, Google Maps | Lokalisierung |
| Telefon (Geschäft) | Gelbe Seiten, Google Maps | B2B-Kontakt |
| E-Mail (Geschäft) | Gelbe Seiten | B2B-Kontakt |
| Website-URL | Gelbe Seiten, Google Maps | Website-Analyse |
| Branche/Kategorie | Gelbe Seiten, Google Maps | Segmentierung |
| Öffnungszeiten | Google Maps | Service-Information |
| Bewertungsdurchschnitt | Gelbe Seiten, Google Maps | Qualitätsbewertung |

### Ausgeschlossene Personendaten

❌ Diese Daten werden NICHT extrahiert:

| Datenfeld | Grund für Ausschluss |
|-----------|---------------------|
| Review-Texte | Enthalten Personennamen und persönliche Meinungen |
| Review-Autoren | Personenbezogene Daten (Namen, Profilbilder) |
| Nutzerfotos | Können Personen zeigen |
| Owner-Namen | Personenbezogene Daten |
| Mitarbeiter-Namen | Personenbezogene Daten |
| Private Telefonnummern | Keine Geschäftsdaten |
| Private E-Mail-Adressen | Keine Geschäftsdaten |

---

## 3. Technische Schutzmaßnahmen

### Rate Limiting

- **Gelbe Seiten**: 15 Requests/Minute, 20s Pause alle 20 Requests
- **Google Maps**: 10 Requests/Minute, 40s Pause alle 15 Requests
- **Externe Websites**: 1-2s Delay zwischen Requests

### Anonymisierung

- Proxy-Rotation möglich (optional)
- Keine dauerhafte Speicherung von IP-Adressen
- Keine Tracking-Cookies

### Datenminimierung

- Nur notwendige Geschäftsdaten werden erhoben
- Keine Aggregation mit anderen Datenquellen
- Keine Profilerstellung

---

## 4. Datenverarbeitung

### Speicherdauer

- Export-Dateien werden lokal gespeichert
- Keine zentrale Datenbank
- Nutzer ist für Löschung verantwortlich

### Datensicherheit

- Keine Übertragung an Dritte
- Lokale Verarbeitung
- Verschlüsselte HTTPS-Verbindungen

---

## 5. Betroffenenrechte

### Hinweis für Unternehmen

Unternehmen können folgende Rechte geltend machen:

1. **Auskunftsrecht** (Art. 15 DSGVO): Welche Daten gespeichert sind
2. **Löschungsrecht** (Art. 17 DSGVO): Entfernung aus Export-Dateien
3. **Widerspruchsrecht** (Art. 21 DSGVO): Keine zukünftige Erhebung

### Kontaktaufnahme

Bei Fragen zur Datenverarbeitung: [Kontaktdaten des Nutzers einfügen]

---

## 6. Verwendungszweck

### Legitime Verwendung

✅ Der Scraper ist bestimmt für:

- B2B Cold Outreach für Dienstleistungen
- Marktforschung und Wettbewerbsanalyse
- Lead-Generierung für legitime Geschäftszwecke
- Identifikation von Unternehmen ohne professionelle Webpräsenz

### Nicht erlaubte Verwendung

❌ Der Scraper darf NICHT verwendet werden für:

- Spam oder unerwünschte Massenwerbung
- Weiterverkauf von Daten
- Erstellung von Personenprofilen
- Sammlung von Daten zu Privatpersonen

---

## 7. Compliance im Export

Jede Export-Datei enthält automatisch:

```json
{
  "meta": {
    "dsgvo_konform": true,
    "ausgeschlossene_daten": [
      "personenbezogene_reviews",
      "review_autoren",
      "nutzerfotos",
      "owner_namen",
      "mitarbeiter_namen"
    ],
    "rechtsgrundlage": "Berechtigtes Interesse (B2B-Geschäftsdaten)"
  }
}
```

---

## 8. Aktualisierung

Diese Dokumentation wird bei Änderungen am Scraper aktualisiert.

**Version**: 1.0
**Stand**: Januar 2026
**Autor**: [Nutzer]

---

## 9. Haftungsausschluss

Dieses Dokument stellt keine Rechtsberatung dar. Nutzer sind selbst verantwortlich für die Einhaltung der DSGVO und lokaler Datenschutzgesetze bei der Verwendung des Scrapers.

Bei rechtlichen Fragen wenden Sie sich an einen Fachanwalt für Datenschutzrecht.
