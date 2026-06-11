"""
Étape 7 — Fiche pitch par commune (synthèse + export PDF).

Sélectionne une commune et obtient une fiche de synthèse prête pour un
investisseur : démographie, concurrence EMS, pouvoir d'achat, immobilier,
score d'opportunité. Export PDF en un clic.
"""

from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
from fpdf import FPDF

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "data/processed"

VD_OCCUPATION = 98  # % (INFOSAN/DGS 2024)

st.set_page_config(page_title="Fiche pitch", page_icon="📄", layout="wide")
st.title("📄 Fiche pitch — synthèse par commune")
st.caption("Tout ce qu'il faut pour présenter une localisation à un investisseur, en une page.")


@st.cache_data
def load(sig):
    demo = pd.read_csv(P / "demographie_vd.csv", dtype={"ofs": str})
    ems = pd.read_csv(P / "ems_vd.csv", dtype={"ofs": str})
    pa = pd.read_csv(P / "pouvoir_achat_vd.csv", dtype={"ofs": str})
    immo = pd.read_csv(P / "immobilier_vd.csv", dtype={"ofs": str})
    score = pd.read_csv(P / "score_opportunite_vd.csv", dtype={"ofs": str})
    return demo, ems, pa, immo, score


files = ["demographie_vd.csv", "ems_vd.csv", "pouvoir_achat_vd.csv",
         "immobilier_vd.csv", "score_opportunite_vd.csv"]
demo, ems, pa, immo, score = load(tuple((P / f).stat().st_mtime for f in files))

# Score pondéré (poids par défaut, alignés sur l'étape 6)
W = {"demande_score": 40, "sous_offre_score": 25, "pouvoir_achat_score": 20, "faisabilite_score": 15}
num = pd.Series(0.0, index=score.index); den = pd.Series(0.0, index=score.index)
for c, p in W.items():
    d = score[c].notna(); num += score[c].fillna(0) * p * d; den += p * d
score = score.assign(score=(num / den.replace(0, pd.NA)).round(1))
score["rang"] = score["score"].rank(ascending=False, method="min")

# --- Sélection commune ---
noms = demo.sort_values("nom")["nom"].tolist()
defaut = noms.index("Yverdon-les-Bains") if "Yverdon-les-Bains" in noms else 0
nom_sel = st.selectbox("Choisis une commune", noms, index=defaut)
ofs = demo.loc[demo["nom"] == nom_sel, "ofs"].iloc[0]


def fiche_commune(ofs):
    d = demo[demo["ofs"] == ofs].iloc[0]
    s = score[score["ofs"] == ofs].iloc[0]
    p = pa[pa["ofs"] == ofs]
    p = p.iloc[0] if len(p) else None
    im = immo[immo["ofs"] == ofs]
    im = im.iloc[0] if len(im) else None
    ems_c = ems[(ems["ofs"] == ofs)].dropna(subset=["lits"])
    return d, s, p, im, ems_c


d, s, p, im, ems_c = fiche_commune(ofs)
nb_ems = len(ems_c)
lits_commune = int(ems_c["lits"].sum()) if nb_ems else 0

# Repères cantonaux
cant_part80 = demo["pop_80plus"].sum() / demo["pop_totale"].sum() * 100
cant_revenu = pa["revenu_median_est"].median()

# --- Affichage ---
st.header(f"{nom_sel}  —  district de {d['district']}")
st.caption(f"N° OFS {ofs} · Fiche générée le {date.today():%d.%m.%Y}")

c1, c2, c3 = st.columns(3)
c1.metric("Score d'opportunité", f"{s['score']:.0f}/100", f"rang {int(s['rang'])}/300")
c2.metric("Population", f"{int(d['pop_totale']):,}".replace(",", "'"))
c3.metric("Seniors 80+", f"{int(d['pop_80plus']):,}".replace(",", "'"),
          f"{d['part_80plus']:.1f}% (canton {cant_part80:.1f}%)")

st.subheader("👴 Démographie & demande")
a, b, c = st.columns(3)
a.metric("65+", f"{int(d['pop_65plus']):,}".replace(",", "'"), f"{d['part_65plus']:.1f}%")
b.metric("80+", f"{int(d['pop_80plus']):,}".replace(",", "'"), f"{d['part_80plus']:.1f}%")
c.metric("Sous-offre EMS (district)", f"{s['sous_offre_score']:.0f}/100")

st.subheader("🏥 Concurrence (offre EMS)")
a, b, c = st.columns(3)
a.metric("EMS dans la commune", nb_ems)
b.metric("Lits dans la commune", lits_commune)
c.metric("Occupation cantonale", f"{VD_OCCUPATION}%", "marché saturé")
if nb_ems:
    st.caption("EMS recensés : " + ", ".join(
        f"{r.nom_clean} ({int(r.lits)} lits)" for r in ems_c.itertuples()))

st.subheader("💰 Pouvoir d'achat")
if p is not None:
    a, b, c = st.columns(3)
    rev = p["revenu_median_est"]
    a.metric("Revenu médian estimé", f"{rev:,.0f} CHF".replace(",", "'") if pd.notna(rev) else "n/d",
             f"canton {cant_revenu:,.0f}".replace(",", "'"))
    b.metric("Indice pouvoir d'achat", f"{p['indice_pouvoir_achat']:.0f}/100" if pd.notna(p['indice_pouvoir_achat']) else "n/d")
    c.metric("Fortune moy. (district)", f"{p['fortune_moy_chf']:,.0f} CHF".replace(",", "'") if pd.notna(p.get('fortune_moy_chf')) else "n/d")

st.subheader("🏗️ Immobilier")
if im is not None and pd.notna(im["prix_m2_appart"]):
    st.metric("Prix indicatif appartement", f"{im['prix_m2_appart']:,.0f} CHF/m²".replace(",", "'"),
              "indicatif, non officiel")
else:
    st.info("Pas de prix immobilier indicatif pour cette commune (hors short-list). "
            "Ajoutable dans data/raw/prix_m2_manuel.csv.")


# --- Export PDF ---
def latin(t):
    return (str(t).replace("’", "'").replace("–", "-").replace("œ", "oe")
            .replace(" ", " ").encode("latin-1", "replace").decode("latin-1"))


def make_pdf():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, latin(f"Fiche investissement - {nom_sel}"), ln=1)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(110)
    pdf.cell(0, 6, latin(f"District de {d['district']} · N° OFS {ofs} · "
                         f"{date.today():%d.%m.%Y} · Senior Invest CH"), ln=1)
    pdf.set_text_color(0)
    pdf.ln(3)

    def section(titre, lignes):
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_fill_color(235, 240, 245)
        pdf.cell(0, 8, latin(titre), ln=1, fill=True)
        pdf.set_font("Helvetica", "", 11)
        for lab, val in lignes:
            pdf.cell(95, 7, latin(lab))
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 7, latin(val), ln=1)
            pdf.set_font("Helvetica", "", 11)
        pdf.ln(2)

    section("Score d'opportunite", [
        ("Score global (poids 40/25/20/15)", f"{s['score']:.0f}/100  (rang {int(s['rang'])}/300)"),
        ("  Demande (seniors)", f"{s['demande_score']:.0f}/100"),
        ("  Sous-offre EMS (district)", f"{s['sous_offre_score']:.0f}/100"),
        ("  Pouvoir d'achat", f"{s['pouvoir_achat_score']:.0f}/100"),
        ("  Faisabilite immo", f"{s['faisabilite_score']:.0f}/100" if pd.notna(s['faisabilite_score']) else "n/d"),
    ])
    section("Demographie (OFS 2024)", [
        ("Population totale", f"{int(d['pop_totale']):,}".replace(",", "'")),
        ("Seniors 65+", f"{int(d['pop_65plus']):,} ({d['part_65plus']:.1f}%)".replace(",", "'")),
        ("Seniors 80+", f"{int(d['pop_80plus']):,} ({d['part_80plus']:.1f}%)".replace(",", "'")),
        ("Part 80+ canton", f"{cant_part80:.1f}%"),
    ])
    section("Concurrence EMS", [
        ("EMS dans la commune", str(nb_ems)),
        ("Lits dans la commune", str(lits_commune)),
        ("Taux d'occupation cantonal", f"{VD_OCCUPATION}% (marche sature)"),
    ])
    if p is not None:
        section("Pouvoir d'achat", [
            ("Revenu median estime", f"{p['revenu_median_est']:,.0f} CHF".replace(",", "'") if pd.notna(p['revenu_median_est']) else "n/d"),
            ("Indice pouvoir d'achat", f"{p['indice_pouvoir_achat']:.0f}/100" if pd.notna(p['indice_pouvoir_achat']) else "n/d"),
            ("Fortune moy. district", f"{p['fortune_moy_chf']:,.0f} CHF".replace(",", "'") if pd.notna(p.get('fortune_moy_chf')) else "n/d"),
        ])
    prix = f"{im['prix_m2_appart']:,.0f} CHF/m2 (indicatif)".replace(",", "'") if (im is not None and pd.notna(im["prix_m2_appart"])) else "n/d"
    section("Immobilier", [("Prix appartement", prix)])

    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(120)
    pdf.multi_cell(0, 4, latin(
        "Sources : OFS (demographie, revenu IFD 2022), liste LAMal VD 2024 (EMS/lits), "
        "StatVD/vd.ch (fiscalite, fortune), portails immobiliers (prix indicatifs ~2025). "
        "Prix immobiliers et fortune (district) indicatifs - a valider avant engagement. "
        "Document d'aide a la decision."))
    return bytes(pdf.output())


st.divider()
st.download_button(
    "📥 Télécharger la fiche en PDF",
    data=make_pdf(),
    file_name=f"fiche_{nom_sel.replace(' ', '_').replace('(', '').replace(')', '')}.pdf",
    mime="application/pdf",
    type="primary",
)
st.caption("⚠️ Synthèse d'aide à la décision. Prix immobiliers et fortune (district) "
           "indicatifs ; EMS géolocalisés à ~83 %. À valider avant tout engagement.")
