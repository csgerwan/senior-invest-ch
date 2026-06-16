"""
V2 — Données du radar « Évaluation d'un bien » (zone verte : qualification demande).

Calcule, par commune, les 3 notes sur 0-5 de la zone verte du radar investisseur :
  1. Pouvoir d'achat senior      = indice pouvoir d'achat (étape 4) / 20
  2. Population senior de la zone = somme des 80+ dans un BASSIN de RAYON_KM autour
     de la commune (échelle logarithmique) -> 0-5  [moins sensible aux extrêmes]
  3. Proximité & saturation EMS   = TENSION : zones mal couvertes (saturation du
     district vu la pop. senior, en priorité, + éloignement de l'EMS le plus proche)

Réutilise les sorties existantes (score, démographie, EMS, immobilier).
Sortie : data/processed/radar_vd.csv

Lancer depuis la racine du projet :
    python scripts/07_build_radar.py
"""

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import shape

P = Path("data/processed")
GEO = P / "communes_vd.geojson"
OUT = P / "radar_vd.csv"
RAYON_KM = 10  # rayon du bassin de captation pour la population senior de la zone


def minmax(s):
    lo, hi = s.min(), s.max()
    return (s - lo) / (hi - lo) * 100 if hi > lo else s * 0 + 50


def population_zone(df):
    """Somme des 80+ dans un rayon RAYON_KM autour du centre de chaque commune."""
    cent = gpd.GeoDataFrame(
        [{"ofs": f["properties"]["ofs"], "geometry": shape(f["geometry"])}
         for f in json.loads(GEO.read_text(encoding="utf-8"))["features"]],
        crs="EPSG:4326").to_crs(2056)
    cent["x"], cent["y"] = cent.geometry.centroid.x, cent.geometry.centroid.y
    cent = cent.merge(df[["ofs", "pop_80plus"]], on="ofs", how="left")
    xs, ys, pops = cent["x"].values, cent["y"].values, cent["pop_80plus"].fillna(0).values
    rayon_m = RAYON_KM * 1000
    zone = []
    for i in range(len(cent)):
        d = ((xs - xs[i]) ** 2 + (ys - ys[i]) ** 2) ** 0.5
        zone.append(pops[d <= rayon_m].sum())
    cent["pop_zone_80plus"] = zone
    return df.merge(cent[["ofs", "pop_zone_80plus"]], on="ofs", how="left")


def minmax(s):
    lo, hi = s.min(), s.max()
    return (s - lo) / (hi - lo) * 100 if hi > lo else s * 0 + 50


def main():
    score = pd.read_csv(P / "score_opportunite_vd.csv", dtype={"ofs": str})

    # tension_score et lits_pour_100_district sont déjà calculés par le script 06
    df = score[["ofs", "nom", "district", "dist_ems_km", "pop_80plus",
                "part_80plus", "indice_pouvoir_achat", "prix_m2_appart",
                "prix_fiabilite", "lits_pour_100_district", "tension_score"]].copy()

    # --- Notes 0-5 de la zone verte ---
    df["note_pouvoir_achat"] = (df["indice_pouvoir_achat"] / 20).round(2)
    # Population senior DE LA ZONE : bassin de RAYON_KM + échelle log (moins sensible)
    df = population_zone(df)
    df["note_population"] = (minmax(np.log1p(df["pop_zone_80plus"])) / 20).round(2)
    # tension EMS : reprend exactement le sous-score du score (06) -> cohérence
    df["note_tension_ems"] = (df["tension_score"] / 20).round(2)

    df["pop_zone_80plus"] = df["pop_zone_80plus"].round().astype(int)
    cols = ["ofs", "nom", "district",
            "note_pouvoir_achat", "note_population", "note_tension_ems",
            "indice_pouvoir_achat", "pop_80plus", "pop_zone_80plus", "part_80plus",
            "dist_ems_km", "lits_pour_100_district",
            "prix_m2_appart", "prix_fiabilite"]
    df[cols].to_csv(OUT, index=False)
    print(f"✅ {len(df)} communes écrites dans {OUT} (bassin {RAYON_KM} km)")
    print("\nExemples — note population (bassin) :")
    for nom in ["Lausanne", "Yverdon-les-Bains", "Nyon", "Morges", "Begnins", "Aigle"]:
        r = df[df["nom"] == nom]
        if len(r):
            r = r.iloc[0]
            print(f"   {nom:20} commune {int(r['pop_80plus']):>5} 80+ | "
                  f"zone {int(r['pop_zone_80plus']):>5} 80+ -> note {r['note_population']:.1f}/5")


if __name__ == "__main__":
    main()
