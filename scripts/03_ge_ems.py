"""
EMS Genève — capacité (lits) + localisation, format homogène avec Vaud.

Croise :
  - localisations : SITG (data/raw/ems_ge_sitg.geojson) — noms + coords
  - lits long séjour : PDF officiel SeSPA (data/raw/ems_geneve_2026.pdf)
Rattache chaque EMS à sa commune (point-dans-polygone) et écrit data/processed/ems_ge.csv
au même schéma que ems_vd.csv (nom_clean, type, lits, lat, lon, ofs, commune, geo_source).

Lancer depuis la racine du projet :
    python scripts/03_ge_ems.py
"""

import json
import re
import unicodedata
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pdfplumber
from shapely.geometry import Point, shape

SITG = Path("data/raw/ems_ge_sitg.geojson")
PDF = Path("data/raw/ems_geneve_2026.pdf")
COMMUNES = Path("data/processed/communes_vd.geojson")
OUT = Path("data/processed/ems_ge.csv")

RUE = re.compile(r"\b(Rue|Route|Chemin|Quai|Avenue|Av\.|Ch\.|Place|Impasse|Promenade|"
                 r"Sentier|Boulevard|Vy|Vieux|Cité|Clos|Champ)", re.I)


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    for stop in ["ems", "residence", "résidence", "foyer", "home", "la", "le", "les",
                 "de", "du", "des", "d", "l"]:
        s = re.sub(rf"\b{stop}\b", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def lits_depuis_pdf():
    """Parse le PDF -> dict {nom_normalisé: lits long séjour}."""
    texte = "\n".join((p.extract_text() or "") for p in pdfplumber.open(PDF).pages)
    lits, nom_courant = {}, None
    for ligne in texte.splitlines():
        if "(Tel.)" in ligne:                       # ligne d'en-tête d'un EMS
            avant = RUE.split(ligne, 1)[0]           # nom = avant le nom de rue
            nom_courant = norm(avant)
        m = re.search(r"(\d+)\s*lits?\s*LS", ligne)
        if m and nom_courant:
            lits[nom_courant] = int(m.group(1))
    return lits


def main():
    sitg = json.loads(SITG.read_text(encoding="utf-8"))
    lits = lits_depuis_pdf()
    print(f"Lits extraits du PDF : {len(lits)} EMS")

    # communes GE pour le rattachement
    geo = json.loads(COMMUNES.read_text(encoding="utf-8"))
    communes = gpd.GeoDataFrame(
        [{"ofs": f["properties"]["ofs"], "commune": f["properties"]["nom"],
          "geometry": shape(f["geometry"])} for f in geo["features"]], crs="EPSG:4326")

    rows = []
    for f in sitg["features"]:
        p = f["properties"]
        nom = p.get("NOM_EMS", "")
        lon, lat = f["geometry"]["coordinates"][:2]
        cle = norm(nom)
        # appariement des lits : nom normalisé, sinon inclusion partielle
        nb = lits.get(cle)
        if nb is None:
            for k, v in lits.items():
                if k and (k in cle or cle in k):
                    nb = v
                    break
        rows.append({"nom_clean": nom, "type": "EMS", "lits": nb,
                     "lat": lat, "lon": lon, "geo_source": "SITG"})

    df = pd.DataFrame(rows)
    # rattachement commune par point-dans-polygone
    pts = gpd.GeoDataFrame(df, geometry=[Point(xy) for xy in zip(df["lon"], df["lat"])],
                           crs="EPSG:4326")
    j = gpd.sjoin(pts.to_crs(2056), communes.to_crs(2056), how="left")
    j = j[~j.index.duplicated(keep="first")]
    df["ofs"] = j["ofs"].values
    df["commune"] = j["commune"].values

    OUT.write_text(df.to_csv(index=False), encoding="utf-8")
    n_lits = int(df["lits"].notna().sum())
    print(f"✅ {len(df)} EMS Genève écrits dans {OUT}")
    print(f"   avec lits appariés : {n_lits}/{len(df)} · "
          f"total lits : {df['lits'].sum():.0f} · rattachés commune : {df['ofs'].notna().sum()}")
    manq = df[df["lits"].isna()]["nom_clean"].tolist()
    if manq:
        print(f"   sans lits (à vérifier) : {manq[:8]}")


if __name__ == "__main__":
    main()
