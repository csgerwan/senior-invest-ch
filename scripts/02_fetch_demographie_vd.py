"""
Étape 2 — Démographie & vieillissement par commune vaudoise.

Source : OFS / STAT-TAB, table px-x-0102010000_103
  "Population résidante permanente selon commune, sexe, état civil et classe d'âge"
  API PXWeb : https://www.pxweb.bfs.admin.ch/api/v1/fr/

Ce script :
  1. lit les n° OFS des communes VD (data/processed/communes_vd.geojson)
  2. interroge l'API OFS pour l'année choisie (population permanente, tous sexes)
  3. calcule par commune : population totale, 65+, 80+ et leurs parts (%)
  4. enregistre data/processed/demographie_vd.csv

Lancer depuis la racine du projet :
    python scripts/02_fetch_demographie_vd.py
"""

import json
from pathlib import Path

import pandas as pd
import requests

ANNEE = "2024"  # dernière année disponible dans la table
TABLE_URL = (
    "https://www.pxweb.bfs.admin.ch/api/v1/fr/"
    "px-x-0102010000_103/px-x-0102010000_103.px"
)
REGION_CODE = "Kanton (-) / Bezirk (>>) / Gemeinde (......)"

GEOJSON = Path("data/processed/communes_vd.geojson")
OUT = Path("data/processed/demographie_vd.csv")

# Codes des classes d'âge (tranches de 5 ans) qui composent les seniors
CLASSES_65PLUS = ["65", "70", "75", "80", "85", "90", "95", "100"]
CLASSES_80PLUS = ["80", "85", "90", "95", "100"]
TOUTES_CLASSES = [
    "0", "5", "10", "15", "20", "25", "30", "35", "40", "45", "50",
    "55", "60", *CLASSES_65PLUS,
]


def codes_ofs_vd():
    geo = json.loads(GEOJSON.read_text(encoding="utf-8"))
    return {f["properties"]["ofs"]: f["properties"]["nom"] for f in geo["features"]}


def construire_requete(ofs_codes):
    """Requête PXWeb : année, communes VD, pop. permanente, tous sexes/états civils,
    toutes les classes d'âge (on agrège ensuite)."""
    return {
        "query": [
            {"code": "Jahr", "selection": {"filter": "item", "values": [ANNEE]}},
            {"code": REGION_CODE, "selection": {"filter": "item", "values": ofs_codes}},
            {"code": "Bevölkerungstyp", "selection": {"filter": "item", "values": ["1"]}},
            {"code": "Geschlecht", "selection": {"filter": "item", "values": ["-99999"]}},
            {"code": "Zivilstand", "selection": {"filter": "item", "values": ["-99999"]}},
            {"code": "Altersklasse", "selection": {"filter": "item", "values": TOUTES_CLASSES}},
        ],
        "response": {"format": "json-stat2"},
    }


def parser_jsonstat(js):
    """Transforme la réponse json-stat2 en DataFrame long (ofs, classe_age, valeur)."""
    dims = js["id"]                      # ordre des dimensions
    sizes = js["size"]                   # taille de chaque dimension
    values = js["value"]                 # valeurs à plat (row-major)

    # index -> code, pour la région et la classe d'âge
    def codes_de(dim):
        idx = js["dimension"][dim]["category"]["index"]
        return [c for c, _ in sorted(idx.items(), key=lambda kv: kv[1])]

    region_codes = codes_de(REGION_CODE)
    age_codes = codes_de("Altersklasse")

    i_region = dims.index(REGION_CODE)
    i_age = dims.index("Altersklasse")

    # déplie l'index plat en coordonnées multidimensionnelles
    lignes = []
    for flat, val in enumerate(values):
        coords, reste = [], flat
        for s in reversed(sizes):
            coords.append(reste % s)
            reste //= s
        coords.reverse()
        ofs = region_codes[coords[i_region]]
        age = age_codes[coords[i_age]]
        lignes.append({"ofs": ofs, "classe_age": age, "valeur": val or 0})
    return pd.DataFrame(lignes)


def main():
    noms = codes_ofs_vd()
    ofs_codes = list(noms.keys())

    print(f"Interrogation de l'OFS pour {len(ofs_codes)} communes (année {ANNEE})...")
    r = requests.post(TABLE_URL, json=construire_requete(ofs_codes), timeout=120)
    r.raise_for_status()
    df = parser_jsonstat(r.json())

    # Agrégations par commune
    total = df.groupby("ofs")["valeur"].sum().rename("pop_totale")
    p65 = (
        df[df["classe_age"].isin(CLASSES_65PLUS)]
        .groupby("ofs")["valeur"].sum().rename("pop_65plus")
    )
    p80 = (
        df[df["classe_age"].isin(CLASSES_80PLUS)]
        .groupby("ofs")["valeur"].sum().rename("pop_80plus")
    )

    out = pd.concat([total, p65, p80], axis=1).reset_index()
    out["nom"] = out["ofs"].map(noms)
    out["part_65plus"] = (out["pop_65plus"] / out["pop_totale"] * 100).round(1)
    out["part_80plus"] = (out["pop_80plus"] / out["pop_totale"] * 100).round(1)
    out["annee"] = int(ANNEE)
    out = out[
        ["ofs", "nom", "annee", "pop_totale", "pop_65plus", "pop_80plus",
         "part_65plus", "part_80plus"]
    ].sort_values("pop_totale", ascending=False)

    OUT.write_text(out.to_csv(index=False), encoding="utf-8")
    print(f"✅ {len(out)} communes écrites dans {OUT}")
    print("\nCanton de Vaud — total :")
    print(f"  Population : {out['pop_totale'].sum():,.0f}")
    print(f"  65+ : {out['pop_65plus'].sum():,.0f} "
          f"({out['pop_65plus'].sum()/out['pop_totale'].sum()*100:.1f}%)")
    print(f"  80+ : {out['pop_80plus'].sum():,.0f} "
          f"({out['pop_80plus'].sum()/out['pop_totale'].sum()*100:.1f}%)")
    print("\nTop 5 communes les plus âgées (part 80+, min 500 hab.) :")
    grandes = out[out["pop_totale"] >= 500].nlargest(5, "part_80plus")
    for _, row in grandes.iterrows():
        print(f"  {row['nom']:<25} {row['part_80plus']}% de 80+  "
              f"({row['pop_totale']:,.0f} hab.)")


if __name__ == "__main__":
    main()
