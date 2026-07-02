"""
Étape 6 — Score d'opportunité d'investissement par commune (V1).

Croise TOUTES les données en 4 sous-scores normalisés (0-100), pondérables en
direct dans l'app. Une commune est d'autant plus intéressante que :
  1. demande      : la PART de seniors (80+) est élevée
  2. eloignement  : elle est LOIN de l'EMS le plus proche (zone mal desservie)
  3. pouvoir_achat: le pouvoir d'achat est élevé (capacité à payer)
  4. prix_bas     : le prix immobilier au m² est bas (foncier abordable)

Sortie : data/processed/score_opportunite_vd.csv (sous-scores + valeurs brutes).

Lancer depuis la racine du projet :
    python scripts/06_build_score.py
"""

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, shape

ROOT = Path(".")
GEO = ROOT / "data/processed/communes_vd.geojson"
DEMO = ROOT / "data/processed/demographie_vd.csv"
EMS = ROOT / "data/processed/ems.csv"  # unifié VD+GE+FR
PA = ROOT / "data/processed/pouvoir_achat_vd.csv"
IMMO = ROOT / "data/processed/immobilier_vd.csv"
OUT = ROOT / "data/processed/score_opportunite_vd.csv"


def minmax(s):
    lo, hi = s.min(), s.max()
    return (s - lo) / (hi - lo) * 100 if hi > lo else s * 0 + 50


def main():
    geo = json.loads(GEO.read_text(encoding="utf-8"))
    communes = gpd.GeoDataFrame(
        [{"ofs": f["properties"]["ofs"], "nom": f["properties"]["nom"],
          "district": f["properties"]["district"], "geometry": shape(f["geometry"])}
         for f in geo["features"]], crs="EPSG:4326").to_crs(2056)
    communes["cx"] = communes.geometry.centroid.x
    communes["cy"] = communes.geometry.centroid.y

    demo = pd.read_csv(DEMO, dtype={"ofs": str})
    ems_all = pd.read_csv(EMS, dtype={"ofs": str})           # tous (pour lits/district)
    ems = ems_all.dropna(subset=["lat", "lon"])              # géolocalisés (pour distance)
    pa = pd.read_csv(PA, dtype={"ofs": str})[["ofs", "indice_pouvoir_achat"]]
    immo = pd.read_csv(IMMO, dtype={"ofs": str})[["ofs", "prix_m2_appart", "fiabilite"]]

    # Distance (km) de chaque centroïde communal à l'EMS le plus proche
    ems_pts = gpd.GeoSeries(
        [Point(xy) for xy in zip(ems["lon"], ems["lat"])], crs="EPSG:4326").to_crs(2056)
    ems_xy = list(zip(ems_pts.x, ems_pts.y))
    def dist_min_km(row):
        return min(((row["cx"] - x) ** 2 + (row["cy"] - y) ** 2) ** 0.5
                   for x, y in ems_xy) / 1000
    communes["dist_ems_km"] = communes.apply(dist_min_km, axis=1).round(2)

    df = (communes[["ofs", "nom", "district", "dist_ems_km"]]
          .merge(demo[["ofs", "pop_totale", "pop_80plus", "part_80plus"]], on="ofs", how="left")
          .merge(pa, on="ofs", how="left")
          .merge(immo, on="ofs", how="left")
          .rename(columns={"fiabilite": "prix_fiabilite"}))

    # Saturation EMS au niveau district : lits pour 100 personnes de 80+
    lits_dist = (ems_all.dropna(subset=["ofs"]).merge(df[["ofs", "district"]], on="ofs", how="left")
                 .groupby("district")["lits"].sum())
    pop80_dist = df.groupby("district")["pop_80plus"].sum()
    lits_pour_100 = (lits_dist / pop80_dist * 100).rename("lits_pour_100_district")
    df = df.merge(lits_pour_100, on="district", how="left")
    df["lits_pour_100_district"] = df["lits_pour_100_district"].fillna(0).round(1)

    # Sous-scores 0-100
    df["demande_score"] = minmax(df["part_80plus"]).round(1)              # 1. part seniors
    # 2. TENSION de la zone : saturation district (75%) + éloignement réduit (25%)
    saturation = 100 - minmax(df["lits_pour_100_district"])
    eloignement = minmax(df["dist_ems_km"])
    df["tension_score"] = (0.75 * saturation + 0.25 * eloignement).round(1)
    df["pouvoir_achat_score"] = df["indice_pouvoir_achat"].round(1)      # 3. pouvoir d'achat
    df["prix_bas_score"] = (100 - minmax(df["prix_m2_appart"])).round(1)  # 4. prix bas

    OUT.write_text(df.to_csv(index=False), encoding="utf-8")
    print(f"✅ {len(df)} communes écrites dans {OUT}")

    # Aperçu (poids égaux 25/25/25/25)
    w = {"demande_score": .25, "tension_score": .25,
         "pouvoir_achat_score": .25, "prix_bas_score": .25}
    def sc(r):
        parts = {k: r[k] for k in w if pd.notna(r[k])}
        tot = sum(w[k] for k in parts)
        return round(sum(r[k] * w[k] for k in parts) / tot, 1) if tot else None
    df["score"] = df.apply(sc, axis=1)
    top = df[df["pop_totale"] >= 1500].dropna(subset=["score"]).nlargest(12, "score")
    print("\n🏆 Top 12 (poids égaux, communes ≥ 1500 hab.) :")
    for _, r in top.iterrows():
        print(f"   {r['nom']:22} {r['score']:>5}  | 80+ {r['part_80plus']:.1f}%  "
              f"EMS {r['dist_ems_km']:>4} km  PA {r['pouvoir_achat_score']:>4}  "
              f"prix {r['prix_m2_appart']:.0f}")


if __name__ == "__main__":
    main()
