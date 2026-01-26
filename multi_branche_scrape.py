#!/usr/bin/env python3
"""Scraped mehrere Branchen bis 300 Leads erreicht sind."""

import subprocess
import json
import sys
from pathlib import Path

# Branchen die Online-Branding verstehen (kein Handwerk, keine Kosmetik)
BRANCHEN = [
    "Friseur",
    "Restaurant", 
    "Café",
    "Fitnessstudio",
    "Fotograf",
    "Physiotherapie",
    "Nagelstudio",
    "Yoga",
    "Massage",
    "Tattoo",
]

TARGET_LEADS = 300
all_leads = []
stadt = "Essen"

print(f"Ziel: {TARGET_LEADS} Leads aus {stadt}")
print("=" * 50)

for branche in BRANCHEN:
    if len(all_leads) >= TARGET_LEADS:
        break
    
    print(f"\n>>> Scrape: {branche}")
    
    # Nur Gelbe Seiten, kein Stealth (schneller)
    cmd = [
        "python3", "main.py",
        "-b", branche,
        "-s", stadt,
        "--sources", "gelbe-seiten",
        "--format", "json",
        "-l", "100",
        "-q"  # quiet
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # Lade die Ergebnisse
    output_file = Path(f"leads_{branche.lower().replace(' ', '_').replace('é', 'e')}_{stadt.lower()}.json")
    
    if output_file.exists():
        with open(output_file) as f:
            data = json.load(f)
            new_leads = data.get("leads", [])
            print(f"    Gefunden: {len(new_leads)} Leads")
            
            # Füge Branche hinzu für Tracking
            for lead in new_leads:
                lead["such_branche"] = branche
            
            all_leads.extend(new_leads)
            print(f"    Gesamt: {len(all_leads)} Leads")
    else:
        print(f"    Keine Ergebnisse")

# Exportiere kombinierte Liste
print("\n" + "=" * 50)
print(f"FERTIG: {len(all_leads)} Leads gesammelt")

output = {
    "meta": {
        "stadt": stadt,
        "branchen": BRANCHEN[:len(all_leads)//50 + 1],
        "anzahl_leads": len(all_leads),
        "ziel": TARGET_LEADS
    },
    "leads": all_leads
}

with open("leads_multi_essen_300.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2, default=str)

# CSV Export
import csv
with open("leads_multi_essen_300.csv", "w", encoding="utf-8", newline="") as f:
    if all_leads:
        writer = csv.DictWriter(f, fieldnames=all_leads[0].keys(), delimiter=";")
        writer.writeheader()
        writer.writerows(all_leads)

print(f"\nExportiert:")
print(f"  → leads_multi_essen_300.json")
print(f"  → leads_multi_essen_300.csv")
