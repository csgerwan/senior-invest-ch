"""
Étape 6 — Score d'opportunité d'investissement par commune.

Combine les 4 dimensions construites aux étapes 2 à 5 en sous-scores normalisés
(0-100), que la page Streamlit pondère ensuite EN DIRECT (poids ajustables) :

  1. demande        : population senior (80+) — taille + intensité du marché
  2. sous_offre     : manque de lits d'EMS au regard des seniors (tension)
  3. pouvoir_achat  : capacité à payer (revenu + fiscalité)  [indice étape 4]
  4. faisabilite    : coût immobilier (prix/m² bas = mieux)  [short-list seulement]

Sortie : data/processed/score_opportunite_vd.csv
  -> sous-scores 0-100 + valeurs brutes ; le score final est calculé dans l'app.

Lancer depuis la racine du projet :
    python scripts/06_build_score.py
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(".")
GEO = ROOT / "data/processed/communes_vd.geojson"
DEMO = ROOT / "data/processed/demographie_vd.csv"
EMS = ROOT / "data/processed/ems_vd.csv"
PA = ROOT / "data/processed/pouvoir_achat_vd.csv"
IMMO = ROOT / "data/processed/immobilier_vd.csv"
OUT = ROOT / "data/processed/score_opportunite_vd.csv"


def minmax(s):
    lo, hi = s.min(), s.max()
    return (s - lo) / (hi - lo) * 100 if hi > lo else s * 0 + 50


def main():
    geo = json.loads(GEO.read_text(encoding="utf-8"))
    base = pd.DataFrame([{"ofs": f["properties"]["ofs"], "nom": f["properties"]["nom"],
                          "district": f["properties"]["district"]} for f in geo["features"]])

    demo = pd.read_csv(DEMO, dtype={"ofs": str})
    ems = pd.read_csv(EMS, dtype={"ofs": str})
    pa = pd.read_csv(PA, dtype={"ofs": str})[["ofs", "indice_pouvoir_achat"]]
    immo = pd.read_csv(IMMO, dtype={"ofs": str})[["ofs", "prix_m2_appart"]]

    lits = ems.dropna(subset=["ofs"]).groupby("ofs")["lits"].sum().rename("lits_commune")
    df = (base
          .merge(demo[["ofs", "pop_totale", "pop_80plus", "part_80plus"]], on="ofs", how="left")
          .merge(lits, on="ofs", how="left")
          .merge(pa, on="ofs", how="left")
          .merge(immo, on="ofs", how="left"))
    df["lits_commune"] = df["lits_commune"].fillna(0)

    # 1. Demande : taille (70%) + intensité du vieillissement (30%)
    df["demande_score"] = (0.7 * minmax(df["pop_80plus"])
                           + 0.3 * minmax(df["part_80plus"])).round(1)

    # 2. Sous-offre : calculée AU NIVEAU DU DISTRICT (un EMS dessert une région,
    #    pas une seule commune). lits pour 100 personnes de 80+ dans le district ;
    #    bas = district sous-équipé. Toutes les communes d'un district héritent du score.
    dist = df.groupby("district").agg(
        lits_dist=("lits_commune", "sum"), pop80_dist=("pop_80plus", "sum")).reset_index()
    dist["lits_pour_100_district"] = (dist["lits_dist"] / dist["pop80_dist"] * 100).round(1)
    dist["sous_offre_score"] = (100 - minmax(dist["lits_pour_100_district"])).round(1)
    df = df.merge(dist[["district", "lits_pour_100_district", "sous_offre_score"]],
                  on="district", how="left")
    # indicateur communal conservé pour info/affichage
    df["lits_pour_100_80plus"] = (df["lits_commune"] / df["pop_80plus"] * 100).round(1)

    # 3. Pouvoir d'achat : indice étape 4 (déjà 0-100)
    df["pouvoir_achat_score"] = df["indice_pouvoir_achat"].round(1)

    # 4. Faisabilité immo : prix/m² bas = mieux (short-list uniquement)
    df["faisabilite_score"] = (100 - minmax(df["prix_m2_appart"])).round(1)

    cols = ["ofs", "nom", "district", "pop_totale", "pop_80plus", "part_80plus",
            "lits_commune", "lits_pour_100_80plus", "lits_pour_100_district",
            "prix_m2_appart", "demande_score", "sous_offre_score",
            "pouvoir_achat_score", "faisabilite_score"]
    df = df[cols]
    OUT.write_text(df.to_csv(index=False), encoding="utf-8")
    print(f"✅ {len(df)} communes écrites dans {OUT}")

    # Aperçu avec les poids par défaut (35/25/25/15, immo redistribué si absent)
    w = {"demande_score": .35, "sous_offre_score": .25,
         "pouvoir_achat_score": .25, "faisabilite_score": .15}
    def score(r):
        parts = {k: r[k] for k in w if pd.notna(r[k])}
        wt = sum(w[k] for k in parts)
        return round(sum(r[k] * w[k] for k in parts) / wt, 1) if wt else None
    df["score"] = df.apply(score, axis=1)
    apercu = df[df["pop_totale"] >= 1500].dropna(subset=["score"])
    print("\n🏆 Top 12 opportunités (poids par défaut, communes ≥ 1500 hab.) :")
    for _, r in apercu.nlargest(12, "score").iterrows():
        print(f"   {r['nom']:24} score {r['score']:>5}  "
              f"(80+ {int(r['pop_80plus']):4}, lits/100 {r['lits_pour_100_80plus']:>5}, "
              f"PA {r['pouvoir_achat_score']:>4})")


if __name__ == "__main__":
    main()
