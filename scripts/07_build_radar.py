"""
V2 — Données du radar « Évaluation d'un bien » (zone verte : qualification demande).

Calcule, par commune, les 3 notes sur 0-5 de la zone verte du radar investisseur :
  1. Pouvoir d'achat senior      = indice pouvoir d'achat (étape 4) / 20
  2. Population senior de la zone = nb de 80+ normalisé (min-max canton) -> 0-5
  3. Proximité & saturation EMS   = TENSION : zones mal couvertes (saturation du
     district vu la pop. senior, en priorité, + éloignement de l'EMS le plus proche)

Réutilise les sorties existantes (score, démographie, EMS, immobilier).
Sortie : data/processed/radar_vd.csv

Lancer depuis la racine du projet :
    python scripts/07_build_radar.py
"""

from pathlib import Path

import pandas as pd

P = Path("data/processed")
OUT = P / "radar_vd.csv"


def minmax(s):
    lo, hi = s.min(), s.max()
    return (s - lo) / (hi - lo) * 100 if hi > lo else s * 0 + 50


def main():
    score = pd.read_csv(P / "score_opportunite_vd.csv", dtype={"ofs": str})
    demo = pd.read_csv(P / "demographie_vd.csv", dtype={"ofs": str})
    ems = pd.read_csv(P / "ems_vd.csv", dtype={"ofs": str})

    df = score[["ofs", "nom", "district", "dist_ems_km", "pop_80plus",
                "part_80plus", "indice_pouvoir_achat", "prix_m2_appart",
                "prix_fiabilite", "eloignement_score"]].copy()

    # --- Saturation EMS au niveau district : lits pour 100 personnes de 80+ ---
    ofs_district = score[["ofs", "district"]]
    lits_dist = (ems.dropna(subset=["ofs"]).merge(ofs_district, on="ofs", how="left")
                 .groupby("district")["lits"].sum())
    pop80_dist = (demo.merge(ofs_district, on="ofs", how="left")
                  .groupby("district")["pop_80plus"].sum())
    lits_pour_100 = (lits_dist / pop80_dist * 100).rename("lits_pour_100_district")
    df = df.merge(lits_pour_100, on="district", how="left")
    df["lits_pour_100_district"] = df["lits_pour_100_district"].fillna(0).round(1)

    # saturation : peu de lits/senior => district sous tension => score haut
    saturation = 100 - minmax(df["lits_pour_100_district"])

    # --- Notes 0-5 de la zone verte ---
    df["note_pouvoir_achat"] = (df["indice_pouvoir_achat"] / 20).round(2)
    df["note_population"] = (minmax(df["pop_80plus"]) / 20).round(2)
    # tension EMS : saturation prioritaire (60%) + éloignement (40%)
    tension = 0.6 * saturation + 0.4 * df["eloignement_score"]
    df["note_tension_ems"] = (tension / 20).round(2)

    cols = ["ofs", "nom", "district",
            "note_pouvoir_achat", "note_population", "note_tension_ems",
            "indice_pouvoir_achat", "pop_80plus", "part_80plus",
            "dist_ems_km", "lits_pour_100_district",
            "prix_m2_appart", "prix_fiabilite"]
    df[cols].to_csv(OUT, index=False)
    print(f"✅ {len(df)} communes écrites dans {OUT}")
    print("\nExemples (notes /5) :")
    for _, r in df.sort_values("note_tension_ems", ascending=False).head(6).iterrows():
        print(f"   {r['nom']:22} PA {r['note_pouvoir_achat']:.1f} | "
              f"Pop {r['note_population']:.1f} | Tension {r['note_tension_ems']:.1f}  "
              f"(dist EMS {r['dist_ems_km']} km, lits/100 {r['lits_pour_100_district']})")


if __name__ == "__main__":
    main()
