"""
Étape 4 (amont) — Coefficient d'impôt communal par commune vaudoise.

Source : État de Vaud, "Arrêtés d'imposition 2026" (vd.ch)
  data/raw/coefficients_impot_communes_2026.xls

Le coefficient communal ("Pour-cent total", en % de l'impôt cantonal de base)
mesure la charge fiscale : plus il est élevé, plus le pouvoir d'achat NET baisse.

Sortie : data/processed/coefficients_vd.csv  (ofs, nom, coefficient)

Lancer depuis la racine du projet :
    python scripts/04b_parse_coefficients.py
"""

import json
import re
import unicodedata
from pathlib import Path

import pandas as pd

XLS = Path("data/raw/coefficients_impot_communes_2026.xls")
COMMUNES = Path("data/processed/communes_vd.geojson")
OUT = Path("data/processed/coefficients_vd.csv")


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\(vd\)", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def main():
    geo = json.loads(COMMUNES.read_text(encoding="utf-8"))
    par_nom = {norm(f["properties"]["nom"]): (f["properties"]["ofs"],
               f["properties"]["nom"]) for f in geo["features"]}

    raw = pd.read_excel(XLS, sheet_name=0, header=None)
    rows = []
    for _, r in raw.iterrows():
        nom = r[0]
        coeff = r[5] if pd.notna(r[5]) else r[3]   # "Pour-cent total", sinon revenu/fortune
        if not isinstance(nom, str):
            continue
        cle = norm(nom)
        if cle not in par_nom:                      # ignore en-têtes district, lignes vides
            continue
        try:
            coeff = float(str(coeff).replace(",", "."))
        except (ValueError, TypeError):
            continue
        ofs, nom_off = par_nom[cle]
        rows.append({"ofs": ofs, "nom": nom_off, "coefficient": coeff})

    df = pd.DataFrame(rows).drop_duplicates("ofs")
    OUT.write_text(df.to_csv(index=False), encoding="utf-8")
    print(f"✅ {len(df)} communes écrites dans {OUT}")
    print(f"   Coefficient : min {df['coefficient'].min()}, "
          f"médian {df['coefficient'].median()}, max {df['coefficient'].max()}")
    print("\nLes 5 communes les MOINS taxées (coefficient le plus bas) :")
    for _, r in df.nsmallest(5, "coefficient").iterrows():
        print(f"   {r['nom']:28} {r['coefficient']}")


if __name__ == "__main__":
    main()
