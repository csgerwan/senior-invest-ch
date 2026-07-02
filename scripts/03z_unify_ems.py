"""
Unifie les EMS des trois cantons (VD + GE + FR) en un seul fichier homogène.

Entrées : data/processed/ems_vd.csv, ems_ge.csv, ems_fr.csv
Sortie   : data/processed/ems.csv
  colonnes : canton, nom_clean, type, lits, lat, lon, ofs, commune, geo_source

Lancer depuis la racine du projet :
    python scripts/03z_unify_ems.py
"""

from pathlib import Path

import pandas as pd

COLS = ["nom_clean", "type", "lits", "lat", "lon", "ofs", "commune", "geo_source"]
SRC = {"Vaud": "ems_vd.csv", "Genève": "ems_ge.csv", "Fribourg": "ems_fr.csv"}
PROC = Path("data/processed")
OUT = PROC / "ems.csv"


def main():
    parts = []
    for canton, fichier in SRC.items():
        d = pd.read_csv(PROC / fichier)
        d = d[[c for c in COLS if c in d.columns]].copy()
        d.insert(0, "canton", canton)
        parts.append(d)
        print(f"  {canton:9} : {len(d):3} EMS · {int(d['lits'].fillna(0).sum()):5} lits")
    df = pd.concat(parts, ignore_index=True)
    df["ofs"] = df["ofs"].astype("Int64").astype(str).replace("<NA>", "")
    OUT.write_text(df.to_csv(index=False), encoding="utf-8")
    print(f"✅ {len(df)} EMS écrits dans {OUT} · total {int(df['lits'].fillna(0).sum())} lits · "
          f"{df['commune'].nunique()} communes")


if __name__ == "__main__":
    main()
