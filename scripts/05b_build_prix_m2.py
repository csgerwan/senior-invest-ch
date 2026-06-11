"""
Étape 5 (v2) — Prix au m² par commune à partir des annonces Homegate (Apify).

Entrée : data/raw/homegate_vd_raw.json (annonces VD à l'achat)
Traitements :
  - rattachement de chaque annonce à sa commune par GPS (point-dans-polygone)
    [le champ 'canton'/'city' de l'actor est peu fiable, le GPS l'est]
  - extraction de la surface habitable depuis titre + description (gratuit)
  - prix/m² = prix / surface, filtré dans une fourchette plausible
  - agrégation par commune : prix/m² moyen et médian, nombre d'annonces

Sortie : data/processed/prix_m2_immo_vd.csv

Lancer depuis la racine du projet :
    python scripts/05b_build_prix_m2.py
"""

import json
import re
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, shape

RAW = Path("data/raw/homegate_vd_raw.json")
GEO = Path("data/processed/communes_vd.geojson")
OUT = Path("data/processed/prix_m2_immo_vd.csv")

PRIX_M2_MIN, PRIX_M2_MAX = 3000, 30000  # fourchette plausible CHF/m² (VD)


def extraire_surface(it):
    """Surface habitable (m²) depuis titre + description, en évitant
    terrasse/balcon/jardin/terrain. None si rien de plausible."""
    txt = " ".join(str(it.get(k, "")) for k in ("title", "description"))
    cands = []
    for m in re.finditer(r"(\d{2,4})\s*m[2²]", txt):
        ctx = txt[max(0, m.start() - 28):m.start()].lower()
        if any(w in ctx for w in ("terrass", "balcon", "jardin", "garten",
                                  "parcell", "terrain", "cave", "garage")):
            continue
        v = int(m.group(1))
        if 20 <= v <= 400:
            cands.append(v)
    if not cands:
        return None
    # surface habitable = la plus grande valeur plausible mentionnée
    surface = max(cands)
    # garde-fou via le nombre de pièces (≈ 20-60 m²/pièce)
    rooms = it.get("rooms")
    if rooms and not (rooms * 12 <= surface <= rooms * 70):
        return None
    return surface


def main():
    listings = json.loads(RAW.read_text(encoding="utf-8"))
    geo = json.loads(GEO.read_text(encoding="utf-8"))
    communes = gpd.GeoDataFrame(
        [{"ofs": f["properties"]["ofs"], "nom": f["properties"]["nom"],
          "geometry": shape(f["geometry"])} for f in geo["features"]],
        crs="EPSG:4326")

    # Ratio médian m²/pièce (sur les annonces ayant surface ET pièces) -> imputation
    ratios = [extraire_surface(it) / it["rooms"]
              for it in listings
              if it.get("rooms") and extraire_surface(it)]
    m2_par_piece = pd.Series(ratios).median() if ratios else 25.0
    print(f"Ratio médian m²/pièce (imputation) : {m2_par_piece:.1f}")

    rows = []
    for it in listings:
        lat, lon, price = it.get("latitude"), it.get("longitude"), it.get("price")
        if not (lat and lon and price):
            continue
        surface = extraire_surface(it)
        reelle = surface is not None
        if not surface and it.get("rooms"):           # imputation via nb de pièces
            surface = it["rooms"] * m2_par_piece
        if not surface:
            continue
        pm2 = price / surface
        if not (PRIX_M2_MIN <= pm2 <= PRIX_M2_MAX):
            continue
        rows.append({"lat": lat, "lon": lon, "prix_m2": pm2, "reelle": reelle})

    df = pd.DataFrame(rows)
    print(f"Annonces exploitables : {len(df)} "
          f"(surface réelle {df['reelle'].sum()}, imputée {(~df['reelle']).sum()})")

    pts = gpd.GeoDataFrame(df, geometry=[Point(xy) for xy in zip(df["lon"], df["lat"])],
                           crs="EPSG:4326")
    j = gpd.sjoin(pts.to_crs(2056), communes.to_crs(2056), how="left", predicate="within")
    j = j.dropna(subset=["ofs"])

    agg = j.groupby(["ofs", "nom"]).agg(
        prix_m2_moyen=("prix_m2", "mean"),
        prix_m2_median=("prix_m2", "median"),
        n_annonces=("prix_m2", "size"),
        n_reelles=("reelle", "sum")).reset_index()
    agg["prix_m2_moyen"] = agg["prix_m2_moyen"].round(0)
    agg["prix_m2_median"] = agg["prix_m2_median"].round(0)

    def fiab(r):
        if r["n_reelles"] >= 5:
            return "solide (5+)"
        if r["n_reelles"] >= 1:
            return "indicative (1-4)"
        return "annonces (surface estimée)"
    agg["fiabilite"] = agg.apply(fiab, axis=1)
    agg = agg.sort_values("n_annonces", ascending=False)

    OUT.write_text(agg.to_csv(index=False), encoding="utf-8")
    print(f"✅ {len(agg)} communes avec prix/m² écrites dans {OUT}")
    print(f"   Annonces rattachées : {len(j)} | communes couvertes : {agg['ofs'].nunique()}")
    print("\nTop communes par nombre d'annonces :")
    for _, r in agg.head(12).iterrows():
        print(f"   {r['nom']:24} {r['prix_m2_moyen']:>7,.0f} CHF/m² moyen  "
              f"(médian {r['prix_m2_median']:,.0f}, n={r['n_annonces']})".replace(",", "'"))


if __name__ == "__main__":
    main()
