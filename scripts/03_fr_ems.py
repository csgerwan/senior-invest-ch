"""
EMS Fribourg — capacité (lits long séjour) + localisation, format homogène VD/GE.

Source lits : Ordonnance du 30 janvier 2018 fixant la liste des EMS du canton de
Fribourg (RSF 834.2.41), version en vigueur — data/raw/liste_ems_fr_2026.pdf.
On additionne par établissement les lits « long séjour reconnus » + « long séjour AOS »
(les lits court séjour et places de foyer de jour sont exclus, comme pour VD/GE).

Localisation : géocodage geo.admin (SearchServer) sur « nom, NPA commune » avec cache
disque, puis rattachement à la commune par point-dans-polygone.

Sortie : data/processed/ems_fr.csv (nom_clean, type, lits, lat, lon, ofs, commune, geo_source)

Lancer depuis la racine du projet :
    python scripts/03_fr_ems.py
"""

import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pdfplumber
from shapely.geometry import Point, shape

PDF = Path("data/raw/liste_ems_fr_2026.pdf")
COMMUNES = Path("data/processed/communes_vd.geojson")
CACHE = Path("data/raw/cache_geoadmin_fr.json")
OUT = Path("data/processed/ems_fr.csv")

# Lignes de « bruit » (en-têtes/pieds de page) à ignorer dans un item multi-lignes
NOISE = re.compile(r"^(\d+$|Liste des|O 834|834\.2|Entrée|Art\.|La liste|"
                   r"Le Conseil|Vu |Sur la|Arrête|Modification|Le présent|"
                   r"Cette modification|Direction)")
ITEM = re.compile(r"^\d+\.\s+(.*)")
DISTRICT = re.compile(r"Art\.\s*\d+\s+Etablissements du district de (?:la |l.|le |du )?(.+)")
SECTION = re.compile(r"^([a-d])\)\s")
# « Nom, NPA Commune  NN lits »  (le nom peut contenir des virgules internes)
LIGNE = re.compile(r"(.+),\s*(\d{4})\s+(.+?)\s+(\d+)\s+lits")


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def parse_pdf():
    """-> liste de dicts {district, nom, npa, commune, lits} (long séjour recon+AOS)."""
    t = "\n".join((p.extract_text() or "") for p in pdfplumber.open(PDF).pages)
    district = section = None
    buf = None
    items = []

    def flush():
        nonlocal buf
        if buf:
            s = " ".join(buf).strip()
            m = LIGNE.search(s)
            if m and section in ("a", "b"):
                items.append({
                    "district": district, "nom": m.group(1).strip(),
                    "npa": m.group(2), "commune": m.group(3).strip(),
                    "lits": int(m.group(4)),
                })
        buf = None

    for raw in t.splitlines():
        l = raw.strip()
        dm = DISTRICT.match(l)
        if dm:
            flush(); district = dm.group(1).strip(); section = None; continue
        sm = SECTION.match(l)
        if sm:
            flush(); section = sm.group(1); continue
        im = ITEM.match(l)
        if im:
            flush(); buf = [im.group(1)]; continue
        if buf is not None and not NOISE.match(l):
            buf.append(l)
    flush()

    # Fusion des lits d'un même établissement (reconnus + AOS)
    fusion = {}
    for it in items:
        cle = norm(it["nom"])
        if cle in fusion:
            fusion[cle]["lits"] += it["lits"]
        else:
            fusion[cle] = it
    return list(fusion.values())


def geocode(nom, npa, commune, cache):
    cle = f"{nom}|{npa} {commune}"
    if cle in cache:
        return cache[cle]
    coords = None
    for q in (f"{nom}, {npa} {commune}", f"{npa} {commune}"):
        url = ("https://api3.geo.admin.ch/rest/services/api/SearchServer?"
               + urllib.parse.urlencode({"searchText": q, "type": "locations",
                                         "limit": 5, "sr": 4326}))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "senior-invest-ch"})
            res = json.loads(urllib.request.urlopen(req, timeout=30).read())
            # ne retient qu'un résultat dont le libellé contient le bon NPA
            # (évite les faux positifs renvoyés au centre du pays)
            for hit in res.get("results", []):
                a = hit["attrs"]
                if npa in a.get("label", ""):
                    coords = (a["lat"], a["lon"])
                    break
            if coords:
                break
        except Exception:
            pass
        time.sleep(0.3)
    cache[cle] = coords
    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return coords


def main():
    ems = parse_pdf()
    print(f"EMS long séjour (reconnus+AOS) extraits du PDF : {len(ems)} · "
          f"total lits : {sum(e['lits'] for e in ems)}")

    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    rows = []
    for e in ems:
        c = geocode(e["nom"], e["npa"], e["commune"], cache)
        rows.append({"nom_clean": e["nom"], "type": "EMS", "lits": e["lits"],
                     "lat": c[0] if c else None, "lon": c[1] if c else None,
                     "npa": e["npa"], "commune_ord": e["commune"],
                     "geo_source": "geo.admin"})
    df = pd.DataFrame(rows)
    n_geo = int(df["lat"].notna().sum())
    print(f"géocodés : {n_geo}/{len(df)}")

    # communes FR : ofs + centroïde, indexées par nom normalisé (source d'autorité
    # pour le rattachement, l'adresse de l'ordonnance donnant la commune exacte)
    geo = json.loads(COMMUNES.read_text(encoding="utf-8"))
    communes = gpd.GeoDataFrame(
        [{"ofs": f["properties"]["ofs"], "commune": f["properties"]["nom"],
          "geometry": shape(f["geometry"])} for f in geo["features"]], crs="EPSG:4326")
    cen = communes.to_crs(2056).geometry.centroid.to_crs(4326)
    par_nom = {norm(r.commune): (r.ofs, r.commune, cen[i].y, cen[i].x)
               for i, r in communes.iterrows()}
    # alias localité (ordonnance) -> commune politique (geojson)
    ALIAS = {"morat": "murten"}
    for a, cible in ALIAS.items():
        if cible in par_nom:
            par_nom[a] = par_nom[cible]

    poly_par_ofs = dict(zip(communes["ofs"], communes["geometry"]))

    for i, r in df.iterrows():
        info = par_nom.get(norm(r["commune_ord"]))
        if info:
            # 1) commune de l'ordonnance = source d'autorité (le géocodage peut
            #    renvoyer un point erroné tombant dans une commune voisine)
            df.at[i, "ofs"], df.at[i, "commune"] = info[0], info[1]
            pt = Point(r["lon"], r["lat"]) if pd.notna(r["lat"]) else None
            if pt is None or not poly_par_ofs[info[0]].contains(pt):
                df.at[i, "lat"], df.at[i, "lon"] = info[2], info[3]  # centroïde
        elif pd.notna(r["lat"]):
            # 2) nom non reconnu (fusion de commune) -> point-dans-polygone
            pt = Point(r["lon"], r["lat"])
            for ofs, poly in poly_par_ofs.items():
                if poly.contains(pt):
                    df.at[i, "ofs"] = ofs
                    df.at[i, "commune"] = communes.loc[communes["ofs"] == ofs,
                                                       "commune"].iloc[0]
                    break
        if pd.isna(df.at[i, "ofs"]):
            df.at[i, "commune"] = r["commune_ord"]
    df = df.drop(columns=["commune_ord", "npa"])

    OUT.write_text(df.to_csv(index=False), encoding="utf-8")
    print(f"✅ {len(df)} EMS Fribourg écrits dans {OUT}")
    print(f"   rattachés commune : {df['ofs'].notna().sum()} · total lits : {df['lits'].sum()}")
    manq = df[df["lat"].isna()]["nom_clean"].tolist()
    if manq:
        print(f"   non géocodés : {manq}")


if __name__ == "__main__":
    main()
