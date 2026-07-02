"""
Coefficients d'impôt communaux — VD + GE + FR, format unifié.

⚠️ Les trois cantons n'utilisent PAS la même base fiscale :
  - VD : coefficient annuel communal, en % de l'impôt cantonal de base vaudois
  - GE : centimes additionnels communaux (surcharge sur l'impôt cantonal genevois)
  - FR : coefficient communal, en % de l'impôt cantonal de base fribourgeois
Les valeurs ne sont donc PAS comparables telles quelles entre cantons ; l'indice de
pouvoir d'achat les normalisera PAR CANTON (attractivité fiscale relative interne).

Sources :
  - VD : data/processed/coefficients_vd.csv (déjà produit par 04b, vd.ch 2026)
  - GE : data/raw/centimes_add_ge_2026.xlsx (ge.ch, Service des affaires communales)
  - FR : opendata.fr.ch dataset 18_03_coefficients (type « revenu et fortune »)

Sortie : data/processed/coefficients_romandie.csv (ofs, nom, canton, coefficient, annee)

Lancer depuis la racine du projet :
    python scripts/04b2_coefficients_romandie.py
"""

import json
import re
import unicodedata
from pathlib import Path

import openpyxl
import pandas as pd

GEO = Path("data/processed/communes_vd.geojson")
VD = Path("data/processed/coefficients_vd.csv")
GE_XLSX = Path("data/raw/centimes_add_ge_2026.xlsx")
FR_CSV = Path("data/raw/coefficients_fr_opendata.csv")
OUT = Path("data/processed/coefficients_romandie.csv")


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\((ge|fr|vd)\)", " ", s)          # retire le suffixe cantonal
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    s = re.sub(r"^(le|la|les)\s+", "", s)           # retire l'article de tête
    return s


def communes_par_canton():
    geo = json.loads(GEO.read_text(encoding="utf-8"))
    par_nom, ofs2canton, ofs2nom = {}, {}, {}
    for f in geo["features"]:
        p = f["properties"]
        par_nom.setdefault(p["canton"], {})[norm(p["nom"])] = p["ofs"]
        ofs2canton[str(p["ofs"])] = p["canton"]
        ofs2nom[str(p["ofs"])] = p["nom"]
    return par_nom, ofs2canton, ofs2nom


def coeff_vd():
    d = pd.read_csv(VD, dtype={"ofs": str})[["ofs", "nom", "coefficient"]]
    d["canton"] = "Vaud"
    d["annee"] = 2026
    return d


def coeff_ge(par_nom):
    wb = openpyxl.load_workbook(GE_XLSX, read_only=True, data_only=True)
    ws = wb["Taux centimes add"]
    rows = list(ws.iter_rows(values_only=True))
    annees = [c for c in rows[1] if isinstance(c, int)]
    # colonnes des années, de la plus récente à la plus ancienne (repli)
    cols = sorted((rows[1].index(a), a) for a in annees)
    cols = [(i, a) for i, a in cols][::-1]
    idx_ge = par_nom["Genève"]
    out = []
    for r in rows[3:]:
        if not r[0] or str(r[0]).lower().startswith("total"):
            continue
        libelle = re.split(r"\d", str(r[0]))[0].strip()  # « Vernier 2026: ... » -> « Vernier »
        ofs = idx_ge.get(norm(libelle))
        if not ofs:
            continue
        # dernière année disponible (repli si valeur provisoire/absente, ex. Vernier 2026)
        for i, a in cols:
            if isinstance(r[i], (int, float)):
                out.append({"ofs": ofs, "nom": libelle.title(), "coefficient": float(r[i]),
                            "canton": "Genève", "annee": int(a)})
                break
    return pd.DataFrame(out)


def coeff_fr():
    d = pd.read_csv(FR_CSV, sep=";",
                    usecols=["annee", "commune", "commune_id", "coefficients", "valeur"])
    d = d[d["coefficients"].str.contains("revenu et la fortune", na=False)]
    d = d[d["annee"] == d["annee"].max()]
    d = d.rename(columns={"commune_id": "ofs", "commune": "nom", "valeur": "coefficient"})
    d["ofs"] = d["ofs"].astype(str)
    d["canton"] = "Fribourg"
    return d[["ofs", "nom", "coefficient", "canton", "annee"]]


def main():
    par_nom, ofs2canton, _ = communes_par_canton()
    df = pd.concat([coeff_vd(), coeff_ge(par_nom), coeff_fr()], ignore_index=True)
    # ne garder que les communes réellement dans notre périmètre (3 cantons)
    df = df[df["ofs"].isin(ofs2canton)]
    df = df.drop_duplicates("ofs").sort_values(["canton", "nom"])
    OUT.write_text(df.to_csv(index=False), encoding="utf-8")

    print(f"✅ {len(df)} communes écrites dans {OUT}")
    for canton, g in df.groupby("canton"):
        print(f"   {canton:9} : {len(g):3} communes · coeff {g['coefficient'].min():.0f}"
              f"–{g['coefficient'].max():.0f} (méd. {g['coefficient'].median():.0f}) · "
              f"année {int(g['annee'].max())}")


if __name__ == "__main__":
    main()
