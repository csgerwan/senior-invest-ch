"""
Étape 1 — Préparation des limites communales vaudoises.

Lit le GeoJSON brut téléchargé depuis Opendatasoft (source officielle OFS/geo.admin,
millésime 2025) et produit un GeoJSON propre dans data/processed/.

Nettoyages effectués :
- aplatit les propriétés qui arrivent sous forme de listes (['Aigle'] -> 'Aigle')
- normalise les noms de propriétés (gem_name -> nom, gem_code -> ofs, bez_name -> district)
- garde le numéro OFS en texte (clé de jointure avec les autres jeux de données)

Lancer depuis la racine du projet :
    python scripts/01_prepare_communes_vd.py
"""

import json
from pathlib import Path

RAW = Path("data/raw/communes_romandie.geojson")  # VD + GE + FR
OUT = Path("data/processed/communes_vd.geojson")


def flatten(value):
    """Transforme ['Aigle'] en 'Aigle' ; laisse les valeurs simples telles quelles."""
    if isinstance(value, list):
        return value[0] if value else None
    return value


def main():
    data = json.loads(RAW.read_text(encoding="utf-8"))

    for feature in data["features"]:
        p = feature["properties"]
        canton = flatten(p.get("kan_name"))
        district = flatten(p.get("bez_name")) or canton  # repli : canton si pas de district
        feature["properties"] = {
            "nom": flatten(p.get("gem_name")),
            "ofs": str(flatten(p.get("gem_code"))),  # numéro OFS = clé de jointure
            "district": district,
            "canton": canton,
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    print(f"✅ {len(data['features'])} communes écrites dans {OUT}")
    print("Exemple :", data["features"][0]["properties"])


if __name__ == "__main__":
    main()
