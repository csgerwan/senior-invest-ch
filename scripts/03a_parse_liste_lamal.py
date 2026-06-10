"""
Étape 3 (amont) — Extraction de la liste officielle des EMS/EPSM vaudois avec lits.

Source : PDF officiel du canton de Vaud
  "Liste des établissements médico-sociaux et des divisions C au sens de
   l'article 39 al. 3 LAMal — Mandat 2024" (vd.ch)
  data/raw/liste_lamal_ems_vd_2024.pdf

Produit data/raw/ems_vd_source.csv (la source "officielle" du pipeline) avec :
  no_ua, nom, nom_clean, type, entite, lits, lits_geriatrie,
  lits_psy_age, lits_mixte, lits_psy_adulte, commentaire

Lancer depuis la racine du projet :
    python scripts/03a_parse_liste_lamal.py
"""

import re
from pathlib import Path

import pandas as pd
import pdfplumber

PDF = Path("data/raw/liste_lamal_ems_vd_2024.pdf")
OUT = Path("data/raw/ems_vd_source.csv")


def to_int(x):
    try:
        return int(str(x).strip())
    except (ValueError, TypeError):
        return None


def nettoyer_nom(nom: str) -> str:
    """Nom lisible pour le géocodage : enlève (...), les suffixes EMS/EPSM, etc."""
    n = re.sub(r"\([^)]*\)", " ", nom)
    n = re.sub(r"\b(EMS|EPSM|DIVISION C|DIV\.? C)\b", " ", n, flags=re.I)
    n = re.sub(r"\s+", " ", n).strip()
    return n.title()


def main():
    lignes = []
    with pdfplumber.open(PDF) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for r in table:
                    if not r or not r[0] or not re.match(r"^\d+$", str(r[0]).strip()):
                        continue
                    lignes.append(r)

    rows = []
    for r in lignes:
        # colonnes : 0 No.UA, 1 Activité(nom), 2 Type, 3 Entité, 4 Lits,
        #            5 Gériatrie, 6 Psy âge avancé, 7 Mixte, 8 Psy adulte, 9 Commentaire
        nom = (r[1] or "").strip()
        rows.append({
            "no_ua": to_int(r[0]),
            "nom": nom,
            "nom_clean": nettoyer_nom(nom),
            "type": (r[2] or "").strip(),
            "entite": (r[3] or "").strip(),
            "lits": to_int(r[4]),
            "lits_geriatrie": to_int(r[5]) if len(r) > 5 else None,
            "lits_psy_age": to_int(r[6]) if len(r) > 6 else None,
            "lits_mixte": to_int(r[7]) if len(r) > 7 else None,
            "lits_psy_adulte": to_int(r[8]) if len(r) > 8 else None,
            "commentaire": (r[9] or "").strip() if len(r) > 9 else "",
        })

    df = pd.DataFrame(rows)
    OUT.write_text(df.to_csv(index=False), encoding="utf-8")
    print(f"✅ {len(df)} établissements écrits dans {OUT}")
    print(f"   Total lits : {df['lits'].sum():.0f}")
    print(f"   Par type : {df['type'].value_counts().to_dict()}")


if __name__ == "__main__":
    main()
