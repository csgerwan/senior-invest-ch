"""
Étape 3 — Géolocalisation de la liste officielle des EMS/EPSM vaudois.

Entrée  : data/raw/ems_vd_source.csv  (163 établissements + lits, issus du PDF LAMal)
Sortie  : data/processed/ems_vd.csv

Stratégie de géolocalisation (sans jamais inventer une position), avec indice
de confiance :
  1. Correspondance de nom avec OpenStreetMap (qui fournit des coordonnées) -> "OSM"
  2. Sinon géocodage de l'adresse via l'API officielle geo.admin, en n'acceptant
     QUE les résultats de type adresse situés dans le canton -> "adresse"
  3. Commune déduite : par point-dans-polygone si on a des coordonnées, sinon par
     détection d'un nom de commune vaudoise dans le nom de l'établissement -> "nom"
  4. Sinon : non localisé (à compléter)

Lancer depuis la racine du projet :
    python scripts/03_fetch_ems_vd.py
"""

import json
import re
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point, shape

SOURCE = Path("data/raw/ems_vd_source.csv")
COMMUNES = Path("data/processed/communes_vd.geojson")
OUT = Path("data/processed/ems_vd.csv")
UA = {"User-Agent": "senior-invest-ch/1.0 (projet stage)"}

# Bounding box approximative du canton de Vaud (lon/lat) pour filtrer le géocodage
VD_BBOX = (6.0, 46.15, 7.25, 46.99)  # (lon_min, lat_min, lon_max, lat_max)


def norm(s: str) -> str:
    """Normalise pour comparaison : minuscules, sans accents, sans mots vides."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = s.lower()
    for stop in ["ems", "epsm", "fondation", "residence", "home", "ehc",
                 "hopital", "site", "div", "division", "c", "sa", "la", "le",
                 "les", "de", "du", "des", "d"]:
        s = re.sub(rf"\b{stop}\b", " ", s)
    return re.sub(r"[^a-z0-9 ]", " ", s).strip()


OSM_CACHE = Path("data/raw/cache_osm.json")


def charger_osm():
    """EMS OSM (nom + coordonnées) servant d'ancrage de géolocalisation.
    Tolérant aux pannes : met en cache et retombe sur le cache (ou []) si
    l'API Overpass est indisponible (les ancrages OSM ne sont qu'un bonus)."""
    query = """
    [out:json][timeout:90];
    area["name"="Vaud"]["admin_level"="4"]->.a;
    ( nwr["amenity"="nursing_home"](area.a);
      nwr["social_facility"="nursing_home"](area.a);
      nwr["social_facility"="assisted_living"](area.a); );
    out center tags;
    """
    try:
        r = requests.post("https://overpass-api.de/api/interpreter",
                          data={"data": query}, headers=UA, timeout=120)
        r.raise_for_status()
        pts = []
        for e in r.json()["elements"]:
            t = e.get("tags", {})
            if not t.get("name"):
                continue
            lat = e.get("lat") or e.get("center", {}).get("lat")
            lon = e.get("lon") or e.get("center", {}).get("lon")
            if lat and lon:
                pts.append({"nom_norm": norm(t["name"]), "lat": lat, "lon": lon})
        OSM_CACHE.write_text(json.dumps(pts, ensure_ascii=False))
        return pts
    except Exception as ex:
        if OSM_CACHE.exists():
            print(f"  ⚠️ Overpass indisponible ({ex}) — utilisation du cache OSM.")
            return json.loads(OSM_CACHE.read_text())
        print(f"  ⚠️ Overpass indisponible ({ex}) — on continue sans ancrage OSM.")
        return []


def match_osm(nom_norm, osm, seuil=0.6):
    """Renvoie (lat, lon) du meilleur OSM si la similarité dépasse le seuil."""
    best, best_r = None, 0
    for o in osm:
        r = SequenceMatcher(None, nom_norm, o["nom_norm"]).ratio()
        if r > best_r:
            best, best_r = o, r
    return (best["lat"], best["lon"]) if best and best_r >= seuil else (None, None)


def geocode_adresse(texte):
    """geo.admin SearchServer : n'accepte qu'une ADRESSE située dans le canton."""
    try:
        r = requests.get(
            "https://api3.geo.admin.ch/rest/services/api/SearchServer",
            params={"type": "locations", "searchText": texte, "limit": 3,
                    "origins": "address"},
            headers=UA, timeout=15)
        for res in r.json().get("results", []):
            a = res["attrs"]
            lon, lat = a.get("lon"), a.get("lat")
            if lat and VD_BBOX[0] <= lon <= VD_BBOX[2] and VD_BBOX[1] <= lat <= VD_BBOX[3]:
                return lat, lon
    except Exception:
        pass
    return None, None


# Cache disque des réponses search.ch (évite de regâcher le quota quotidien gratuit)
CACHE = Path("data/raw/cache_searchch.json")
_cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
_rate_limited = False


def adresse_searchch(nom, nom_norm):
    """Cherche un EMS dans l'annuaire search.ch (sans clé), avec cache disque.
    Parse le contenu ligne par ligne. Renvoie (rue, npa, ville) en VD, ou None.
    En cas de quota dépassé (HTTP 429), arrête d'interroger l'API pour la session."""
    global _rate_limited
    if nom in _cache:                       # déjà connu -> aucune requête
        return tuple(_cache[nom]) if _cache[nom] else None
    if _rate_limited:                       # quota épuisé -> on n'insiste pas
        return None
    try:
        r = requests.get("https://tel.search.ch/api/",
                         params={"was": nom, "wo": "VD"}, headers=UA, timeout=15)
        if r.status_code == 429:
            _rate_limited = True
            print("  ⚠️ search.ch : quota quotidien épuisé (429) — reprise possible demain.")
            return None
        entries = re.findall(r"<entry>(.*?)</entry>", r.text, re.S)
        mots = [w for w in nom_norm.split() if len(w) > 3]
        resultat = None
        for e in entries:
            titre = re.search(r"<title[^>]*>(.*?)</title>", e, re.S)
            contenu = re.search(r"<content[^>]*>(.*?)</content>", e, re.S)
            if not contenu:
                continue
            lignes = [l.strip() for l in contenu.group(1).splitlines() if l.strip()]
            # validation de pertinence : le nom doit se retrouver dans l'entrée
            ref = norm(titre.group(1) if titre else "") + " " + norm(" ".join(lignes))
            if mots and not any(w in ref for w in mots):
                continue  # entrée non pertinente -> entrée suivante
            for i, l in enumerate(lignes):
                m = re.match(r"^(1\d{3})\s+(.+)$", l)
                if not m:
                    continue
                npa = m.group(1)
                ville = re.sub(r"\s+(VD|VS|FR|GE|NE|JU|BE)$", "", m.group(2)).strip()
                rue = lignes[i - 1] if i > 0 else ""
                resultat = [rue, npa, ville]
                break
            if resultat:
                break
        _cache[nom] = resultat            # mémorise même les échecs (None)
        CACHE.write_text(json.dumps(_cache, ensure_ascii=False))
        return tuple(resultat) if resultat else None
    except Exception:
        pass
    return None


def main():
    df = pd.read_csv(SOURCE)
    geo = json.loads(COMMUNES.read_text(encoding="utf-8"))
    communes = gpd.GeoDataFrame(
        [{"ofs": f["properties"]["ofs"], "commune": f["properties"]["nom"],
          "geometry": shape(f["geometry"])} for f in geo["features"]],
        crs="EPSG:4326")
    noms_communes = {norm(c): (o, c) for o, c in zip(communes["ofs"], communes["commune"])}

    print("Chargement des ancrages OpenStreetMap...")
    osm = charger_osm()
    print(f"  {len(osm)} points OSM disponibles")

    lats, lons, conf, villes = [], [], [], []
    print(f"Géolocalisation de {len(df)} établissements...")
    for nom in df["nom_clean"]:
        nn = norm(nom)
        ville_sc = None
        # 1) ancrage OpenStreetMap (coordonnées directes)
        lat, lon = match_osm(nn, osm)
        c = "OSM" if lat else None
        # 2) adresse trouvée dans l'annuaire search.ch -> ville (commune) + coords
        if not lat:
            res = adresse_searchch(nom, nn)
            time.sleep(0.2)
            if res:
                rue, npa, ville_sc = res
                lat, lon = geocode_adresse(f"{rue} {npa} {ville_sc}".strip())
                c = "search.ch" if (lat or ville_sc) else None
                time.sleep(0.15)
        # 3) géocodage direct du nom (rare)
        if not lat and not ville_sc:
            lat, lon = geocode_adresse(nom)
            c = "adresse" if lat else None
            time.sleep(0.15)
        lats.append(lat); lons.append(lon); conf.append(c); villes.append(ville_sc)
    df["lat"], df["lon"], df["geo_source"], df["ville_sc"] = lats, lons, conf, villes

    # Commune par "commune la plus proche" si coordonnées (gère les points
    # tombant en bordure ou sur le lac à cause d'une géométrie simplifiée)
    df["ofs"] = None
    df["commune"] = None
    loc = df.dropna(subset=["lat", "lon"]).copy()
    if len(loc):
        pts = gpd.GeoDataFrame(
            loc, geometry=[Point(xy) for xy in zip(loc["lon"], loc["lat"])],
            crs="EPSG:4326")
        # projection métrique suisse (LV95) pour un calcul de distance correct
        j = gpd.sjoin_nearest(pts.to_crs(2056), communes.to_crs(2056), how="left")
        j = j[~j.index.duplicated(keep="first")]
        df.loc[j.index, "ofs"] = j["ofs_right"].values if "ofs_right" in j else j["ofs"].values
        df.loc[j.index, "commune"] = (j["commune_right"].values
                                      if "commune_right" in j else j["commune"].values)

    # Repli 0 : référence manuelle vérifiée (data/raw/ems_communes_manuel.csv)
    manuel = Path("data/raw/ems_communes_manuel.csv")
    if manuel.exists():
        ref = pd.read_csv(manuel)
        for _, m in ref.iterrows():
            cle, comm = str(m["motcle"]).upper(), norm(m["commune"])
            if comm not in noms_communes:
                continue
            ofs, cnom = noms_communes[comm]
            for i in df[df["ofs"].isna()].index:
                if cle in str(df.at[i, "nom"]).upper():
                    df.at[i, "ofs"], df.at[i, "commune"] = ofs, cnom
                    df.at[i, "geo_source"] = "manuel"

    # Repli 1 : commune déduite de la ville renvoyée par search.ch
    for i in df[df["ofs"].isna()].index:
        v = df.at[i, "ville_sc"]
        if isinstance(v, str) and norm(v) in noms_communes:
            ofs, cnom = noms_communes[norm(v)]
            df.at[i, "ofs"], df.at[i, "commune"] = ofs, cnom

    # Repli 2 : nom de commune vaudoise présent dans le nom de l'établissement
    for i in df[df["ofs"].isna()].index:
        nn = " " + norm(df.at[i, "nom"]) + " "
        for cnorm, (ofs, cnom) in noms_communes.items():
            if len(cnorm) >= 4 and f" {cnorm} " in nn:
                df.at[i, "ofs"], df.at[i, "commune"] = ofs, cnom
                if pd.isna(df.at[i, "geo_source"]):
                    df.at[i, "geo_source"] = "nom"
                break

    OUT.write_text(df.to_csv(index=False), encoding="utf-8")
    n_coord = int(df[["lat", "lon"]].notna().all(axis=1).sum())
    n_comm = int(df["ofs"].notna().sum())
    print(f"\n✅ {len(df)} établissements écrits dans {OUT}")
    print(f"   - avec coordonnées : {n_coord}")
    print(f"   - rattachés à une commune : {n_comm}")
    print(f"   - répartition confiance : {df['geo_source'].value_counts(dropna=False).to_dict()}")
    print(f"   - lits rattachés à une commune : "
          f"{df[df['ofs'].notna()]['lits'].sum():.0f} / {df['lits'].sum():.0f}")


if __name__ == "__main__":
    main()
