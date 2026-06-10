"""
Étape 5 — Immobilier : prix indicatif au m² sur une short-list de communes.

⚠️ Les prix de transaction par commune ne sont PAS en open data en Suisse.
Ces prix au m² sont des ESTIMATIONS INDICATIVES (appartements) collectées via
recherche web sur des portails (RealAdvisor, Neho, Comparis...), millésime ~2025.
Source éditable : data/raw/prix_m2_manuel.csv (complète/corrige à volonté).

Joint les prix aux communes + contexte (seniors 80+, pouvoir d'achat).
Sortie : data/processed/immobilier_vd.csv

Lancer depuis la racine du projet :
    python scripts/04d_build_immobilier.py
"""

import json
import re
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(".")
GEO = ROOT / "data/processed/communes_vd.geojson"
PRIX = ROOT / "data/raw/prix_m2_manuel.csv"
DEMO = ROOT / "data/processed/demographie_vd.csv"
PA = ROOT / "data/processed/pouvoir_achat_vd.csv"
OUT = ROOT / "data/processed/immobilier_vd.csv"


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\(vd\)", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def main():
    geo = json.loads(GEO.read_text(encoding="utf-8"))
    par_nom = {norm(f["properties"]["nom"]): (f["properties"]["ofs"],
               f["properties"]["nom"], f["properties"]["district"])
               for f in geo["features"]}

    prix = pd.read_csv(PRIX)
    rows, manquants = [], []
    for _, r in prix.iterrows():
        cle = norm(r["commune"])
        if cle not in par_nom:
            manquants.append(r["commune"])
            continue
        ofs, nom, district = par_nom[cle]
        rows.append({
            "ofs": ofs, "nom": nom, "district": district,
            "prix_m2_appart": r["prix_m2_appart"] if pd.notna(r["prix_m2_appart"]) else None,
            "prix_source": r["source"], "prix_date": r["date"],
        })

    df = pd.DataFrame(rows)
    demo = pd.read_csv(DEMO, dtype={"ofs": str})[["ofs", "pop_80plus", "part_80plus"]]
    pa = pd.read_csv(PA, dtype={"ofs": str})[["ofs", "indice_pouvoir_achat", "revenu_median_est"]]
    df = df.merge(demo, on="ofs", how="left").merge(pa, on="ofs", how="left")
    df = df.sort_values("prix_m2_appart", ascending=False, na_position="last")

    OUT.write_text(df.to_csv(index=False), encoding="utf-8")
    avec = df["prix_m2_appart"].notna().sum()
    print(f"✅ {len(df)} communes écrites dans {OUT} ({avec} avec prix)")
    if manquants:
        print("⚠️ Non rattachées (nom à corriger dans le CSV) :", manquants)
    print("\nPrix au m² (appartements, indicatif 2025) :")
    for _, r in df[df["prix_m2_appart"].notna()].iterrows():
        print(f"   {r['nom']:24} {r['prix_m2_appart']:>7,.0f} CHF/m²  "
              f"(80+ : {int(r['pop_80plus'])}, pouvoir d'achat {r['indice_pouvoir_achat']})"
              .replace(",", "'"))


if __name__ == "__main__":
    main()
