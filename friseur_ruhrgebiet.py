#!/usr/bin/env python3
"""300 Friseur-Leads aus dem Ruhrgebiet (Gelbe Seiten)"""

import subprocess
import json
from pathlib import Path

# Städte im Ruhrgebiet rund um Essen
STAEDTE = [
    "Essen",
    "Mülheim an der Ruhr", 
    "Oberhausen",
    "Bochum",
    "Gelsenkirchen",
    "Duisburg",
    "Bottrop",
    "Herne",
]

TARGET = 300
all_leads = []
branche = "Friseur"

print(f"Ziel: {TARGET} {branche}-Leads aus dem Ruhrgebiet")
print("=" * 50)

for stadt in STAEDTE:
    if len(all_leads) >= TARGET:
        break
    
    print(f"\n>>> {stadt}...")
    
    cmd = [
        "python3", "main.py",
        "-b", branche,
        "-s", stadt,
        "--sources", "gelbe-seiten",
        "--format", "json",
        "-l", "100",
        "-q"
    ]
    
    subprocess.run(cmd, capture_output=True, text=True)
    
    # Lade Ergebnisse
    stadt_safe = stadt.lower().replace(" ", "_").replace("ü", "u")
    output_file = Path(f"leads_friseur_{stadt_safe}.json")
    
    if output_file.exists():
        with open(output_file) as f:
            data = json.load(f)
            new_leads = data.get("leads", [])
            
            # Stadt-Tag hinzufügen
            for lead in new_leads:
                lead["such_stadt"] = stadt
            
            all_leads.extend(new_leads)
            print(f"    +{len(new_leads)} Leads (Gesamt: {len(all_leads)})")
    else:
        print(f"    Keine Ergebnisse")

print("\n" + "=" * 50)
print(f"GELBE SEITEN FERTIG: {len(all_leads)} Friseur-Leads")

# Export
output = {
    "meta": {
        "branche": branche,
        "region": "Ruhrgebiet",
        "staedte": STAEDTE,
        "quelle": "gelbe_seiten",
        "anzahl": len(all_leads)
    },
    "leads": all_leads
}

with open("leads_friseur_ruhrgebiet_gs.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2, default=str)

import csv
with open("leads_friseur_ruhrgebiet_gs.csv", "w", encoding="utf-8", newline="") as f:
    if all_leads:
        # Flatten nested dicts for CSV
        flat_leads = []
        for lead in all_leads:
            flat = {}
            for k, v in lead.items():
                if isinstance(v, dict):
                    for k2, v2 in v.items():
                        flat[f"{k}_{k2}"] = v2
                elif isinstance(v, list):
                    flat[k] = ", ".join(str(x) for x in v)
                else:
                    flat[k] = v
            flat_leads.append(flat)
        
        writer = csv.DictWriter(f, fieldnames=flat_leads[0].keys(), delimiter=";")
        writer.writeheader()
        writer.writerows(flat_leads)

print(f"\nExportiert:")
print(f"  → leads_friseur_ruhrgebiet_gs.json")
print(f"  → leads_friseur_ruhrgebiet_gs.csv")
