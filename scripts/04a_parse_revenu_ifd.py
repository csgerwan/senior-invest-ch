"""
Étape 4 (amont) — Revenu par commune via l'impôt fédéral direct (ESTV).

Source : ESTV, "Statistique IFD personnes physiques, par commune, 2022"
  data/raw/ifd_revenu_communes_2022.xlsx  (onglet 511 = revenu net, par tranche)
  Inclut les contribuables AVEC et SANS versement d'IFD (meilleure couverture).

On dispose du nombre de contribuables par tranche de revenu net. On en estime :
  - le revenu net MÉDIAN par commune (formule de la médiane par classes)
  - la part de contribuables à haut revenu (> 100'000 CHF)

Sortie : data/processed/revenu_vd.csv  (ofs, nom, nb_contribuables,
         revenu_median_est, part_haut_revenu)

Lancer depuis la racine du projet :
    python scripts/04a_parse_revenu_ifd.py
"""

from pathlib import Path

import openpyxl
import pandas as pd

XLSX = Path("data/raw/ifd_revenu_communes_2022.xlsx")
OUT = Path("data/processed/revenu_vd.csv")
KANTON_VD = "22"

# Bornes basses/hautes de chaque tranche (CHF). La dernière est plafonnée
# (sans effet sur la médiane). La tranche "0" est traitée comme [0, 1].
TRANCHES = [
    (0, 1), (1, 30000), (30001, 40000), (40001, 50000), (50001, 75000),
    (75001, 100000), (100001, 200000), (200001, 500000),
    (500001, 1000000), (1000001, 2000000),
]
SEUIL_HAUT_REVENU_IDX = 6  # tranches d'index >= 6 => revenu > 100'000


def n(v):
    """Convertit une cellule en entier ; '-', None, etc. -> 0."""
    try:
        return int(str(v).strip().replace("'", ""))
    except (ValueError, AttributeError, TypeError):
        return 0


def mediane_par_classes(counts):
    """Médiane estimée à partir des effectifs par classe (formule classique)."""
    total = sum(counts)
    if total == 0:
        return None
    cible = total / 2
    cumul = 0
    for i, c in enumerate(counts):
        if cumul + c >= cible:
            L, H = TRANCHES[i]
            largeur = H - L
            return round(L + ((cible - cumul) / c) * largeur) if c else L
        cumul += c
    return None


def main():
    wb = openpyxl.load_workbook(XLSX, read_only=True)
    rows = list(wb["511"].iter_rows(values_only=True))

    kanton = None
    out = []
    for r in rows[3:]:
        if r[0] not in (None, ""):
            kanton = str(r[0]).strip()
        if kanton != KANTON_VD or r[2] in (None, ""):
            continue
        ofs = str(n(r[2]))
        nom = str(r[3]).strip() if r[3] else ""
        counts = [n(r[4 + i]) for i in range(len(TRANCHES))]  # colonnes de tranches
        total = sum(counts)
        if total == 0:
            continue
        haut = sum(counts[SEUIL_HAUT_REVENU_IDX:])
        out.append({
            "ofs": ofs,
            "nom_ifd": nom,
            "nb_contribuables": total,
            "revenu_median_est": mediane_par_classes(counts),
            "part_haut_revenu": round(haut / total * 100, 1),
        })

    df = pd.DataFrame(out)
    OUT.write_text(df.to_csv(index=False), encoding="utf-8")
    print(f"✅ {len(df)} communes écrites dans {OUT}")
    print(f"   Revenu net médian estimé (canton, médiane des communes) : "
          f"{df['revenu_median_est'].median():,.0f} CHF".replace(",", "'"))
    print("\nTop 5 communes — revenu médian estimé :")
    for _, r in df.nlargest(5, "revenu_median_est").iterrows():
        print(f"   {r['nom_ifd']:28} {r['revenu_median_est']:>8,.0f} CHF  "
              f"({r['part_haut_revenu']}% >100k)".replace(",", "'"))


if __name__ == "__main__":
    main()
