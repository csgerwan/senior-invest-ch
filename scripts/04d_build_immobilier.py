"""
Étape 5 — Immobilier : prix au m² par commune (intégration).

Fusionne, par ordre de priorité :
  1. Prix RÉELS issus des annonces Homegate via Apify (data/processed/prix_m2_immo_vd.csv)
     -> 147 communes, prix moyen + médian + nb d'annonces (cf. scripts 05/05b)
  2. Prix indicatifs manuels (data/raw/prix_m2_manuel.csv) en secours pour les
     communes non couvertes par Apify.

Joint le tout aux communes + contexte (seniors 80+, pouvoir d'achat).
Sortie : data/processed/immobilier_vd.csv

Lancer depuis la racine du projet :
    python scripts/04d_build_immobilier.py
"""

import json
import re
import unicodedata
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import shape

ROOT = Path(".")
GEO = ROOT / "data/processed/communes_vd.geojson"
APIFY = ROOT / "data/processed/prix_m2_immo_vd.csv"
MANUEL = ROOT / "data/raw/prix_m2_manuel.csv"
DEMO = ROOT / "data/processed/demographie_vd.csv"
PA = ROOT / "data/processed/pouvoir_achat_vd.csv"
OUT = ROOT / "data/processed/immobilier_vd.csv"


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\(vd\)", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def main():
    geo = json.loads(GEO.read_text(encoding="utf-8"))
    base = pd.DataFrame([{"ofs": f["properties"]["ofs"], "nom": f["properties"]["nom"],
                          "district": f["properties"]["district"]} for f in geo["features"]])

    # 1. Prix réels Apify (prioritaire) — on retient le prix MOYEN comme demandé
    apify = pd.read_csv(APIFY, dtype={"ofs": str})
    apify = apify.rename(columns={"prix_m2_moyen": "prix_m2_appart"})
    apify["prix_source"] = "Homegate/Apify (annonces réelles)"
    apify["prix_date"] = 2026
    apify = apify[["ofs", "prix_m2_appart", "prix_m2_median", "n_annonces",
                   "fiabilite", "prix_source", "prix_date"]]

    # 2. Manuel (secours) pour communes non couvertes par Apify
    man = pd.read_csv(MANUEL).rename(columns={"date": "prix_date"})
    par_nom = {norm(f["properties"]["nom"]): f["properties"]["ofs"] for f in geo["features"]}
    man["ofs"] = man["commune"].map(lambda c: par_nom.get(norm(c)))
    man = man.dropna(subset=["ofs", "prix_m2_appart"])
    man = man[~man["ofs"].isin(apify["ofs"])]
    man = man.assign(prix_m2_median=pd.NA, n_annonces=pd.NA, fiabilite="indicatif (web)",
                     prix_source="estimations portails (recherche web)")[
        ["ofs", "prix_m2_appart", "prix_m2_median", "n_annonces", "fiabilite",
         "prix_source", "prix_date"]]

    prix = pd.concat([apify, man], ignore_index=True)

    demo = pd.read_csv(DEMO, dtype={"ofs": str})[["ofs", "pop_80plus", "part_80plus"]]
    pa = pd.read_csv(PA, dtype={"ofs": str})[["ofs", "indice_pouvoir_achat", "revenu_median_est"]]
    df = (base.merge(prix, on="ofs", how="left")
              .merge(demo, on="ofs", how="left").merge(pa, on="ofs", how="left"))

    # 3. Estimation par voisinage pour les communes sans prix (annonces + manuel)
    cent = gpd.GeoDataFrame(
        [{"ofs": f["properties"]["ofs"], "geometry": shape(f["geometry"])}
         for f in geo["features"]], crs="EPSG:4326").to_crs(2056)
    cent["x"] = cent.geometry.centroid.x
    cent["y"] = cent.geometry.centroid.y
    xy = dict(zip(cent["ofs"], zip(cent["x"], cent["y"])))

    connus = df[df["prix_m2_appart"].notna()][["ofs", "prix_m2_appart"]].copy()
    connus["x"] = connus["ofs"].map(lambda o: xy[o][0])
    connus["y"] = connus["ofs"].map(lambda o: xy[o][1])

    K = 3  # nombre de communes proches utilisées pour l'estimation
    for i in df[df["prix_m2_appart"].isna()].index:
        ox, oy = xy[df.at[i, "ofs"]]
        d2 = (connus["x"] - ox) ** 2 + (connus["y"] - oy) ** 2
        proches = connus.loc[d2.nsmallest(K).index, "prix_m2_appart"]
        df.at[i, "prix_m2_appart"] = round(proches.median())
        df.at[i, "prix_source"] = "estimé (voisinage, communes proches)"
        df.at[i, "fiabilite"] = "estimé (voisinage)"

    df = df.sort_values("prix_m2_appart", ascending=False, na_position="last")
    OUT.write_text(df.to_csv(index=False), encoding="utf-8")

    avec = df["prix_m2_appart"].notna().sum()
    reels = df["prix_source"].eq("Homegate/Apify (annonces réelles)").sum()
    estimes = df["prix_source"].eq("estimé (voisinage, communes proches)").sum()
    print(f"✅ {len(df)} communes écrites dans {OUT}")
    print(f"   Avec prix/m² : {avec}  (annonces {reels}, voisinage {estimes}, "
          f"web {avec - reels - estimes})")


if __name__ == "__main__":
    main()
