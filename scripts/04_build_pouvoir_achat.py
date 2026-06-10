"""
Étape 4 — Construction de l'indice de pouvoir d'achat par commune vaudoise.

Fusionne les briques préparées :
  - revenu net médian estimé + part de hauts revenus  (revenu_vd.csv, ESTV 2022)   [commune]
  - coefficient d'impôt communal                      (coefficients_vd.csv, 2026)  [commune]
  - fortune moyenne par contribuable                  (fortune_districts.csv)      [district]

Indice composite (0-100), basé sur les deux indicateurs réellement communaux :
  indice = moyenne( revenu_normalisé , (100 - coefficient_normalisé) )
  -> un revenu élevé tire l'indice vers le haut ; une charge fiscale élevée le baisse.
La fortune (district) est jointe comme CONTEXTE, pas dans l'indice.

Sortie : data/processed/pouvoir_achat_vd.csv

Lancer depuis la racine du projet :
    python scripts/04_build_pouvoir_achat.py
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(".")
GEO = ROOT / "data/processed/communes_vd.geojson"
REVENU = ROOT / "data/processed/revenu_vd.csv"
COEFF = ROOT / "data/processed/coefficients_vd.csv"
FORTUNE = ROOT / "data/processed/fortune_districts.csv"
OUT = ROOT / "data/processed/pouvoir_achat_vd.csv"


def minmax(s):
    """Normalise une série en 0-100 (min->0, max->100)."""
    lo, hi = s.min(), s.max()
    return (s - lo) / (hi - lo) * 100 if hi > lo else s * 0


def main():
    geo = json.loads(GEO.read_text(encoding="utf-8"))
    base = pd.DataFrame([{"ofs": f["properties"]["ofs"],
                          "nom": f["properties"]["nom"],
                          "district": f["properties"]["district"]}
                         for f in geo["features"]])

    revenu = pd.read_csv(REVENU, dtype={"ofs": str})
    coeff = pd.read_csv(COEFF, dtype={"ofs": str})[["ofs", "coefficient"]]
    fortune = pd.read_csv(FORTUNE)

    df = (base
          .merge(revenu[["ofs", "revenu_median_est", "part_haut_revenu",
                         "nb_contribuables"]], on="ofs", how="left")
          .merge(coeff, on="ofs", how="left")
          .merge(fortune, on="district", how="left"))

    # Normalisations (sur les communes ayant les deux indicateurs)
    df["revenu_norm"] = minmax(df["revenu_median_est"])
    df["coeff_norm"] = minmax(df["coefficient"])
    # Indice : revenu (+) et charge fiscale (-)
    df["indice_pouvoir_achat"] = ((df["revenu_norm"] + (100 - df["coeff_norm"])) / 2).round(1)

    df = df.sort_values("indice_pouvoir_achat", ascending=False)
    OUT.write_text(df.to_csv(index=False), encoding="utf-8")

    n_complet = int(df["indice_pouvoir_achat"].notna().sum())
    print(f"✅ {len(df)} communes écrites dans {OUT}")
    print(f"   Indice calculé pour {n_complet} communes "
          f"(revenu + coefficient disponibles)")
    print("\n🏆 Top 5 pouvoir d'achat :")
    for _, r in df.head(5).iterrows():
        print(f"   {r['nom']:26} indice {r['indice_pouvoir_achat']:>5}  "
              f"(revenu {r['revenu_median_est']:.0f}, coeff {r['coefficient']:.0f})")
    print("\n🔻 Bottom 5 :")
    for _, r in df.dropna(subset=["indice_pouvoir_achat"]).tail(5).iterrows():
        print(f"   {r['nom']:26} indice {r['indice_pouvoir_achat']:>5}  "
              f"(revenu {r['revenu_median_est']:.0f}, coeff {r['coefficient']:.0f})")


if __name__ == "__main__":
    main()
