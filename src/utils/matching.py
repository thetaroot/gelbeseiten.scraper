"""
Matching-Utilities für Lead-Deduplizierung.

Verwendet Levenshtein-Distanz und Normalisierung
für fuzzy matching von Firmennamen, Adressen und Telefonnummern.
"""

import re
import logging
from typing import Tuple, Optional
from dataclasses import dataclass

from Levenshtein import ratio as levenshtein_ratio

from src.models.lead import Lead


logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """Ergebnis eines Lead-Matchings."""
    is_match: bool
    confidence: float  # 0.0 - 1.0
    match_reasons: list  # Liste der übereinstimmenden Felder
    mismatch_reasons: list  # Liste der nicht übereinstimmenden Felder


def normalize_phone(phone: Optional[str]) -> str:
    """
    Normalisiert eine Telefonnummer für Vergleiche.

    Entfernt:
    - Ländervorwahl (+49, 0049)
    - Führende 0
    - Leerzeichen, Bindestriche, Schrägstriche

    Args:
        phone: Die zu normalisierende Telefonnummer.

    Returns:
        Normalisierte Nummer (nur Ziffern).
    """
    if not phone:
        return ""

    # Nur Ziffern behalten
    digits = re.sub(r"\D", "", phone)

    # Deutsche Ländervorwahl entfernen
    if digits.startswith("49") and len(digits) > 10:
        digits = digits[2:]
    elif digits.startswith("0049") and len(digits) > 12:
        digits = digits[4:]

    # Führende 0 entfernen (Vorwahl)
    if digits.startswith("0"):
        digits = digits[1:]

    return digits


def normalize_name(name: Optional[str]) -> str:
    """
    Normalisiert einen Firmennamen für Vergleiche.

    - Lowercase
    - Entfernt Rechtsformen (GmbH, AG, etc.)
    - Entfernt Sonderzeichen
    - Normalisiert Umlaute

    Args:
        name: Der zu normalisierende Name.

    Returns:
        Normalisierter Name.
    """
    if not name:
        return ""

    # Lowercase
    name = name.lower()

    # Umlaute normalisieren
    umlaut_map = {
        "ä": "ae", "ö": "oe", "ü": "ue",
        "ß": "ss"
    }
    for umlaut, replacement in umlaut_map.items():
        name = name.replace(umlaut, replacement)

    # Rechtsformen entfernen
    rechtsformen = [
        r"\bgmbh\b", r"\bag\b", r"\bkg\b", r"\bohg\b",
        r"\beg\b", r"\be\.?k\.?\b", r"\binh\.?\b",
        r"\b&\s*co\.?\b", r"\bco\.?\b", r"\bgbr\b",
        r"\bmbh\b", r"\bpartg\b", r"\bpartner\b",
        r"\bgesellschaft\b", r"\bcompany\b"
    ]
    for pattern in rechtsformen:
        name = re.sub(pattern, "", name, flags=re.IGNORECASE)

    # Sonderzeichen entfernen (außer Leerzeichen)
    name = re.sub(r"[^\w\s]", "", name)

    # Mehrfache Leerzeichen
    name = re.sub(r"\s+", " ", name)

    return name.strip()


def normalize_address(address: Optional[str]) -> str:
    """
    Normalisiert eine Adresse für Vergleiche.

    - Lowercase
    - Normalisiert Straßenabkürzungen
    - Entfernt Sonderzeichen
    - Normalisiert Umlaute

    Args:
        address: Die zu normalisierende Adresse.

    Returns:
        Normalisierte Adresse.
    """
    if not address:
        return ""

    # Lowercase
    address = address.lower()

    # Umlaute
    umlaut_map = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}
    for umlaut, replacement in umlaut_map.items():
        address = address.replace(umlaut, replacement)

    # Straßenabkürzungen normalisieren
    street_patterns = [
        (r"\bstr\.?\b", "strasse"),
        (r"\bstrasse\b", "strasse"),
        (r"\bpl\.?\b", "platz"),
        (r"\bweg\b", "weg"),
        (r"\ballee\b", "allee"),
    ]
    for pattern, replacement in street_patterns:
        address = re.sub(pattern, replacement, address)

    # Sonderzeichen
    address = re.sub(r"[^\w\s]", "", address)

    # Leerzeichen
    address = re.sub(r"\s+", " ", address)

    return address.strip()


def similarity_score(a: str, b: str) -> float:
    """
    Berechnet die Ähnlichkeit zwischen zwei Strings.

    Verwendet Levenshtein-Ratio (0.0 - 1.0).

    Args:
        a: Erster String.
        b: Zweiter String.

    Returns:
        Ähnlichkeitswert (0.0 = keine, 1.0 = identisch).
    """
    if not a or not b:
        return 0.0

    return levenshtein_ratio(a, b)


def is_phone_match(phone1: Optional[str], phone2: Optional[str]) -> Tuple[bool, float]:
    """
    Prüft ob zwei Telefonnummern identisch sind.

    Args:
        phone1: Erste Telefonnummer.
        phone2: Zweite Telefonnummer.

    Returns:
        Tuple (is_match, confidence).
    """
    if not phone1 or not phone2:
        return False, 0.0

    norm1 = normalize_phone(phone1)
    norm2 = normalize_phone(phone2)

    if not norm1 or not norm2:
        return False, 0.0

    # Exakte Übereinstimmung
    if norm1 == norm2:
        return True, 1.0

    # Teilweise Übereinstimmung (einer ist Teilstring)
    if norm1 in norm2 or norm2 in norm1:
        # Kürzere Nummer muss mindestens 6 Ziffern haben
        if min(len(norm1), len(norm2)) >= 6:
            return True, 0.9

    # Levenshtein für ähnliche Nummern (Tippfehler)
    similarity = similarity_score(norm1, norm2)
    if similarity >= 0.9:
        return True, similarity

    return False, similarity


def is_name_match(name1: Optional[str], name2: Optional[str], threshold: float = 0.85) -> Tuple[bool, float]:
    """
    Prüft ob zwei Firmennamen identisch sind.

    Args:
        name1: Erster Name.
        name2: Zweiter Name.
        threshold: Mindest-Ähnlichkeit für Match.

    Returns:
        Tuple (is_match, confidence).
    """
    if not name1 or not name2:
        return False, 0.0

    norm1 = normalize_name(name1)
    norm2 = normalize_name(name2)

    if not norm1 or not norm2:
        return False, 0.0

    # Exakte Übereinstimmung
    if norm1 == norm2:
        return True, 1.0

    # Levenshtein-Ähnlichkeit
    similarity = similarity_score(norm1, norm2)

    if similarity >= threshold:
        return True, similarity

    # Prüfe ob einer im anderen enthalten ist (für unterschiedliche Schreibweisen)
    if len(norm1) > 3 and len(norm2) > 3:
        if norm1 in norm2 or norm2 in norm1:
            return True, 0.85

    return False, similarity


def is_address_match(
    addr1: Optional[str],
    plz1: Optional[str],
    addr2: Optional[str],
    plz2: Optional[str],
    threshold: float = 0.8
) -> Tuple[bool, float]:
    """
    Prüft ob zwei Adressen identisch sind.

    PLZ-Match hat höchste Priorität.

    Args:
        addr1: Erste Adresse.
        plz1: Erste PLZ.
        addr2: Zweite Adresse.
        plz2: Zweite PLZ.
        threshold: Mindest-Ähnlichkeit.

    Returns:
        Tuple (is_match, confidence).
    """
    # PLZ-Vergleich (höchste Priorität)
    plz_match = False
    if plz1 and plz2:
        # Normalisiere PLZ
        plz1_clean = re.sub(r"\D", "", plz1)
        plz2_clean = re.sub(r"\D", "", plz2)
        plz_match = plz1_clean == plz2_clean

    # Keine PLZ verfügbar oder unterschiedlich
    if plz1 and plz2 and not plz_match:
        return False, 0.0

    # Adress-Vergleich
    if not addr1 or not addr2:
        # Nur PLZ-Match ohne Adresse
        if plz_match:
            return True, 0.7
        return False, 0.0

    norm1 = normalize_address(addr1)
    norm2 = normalize_address(addr2)

    if not norm1 or not norm2:
        if plz_match:
            return True, 0.7
        return False, 0.0

    similarity = similarity_score(norm1, norm2)

    # PLZ-Match erhöht Confidence
    if plz_match:
        # Mit PLZ-Match reicht niedrigere Adress-Ähnlichkeit
        if similarity >= 0.5:
            return True, min(1.0, similarity + 0.3)

    if similarity >= threshold:
        return True, similarity

    return False, similarity


def is_duplicate(
    lead_a: Lead,
    lead_b: Lead,
    phone_weight: float = 1.0,
    name_weight: float = 0.8,
    address_weight: float = 0.6,
    threshold: float = 0.85
) -> MatchResult:
    """
    Prüft ob zwei Leads Duplikate sind.

    Matching-Priorität:
    1. Telefonnummer (exakt = definitiv Match)
    2. Name + PLZ
    3. Name + Adresse

    Args:
        lead_a: Erster Lead.
        lead_b: Zweiter Lead.
        phone_weight: Gewichtung Telefon.
        name_weight: Gewichtung Name.
        address_weight: Gewichtung Adresse.
        threshold: Mindest-Score für Match.

    Returns:
        MatchResult mit Details.
    """
    match_reasons = []
    mismatch_reasons = []
    total_score = 0.0
    total_weight = 0.0

    # 1. Telefon-Vergleich (höchste Priorität)
    if lead_a.telefon and lead_b.telefon:
        phone_match, phone_conf = is_phone_match(lead_a.telefon, lead_b.telefon)
        if phone_match and phone_conf >= 0.95:
            # Exakter Telefon-Match = definitiv Duplikat
            return MatchResult(
                is_match=True,
                confidence=phone_conf,
                match_reasons=["phone_exact"],
                mismatch_reasons=[]
            )
        elif phone_match:
            match_reasons.append(f"phone ({phone_conf:.2f})")
            total_score += phone_conf * phone_weight
        else:
            mismatch_reasons.append("phone")

        total_weight += phone_weight

    # 2. Name-Vergleich
    name_match, name_conf = is_name_match(lead_a.firmenname, lead_b.firmenname)
    if name_match:
        match_reasons.append(f"name ({name_conf:.2f})")
        total_score += name_conf * name_weight
    else:
        mismatch_reasons.append("name")

    total_weight += name_weight

    # 3. Adress-Vergleich
    addr_a = lead_a.adresse.format_full() if lead_a.adresse else None
    addr_b = lead_b.adresse.format_full() if lead_b.adresse else None
    plz_a = lead_a.adresse.plz if lead_a.adresse else None
    plz_b = lead_b.adresse.plz if lead_b.adresse else None

    if addr_a or addr_b or plz_a or plz_b:
        addr_match, addr_conf = is_address_match(addr_a, plz_a, addr_b, plz_b)
        if addr_match:
            match_reasons.append(f"address ({addr_conf:.2f})")
            total_score += addr_conf * address_weight
        else:
            mismatch_reasons.append("address")

        total_weight += address_weight

    # Berechne Gesamt-Confidence
    if total_weight > 0:
        confidence = total_score / total_weight
    else:
        confidence = 0.0

    # Name + PLZ Match = wahrscheinlich Duplikat
    if name_match and plz_a and plz_b and plz_a == plz_b:
        confidence = max(confidence, 0.9)
        if "plz" not in str(match_reasons):
            match_reasons.append("plz_exact")

    is_match = confidence >= threshold

    return MatchResult(
        is_match=is_match,
        confidence=confidence,
        match_reasons=match_reasons,
        mismatch_reasons=mismatch_reasons
    )


def merge_leads(primary: Lead, secondary: Lead) -> Lead:
    """
    Merged zwei Leads zu einem.

    Primary-Lead hat Vorrang, Secondary ergänzt fehlende Daten.

    Args:
        primary: Primärer Lead (höhere Priorität).
        secondary: Sekundärer Lead (ergänzt Daten).

    Returns:
        Gemergter Lead.
    """
    from config.settings import DataSource

    # Kopiere Primary
    merged_data = primary.model_dump()

    # Ergänze fehlende Felder aus Secondary
    if not primary.telefon and secondary.telefon:
        merged_data["telefon"] = secondary.telefon

    if not primary.email and secondary.email:
        merged_data["email"] = secondary.email

    if not primary.website_url and secondary.website_url:
        merged_data["website_url"] = secondary.website_url

    if not primary.oeffnungszeiten and secondary.oeffnungszeiten:
        merged_data["oeffnungszeiten"] = secondary.oeffnungszeiten

    if not primary.bewertung and secondary.bewertung:
        merged_data["bewertung"] = secondary.bewertung
        merged_data["bewertung_anzahl"] = secondary.bewertung_anzahl

    # Adresse ergänzen
    if primary.adresse and secondary.adresse:
        if not primary.adresse.strasse and secondary.adresse.strasse:
            merged_data["adresse"]["strasse"] = secondary.adresse.strasse
        if not primary.adresse.hausnummer and secondary.adresse.hausnummer:
            merged_data["adresse"]["hausnummer"] = secondary.adresse.hausnummer
        if not primary.adresse.plz and secondary.adresse.plz:
            merged_data["adresse"]["plz"] = secondary.adresse.plz

    # Quellen kombinieren
    quellen = list(set(primary.quellen + secondary.quellen))
    merged_data["quellen"] = quellen

    # Google Maps Daten übernehmen
    if secondary.google_maps_place_id and not primary.google_maps_place_id:
        merged_data["google_maps_place_id"] = secondary.google_maps_place_id
        merged_data["google_maps_url"] = secondary.google_maps_url

    # Gelbe Seiten Daten übernehmen
    if secondary.gelbe_seiten_url and not primary.gelbe_seiten_url:
        merged_data["gelbe_seiten_url"] = secondary.gelbe_seiten_url
        merged_data["gelbe_seiten_id"] = secondary.gelbe_seiten_id

    return Lead(**merged_data)
