"""
Umfassende Liste deutscher Branchen für maximale Marktabdeckung.

Diese Liste deckt die wichtigsten lokalen Dienstleister und Geschäfte ab,
die typischerweise Cold Outreach Zielgruppen sind (kleine/mittlere Unternehmen
ohne professionelle Online-Präsenz).
"""

# Priorisiert nach Wahrscheinlichkeit für veraltete/keine Website
BRANCHEN_LISTE = [
    # Handwerk & Bau (oft ohne moderne Website)
    "Handwerker",
    "Maler",
    "Elektriker",
    "Sanitär",
    "Heizung",
    "Klempner",
    "Dachdecker",
    "Tischler",
    "Schreiner",
    "Fliesenleger",
    "Bodenleger",
    "Maurer",
    "Zimmermann",
    "Glaser",
    "Schlosser",
    "Metallbau",
    "Gartenbau",
    "Landschaftsbau",
    "Gärtner",
    "Bauunternehmen",
    "Trockenbau",
    "Stuckateur",
    "Gerüstbau",
    "Rollladen",
    "Jalousien",
    "Markisen",

    # Gesundheit & Wellness
    "Zahnarzt",
    "Arzt",
    "Hausarzt",
    "Orthopäde",
    "Physiotherapie",
    "Krankengymnastik",
    "Massage",
    "Heilpraktiker",
    "Ergotherapie",
    "Logopädie",
    "Podologe",
    "Fußpflege",
    "Chiropraktiker",
    "Osteopathie",
    "Psychotherapie",
    "Augenarzt",
    "HNO Arzt",
    "Hautarzt",
    "Kinderarzt",
    "Frauenarzt",
    "Tierarzt",
    "Zahntechnik",
    "Pflegedienst",
    "Seniorenbetreuung",

    # Schönheit & Körperpflege
    "Friseur",
    "Kosmetik",
    "Nagelstudio",
    "Kosmetikstudio",
    "Tattoo",
    "Piercing",
    "Sonnenstudio",
    "Barbershop",
    "Beautysalon",
    "Haarentfernung",
    "Permanent Makeup",

    # Gastronomie
    "Restaurant",
    "Gaststätte",
    "Pizzeria",
    "Imbiss",
    "Döner",
    "Asia Restaurant",
    "Italiener",
    "Grieche",
    "Café",
    "Bäckerei",
    "Konditorei",
    "Metzgerei",
    "Fleischerei",
    "Eisdiele",
    "Kneipe",
    "Bar",
    "Biergarten",
    "Catering",
    "Partyservice",
    "Lieferservice",

    # Einzelhandel
    "Blumenladen",
    "Florist",
    "Boutique",
    "Bekleidung",
    "Schuhladen",
    "Schmuck",
    "Uhren",
    "Optiker",
    "Hörgeräte",
    "Sanitätshaus",
    "Apotheke",
    "Reformhaus",
    "Bioladen",
    "Weinhandlung",
    "Getränkemarkt",
    "Tabak",
    "Kiosk",
    "Schreibwaren",
    "Spielwaren",
    "Elektrogeräte",
    "Haushaltsgeräte",
    "Möbel",
    "Küchen",
    "Raumausstatter",
    "Gardinen",
    "Teppiche",
    "Lampen",
    "Antiquitäten",
    "Second Hand",
    "Tierhandlung",
    "Zoofachhandel",
    "Angelbedarf",
    "Sportgeschäft",
    "Fahrradladen",
    "Musikinstrumente",
    "Bürobedarf",
    "Druckerei",
    "Copyshop",

    # Auto & Mobilität
    "Autowerkstatt",
    "KFZ Werkstatt",
    "Reifenservice",
    "Autolackierung",
    "Autoaufbereitung",
    "Autopflege",
    "Autohaus",
    "Autovermietung",
    "Fahrschule",
    "Abschleppdienst",
    "Motorrad",
    "Tankstelle",

    # Dienstleistungen
    "Schlüsseldienst",
    "Reinigung",
    "Gebäudereinigung",
    "Hausmeisterservice",
    "Umzug",
    "Entrümpelung",
    "Schädlingsbekämpfung",
    "Kammerjäger",
    "Wäscherei",
    "Änderungsschneiderei",
    "Schneider",
    "Schuhmacher",
    "Polsterei",
    "Reparaturservice",
    "Handy Reparatur",
    "Computer Reparatur",
    "Schlüsseldienst",

    # Beratung & Büro
    "Steuerberater",
    "Rechtsanwalt",
    "Notar",
    "Wirtschaftsprüfer",
    "Unternehmensberatung",
    "Versicherung",
    "Finanzberater",
    "Immobilienmakler",
    "Hausverwaltung",
    "Buchhalter",
    "Übersetzer",
    "Dolmetscher",
    "Detektei",

    # Kreativ & Medien
    "Fotograf",
    "Videoproduktion",
    "Grafikdesign",
    "Werbeagentur",
    "Druckerei",
    "Schilder",
    "Beschriftung",
    "Eventplanung",
    "DJ",
    "Musiker",
    "Künstler",

    # Bau & Architektur
    "Architekt",
    "Bauingenieur",
    "Statiker",
    "Vermessung",
    "Energieberater",
    "Sachverständiger",
    "Gutachter",

    # Bildung & Betreuung
    "Nachhilfe",
    "Musikschule",
    "Tanzschule",
    "Sprachschule",
    "Fahrschule",
    "Kindergarten",
    "Tagesmutter",
    "Kinderbetreuung",

    # Freizeit & Sport
    "Fitnessstudio",
    "Yoga",
    "Kampfsport",
    "Tanzstudio",
    "Reiterhof",
    "Schwimmschule",
    "Golfclub",
    "Tennisclub",
    "Bowling",
    "Billard",
    "Escape Room",
    "Spielhalle",

    # Haus & Garten
    "Gartenpflege",
    "Baumfällung",
    "Winterdienst",
    "Poolbau",
    "Zaunbau",
    "Terrassenbau",
    "Pflasterarbeiten",
    "Brunnen",

    # Technik & IT
    "Computer Service",
    "IT Service",
    "Telefonanlagen",
    "Alarmanlagen",
    "Videoüberwachung",
    "Elektrotechnik",
    "Antenne Satellit",

    # Sonstiges
    "Hotel",
    "Pension",
    "Ferienwohnung",
    "Campingplatz",
    "Bestattung",
    "Steinmetz",
    "Goldschmied",
    "Gravur",
    "Stempel",
    "Textildruck",
    "Werbemittel",
]

# Anzahl der Branchen
BRANCHEN_COUNT = len(BRANCHEN_LISTE)

# Kategorien für gezielte Suche
BRANCHEN_KATEGORIEN = {
    "handwerk": [
        "Handwerker", "Maler", "Elektriker", "Sanitär", "Heizung",
        "Dachdecker", "Tischler", "Fliesenleger", "Maurer", "Glaser",
        "Schlosser", "Gartenbau", "Trockenbau"
    ],
    "gesundheit": [
        "Zahnarzt", "Arzt", "Physiotherapie", "Massage", "Heilpraktiker",
        "Podologe", "Ergotherapie", "Logopädie", "Tierarzt"
    ],
    "beauty": [
        "Friseur", "Kosmetik", "Nagelstudio", "Tattoo", "Barbershop"
    ],
    "gastro": [
        "Restaurant", "Pizzeria", "Imbiss", "Café", "Bäckerei",
        "Metzgerei", "Bar", "Catering"
    ],
    "auto": [
        "Autowerkstatt", "KFZ Werkstatt", "Reifenservice", "Autohaus",
        "Fahrschule", "Autolackierung"
    ],
    "beratung": [
        "Steuerberater", "Rechtsanwalt", "Versicherung", "Immobilienmakler",
        "Finanzberater"
    ],
}


def get_branchen(kategorie: str = None) -> list:
    """
    Gibt Branchen-Liste zurück.

    Args:
        kategorie: Optional - nur bestimmte Kategorie (handwerk, gesundheit, etc.)

    Returns:
        Liste von Branchen-Strings
    """
    if kategorie and kategorie.lower() in BRANCHEN_KATEGORIEN:
        return BRANCHEN_KATEGORIEN[kategorie.lower()]
    return BRANCHEN_LISTE


def get_kategorien() -> list:
    """Gibt verfügbare Kategorien zurück."""
    return list(BRANCHEN_KATEGORIEN.keys())
