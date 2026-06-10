"""
Étape 3 — Constitution de la couche EMS (établissements médico-sociaux) du canton de Vaud.

SOURCE DES DONNÉES (par ordre de priorité) :
  1. Fichier officiel si présent : data/raw/ems_vd_source.csv
     Colonnes attendues (au minimum) : nom, npa, commune, lits
     Colonnes optionnelles : adresse, lat, lon
     -> C'est LA source à privilégier (liste DGS/canton avec nombre de lits).
  2. À défaut : OpenStreetMap via l'API Overpass (gratuit, reproductible,
     mais couverture partielle et sans nombre de lits).

Traitements :
  - géocodage des adresses manquantes via l'API officielle geo.admin (SearchServer)
  - rattachement de chaque EMS à sa commune par localisation (point-dans-polygone)
  - écriture de data/processed/ems_vd.csv

Lancer depuis la racine du projet :
    python scripts/03_fetch_ems_vd.py
"""

import json
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point, shape

ROOT = Path(".")
SOURCE_OFFICIELLE = ROOT / "data/raw/ems_vd_source.csv"
GEOJSON_COMMUNES = ROOT / "data/processed/communes_vd.geojson"
OUT = ROOT / "data/processed/ems_vd.csv"

UA = {"User-Agent": "senior-invest-ch/1.0 (projet stage)"}


# --------------------------------------------------------------------------- #
# 1. Récupération des EMS
# --------------------------------------------------------------------------- #
def depuis_fichier_officiel() -> pd.DataFrame:
    df = pd.read_csv(SOURCE_OFFICIELLE)
    df["source"] = "officiel (DGS/canton)"
    print(f"✅ Source officielle détectée : {len(df)} EMS depuis {SOURCE_OFFICIELLE}")
    return df


def depuis_openstreetmap() -> pd.DataFrame:
    query = """
    [out:json][timeout:90];
    area["name"="Vaud"]["admin_level"="4"]->.a;
    (
      nwr["amenity"="nursing_home"](area.a);
      nwr["social_facility"="nursing_home"](area.a);
      nwr["social_facility"="assisted_living"](area.a);
    );
    out center tags;
    """
    r = requests.post(
        "https://overpass-api.de/api/interpreter",
        data={"data": query}, headers=UA, timeout=120,
    )
    r.raise_for_status()
    lignes = []
    for e in r.json()["elements"]:
        t = e.get("tags", {})
        lat = e.get("lat") or e.get("center", {}).get("lat")
        lon = e.get("lon") or e.get("center", {}).get("lon")
        lits = t.get("beds") or t.get("capacity") or t.get("capacity:beds")
        lignes.append({
            "nom": t.get("name"),
            "adresse": " ".join(filter(None, [
                t.get("addr:street"), t.get("addr:housenumber")])) or None,
            "npa": t.get("addr:postcode"),
            "commune": t.get("addr:city"),
            "lits": pd.to_numeric(lits, errors="coerce"),
            "lat": lat, "lon": lon,
        })
    df = pd.DataFrame(lignes)
    df["source"] = "OpenStreetMap (partiel, sans lits)"
    print(f"⚠️  Pas de fichier officiel — repli sur OpenStreetMap : {len(df)} EMS "
          f"(remplace data/raw/ems_vd_source.csv pour des données complètes avec lits)")
    return df


# --------------------------------------------------------------------------- #
# 2. Géocodage des adresses manquantes (API officielle geo.admin)
# --------------------------------------------------------------------------- #
def geocoder(adresse: str):
    """Renvoie (lat, lon) via le SearchServer officiel suisse, ou (None, None)."""
    try:
        r = requests.get(
            "https://api3.geo.admin.ch/rest/services/api/SearchServer",
            params={"type": "locations", "searchText": adresse, "limit": 1,
                    "sr": 4326}, headers=UA, timeout=20,
        )
        results = r.json().get("results", [])
        if results:
            a = results[0]["attrs"]
            return a["lat"], a["lon"]
    except Exception:
        pass
    return None, None


def completer_coordonnees(df: pd.DataFrame) -> pd.DataFrame:
    manquantes = df["lat"].isna() | df["lon"].isna()
    n = int(manquantes.sum())
    if n and {"adresse", "npa"}.issubset(df.columns):
        print(f"Géocodage de {n} adresses via geo.admin...")
        for i in df[manquantes].index:
            parts = [str(df.at[i, c]) for c in ["adresse", "npa", "commune"]
                     if c in df.columns and pd.notna(df.at[i, c])]
            if not parts:
                continue
            lat, lon = geocoder(" ".join(parts) + " Suisse")
            df.at[i, "lat"], df.at[i, "lon"] = lat, lon
            time.sleep(0.2)  # respect de l'API
    return df


# --------------------------------------------------------------------------- #
# 3. Rattachement à la commune (point-dans-polygone)
# --------------------------------------------------------------------------- #
def rattacher_communes(df: pd.DataFrame) -> pd.DataFrame:
    geo = json.loads(GEOJSON_COMMUNES.read_text(encoding="utf-8"))
    communes = gpd.GeoDataFrame(
        [{"ofs": f["properties"]["ofs"], "commune_ofs": f["properties"]["nom"],
          "geometry": shape(f["geometry"])} for f in geo["features"]],
        crs="EPSG:4326",
    )
    df = df.dropna(subset=["lat", "lon"]).copy()
    pts = gpd.GeoDataFrame(
        df, geometry=[Point(xy) for xy in zip(df["lon"], df["lat"])],
        crs="EPSG:4326",
    )
    joint = gpd.sjoin(pts, communes, how="left", predicate="within")
    joint = joint.drop(columns=["geometry", "index_right"], errors="ignore")
    return pd.DataFrame(joint)


def main():
    df = (depuis_fichier_officiel() if SOURCE_OFFICIELLE.exists()
          else depuis_openstreetmap())
    for col in ["lat", "lon"]:
        df[col] = pd.to_numeric(df.get(col), errors="coerce")

    df = completer_coordonnees(df)
    df = rattacher_communes(df)

    OUT.write_text(df.to_csv(index=False), encoding="utf-8")
    n_geo = df[["lat", "lon"]].notna().all(axis=1).sum()
    n_lits = int(df["lits"].notna().sum()) if "lits" in df else 0
    print(f"\n✅ {len(df)} EMS écrits dans {OUT}")
    print(f"   - géolocalisés : {n_geo}")
    print(f"   - avec nombre de lits : {n_lits}")
    if "ofs" in df:
        print(f"   - rattachés à une commune : {int(df['ofs'].notna().sum())}")


if __name__ == "__main__":
    main()
