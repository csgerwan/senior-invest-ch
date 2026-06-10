"""
Étape 4 (amont) — Fortune moyenne par contribuable, PAR DISTRICT (contexte).

Source : StatVD, T18.02.16 "Impôt cantonal sur la fortune des PP, par district"
  data/raw/fortune_districts.xlsx (feuille 'Serie')
  Le Canton est en valeurs absolues ; les districts en PROPORTIONS du canton.

On reconstitue la fortune moyenne par contribuable et par district :
  fortune_moy_district = (part_fortune / part_contrib) * (fortune_cant / contrib_cant)

⚠️ Donnée au DISTRICT (10 zones), pas par commune (secret fiscal). À utiliser
comme contexte, pas comme valeur communale précise.

Sortie : data/processed/fortune_districts.csv (district, fortune_moy_chf)

Lancer depuis la racine du projet :
    python scripts/04c_parse_fortune_districts.py
"""

from pathlib import Path

import openpyxl
import pandas as pd

XLSX = Path("data/raw/fortune_districts.xlsx")
OUT = Path("data/processed/fortune_districts.csv")


def num(v):
    try:
        return float(str(v).replace("'", "").replace(" ", ""))
    except (ValueError, TypeError):
        return None


def main():
    ws = openpyxl.load_workbook(XLSX, read_only=True)["Serie"]
    rows = [r for r in ws.iter_rows(values_only=True)]

    # repère l'en-tête "District | Contribuables | Fortune ... | Impôt ..."
    h = next(i for i, r in enumerate(rows)
             if r and str(r[0]).strip() == "District")
    canton = rows[h + 1]
    contrib_cant, fortune_cant = num(canton[1]), num(canton[2])
    moy_cant = fortune_cant / contrib_cant  # en milliers de CHF

    out = []
    for r in rows[h + 2:]:
        nom = r[0]
        if not isinstance(nom, str) or not nom.strip() or nom.strip().startswith("dont"):
            continue
        if nom.strip().lower() == "canton":
            continue
        part_c, part_f = num(r[1]), num(r[2])
        if not part_c or not part_f:
            if nom.strip():            # fin du bloc de districts
                break
            continue
        fortune_moy = (part_f / part_c) * moy_cant * 1000  # -> CHF
        out.append({"district": nom.strip(), "fortune_moy_chf": round(fortune_moy)})
        if len(out) >= 10:
            break

    df = pd.DataFrame(out)
    OUT.write_text(df.to_csv(index=False), encoding="utf-8")
    print(f"✅ {len(df)} districts écrits dans {OUT}")
    print(f"   Fortune moyenne/contribuable (canton) : {moy_cant*1000:,.0f} CHF"
          .replace(",", "'"))
    for _, r in df.sort_values("fortune_moy_chf", ascending=False).iterrows():
        print(f"   {r['district']:24} {r['fortune_moy_chf']:>12,.0f} CHF".replace(",", "'"))


if __name__ == "__main__":
    main()
