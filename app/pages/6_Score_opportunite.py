"""
Étape 6 — Score d'opportunité d'investissement (interactif).

Combine 4 sous-scores (0-100) avec des POIDS AJUSTABLES en direct :
  demande (seniors 80+), sous-offre (tension EMS au niveau district),
  pouvoir d'achat (commune), faisabilité immo (prix/m², short-list).
Le score final est recalculé à la volée -> idéal pour tester des thèses en pitch.
"""

import json
from pathlib import Path

import branca.colormap as cm
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

ROOT = Path(__file__).resolve().parents[2]
GEO = ROOT / "data/processed/communes_vd.geojson"
SCORE = ROOT / "data/processed/score_opportunite_vd.csv"

st.set_page_config(page_title="Score d'opportunité", page_icon="🎯", layout="wide")
st.title("🎯 Score d'opportunité d'investissement")
st.caption("Synthèse interactive : démographie + concurrence EMS + pouvoir d'achat + immobilier")

SOUS_SCORES = {
    "demande_score": "Demande (seniors 80+)",
    "sous_offre_score": "Sous-offre EMS (district)",
    "pouvoir_achat_score": "Pouvoir d'achat",
    "faisabilite_score": "Faisabilité immo (prix bas)",
}


@st.cache_data
def load(_sig):
    geo = json.loads(GEO.read_text(encoding="utf-8"))
    df = pd.read_csv(SCORE, dtype={"ofs": str})
    return geo, df


geo, df = load(tuple(p.stat().st_mtime for p in (GEO, SCORE)))

# --- Réglages ---
st.sidebar.header("⚖️ Pondération des critères")
w = {
    "demande_score": st.sidebar.slider("Demande (seniors 80+)", 0, 100, 40, 5),
    "sous_offre_score": st.sidebar.slider("Sous-offre EMS (district)", 0, 100, 25, 5),
    "pouvoir_achat_score": st.sidebar.slider("Pouvoir d'achat", 0, 100, 20, 5),
    "faisabilite_score": st.sidebar.slider("Faisabilité immo (prix bas)", 0, 100, 15, 5),
}
st.sidebar.caption("Les poids sont relatifs (normalisés automatiquement).")
pop_min = st.sidebar.slider("Population minimale de la commune", 0, 5000, 1500, 250)
immo_only = st.sidebar.checkbox("Uniquement les communes avec prix immo (short-list)", False)

# --- Calcul du score pondéré (renormalisé sur les sous-scores disponibles) ---
num = pd.Series(0.0, index=df.index)
den = pd.Series(0.0, index=df.index)
for col, poids in w.items():
    if poids == 0:
        continue
    dispo = df[col].notna()
    num += (df[col].fillna(0) * poids) * dispo
    den += poids * dispo
df["score"] = (num / den.replace(0, pd.NA)).round(1)

mask = df["pop_totale"].fillna(0) >= pop_min
if immo_only:
    mask &= df["faisabilite_score"].notna()
dff = df[mask].dropna(subset=["score"]).copy()

vals = dict(zip(dff["ofs"], dff["score"]))
infos = df.set_index("ofs").to_dict("index")
colmap = cm.linear.RdYlGn_09.scale(dff["score"].min(), dff["score"].max())
colmap.caption = "Score d'opportunité"

col1, col2 = st.columns([3, 1])
with col2:
    st.metric("Communes classées", len(dff))
    if len(dff):
        best = dff.nlargest(1, "score").iloc[0]
        st.metric("N°1", best["nom"], f"score {best['score']}")
    st.markdown("**🏆 Top 10**")
    for i, (_, r) in enumerate(dff.nlargest(10, "score").iterrows(), 1):
        st.write(f"{i}. {r['nom']} — **{r['score']}**")

with col1:
    m = folium.Map(location=[46.6, 6.6], zoom_start=9, tiles="CartoDB positron")
    for f in geo["features"]:
        o = f["properties"]["ofs"]
        inf = infos.get(o, {})
        f["properties"]["v"] = vals.get(o)
        f["properties"]["nom_t"] = f["properties"]["nom"]
        f["properties"]["sc"] = inf.get("score")
        f["properties"]["d80"] = int(inf["pop_80plus"]) if pd.notna(inf.get("pop_80plus")) else None
        f["properties"]["pa"] = inf.get("pouvoir_achat_score")
    folium.GeoJson(
        geo,
        style_function=lambda ft: {
            "fillColor": colmap(ft["properties"]["v"]) if ft["properties"]["v"] is not None else "#eeeeee",
            "color": "#999", "weight": 0.4,
            "fillOpacity": 0.82 if ft["properties"]["v"] is not None else 0.15,
        },
        highlight_function=lambda _: {"weight": 2, "color": "black"},
        tooltip=folium.GeoJsonTooltip(
            fields=["nom_t", "sc", "d80", "pa"],
            aliases=["Commune :", "Score :", "Pop. 80+ :", "Pouvoir d'achat :"]),
    ).add_to(m)
    colmap.add_to(m)
    st_folium(m, width=None, height=560, returned_objects=[])

st.subheader("🏅 Classement des opportunités")
det = dff.nlargest(30, "score")[[
    "nom", "district", "score", "pop_80plus", "lits_pour_100_district",
    "pouvoir_achat_score", "prix_m2_appart"]].rename(columns={
    "nom": "Commune", "district": "District", "score": "Score",
    "pop_80plus": "Pop. 80+", "lits_pour_100_district": "Lits/100 (district)",
    "pouvoir_achat_score": "Pouvoir d'achat", "prix_m2_appart": "Prix CHF/m²"})
st.dataframe(det, hide_index=True, use_container_width=True)
st.caption("⚠️ Sous-offre = au niveau district (un EMS dessert une région). "
           "Faisabilité immo = short-list seulement (sinon le critère est ignoré et les "
           "poids sont redistribués). Outil d'aide à la décision, pas une vérité absolue.")
