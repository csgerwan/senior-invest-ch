"""
Étape 6 — Score d'opportunité d'investissement (interactif, V1).

Croise 4 critères (sous-scores 0-100), pondérables en direct. Le classement met
en avant les communes où : la part de seniors est élevée, qui sont éloignées des
EMS existants, au pouvoir d'achat élevé et au prix immobilier bas.
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
st.caption("Croisement démographie × concurrence EMS × pouvoir d'achat × immobilier")

# critère -> (colonne sous-score, libellé, poids par défaut)
CRITERES = {
    "Part de seniors (80+) élevée": ("demande_score", 25),
    "Éloignement des EMS existants": ("eloignement_score", 25),
    "Pouvoir d'achat élevé": ("pouvoir_achat_score", 25),
    "Prix immobilier bas": ("prix_bas_score", 25),
}


@st.cache_data
def load(sig):
    geo = json.loads(GEO.read_text(encoding="utf-8"))
    df = pd.read_csv(SCORE, dtype={"ofs": str})
    return geo, df


try:
    geo, df = load(tuple(p.stat().st_mtime for p in (GEO, SCORE)))
except FileNotFoundError:
    st.error("Données du score introuvables. Lance d'abord `python scripts/06_build_score.py`.")
    st.stop()

# --- Pondération ---
st.sidebar.header("⚖️ Importance de chaque critère")
poids = {}
for libelle, (col, defaut) in CRITERES.items():
    poids[col] = st.sidebar.slider(libelle, 0, 100, defaut, 5)
st.sidebar.caption("Poids relatifs (normalisés automatiquement).")
pop_min = st.sidebar.slider("Population minimale de la commune", 0, 5000, 1500, 250)

# --- Score pondéré (renormalisé sur les sous-scores disponibles) ---
num = pd.Series(0.0, index=df.index)
den = pd.Series(0.0, index=df.index)
for col, p in poids.items():
    if p == 0:
        continue
    dispo = df[col].notna()
    num += df[col].fillna(0) * p * dispo
    den += p * dispo
df["score"] = (num / den.replace(0, pd.NA)).round(1)

dff = df[df["pop_totale"].fillna(0) >= pop_min].dropna(subset=["score"]).copy()
dff["rang"] = dff["score"].rank(ascending=False, method="min").astype(int)
vals = dict(zip(dff["ofs"], dff["score"]))
infos = df.set_index("ofs").to_dict("index")

if not vals:
    st.warning("Aucune commune ne correspond aux filtres. Baisse la population minimale.")
    st.stop()

colmap = cm.linear.RdYlGn_09.scale(dff["score"].min(), dff["score"].max())
colmap.caption = "Score d'opportunité"

col1, col2 = st.columns([3, 1])
with col2:
    st.metric("Communes classées", len(dff))
    best = dff.nlargest(1, "score").iloc[0]
    st.metric("N°1", best["nom"], f"score {best['score']}")
    st.markdown("**🏆 Top 10**")
    for _, r in dff.nsmallest(10, "rang").iterrows():
        st.write(f"{r['rang']}. {r['nom']} — **{r['score']}**")

with col1:
    m = folium.Map(location=[46.6, 6.6], zoom_start=9, tiles="CartoDB positron")
    for f in geo["features"]:
        o = f["properties"]["ofs"]
        inf = infos.get(o, {})
        f["properties"]["v"] = vals.get(o)
        f["properties"]["nom_t"] = f["properties"]["nom"]
        f["properties"]["sc"] = inf.get("score")
        f["properties"]["s80"] = inf.get("part_80plus")
        f["properties"]["dems"] = inf.get("dist_ems_km")
        f["properties"]["pa"] = inf.get("pouvoir_achat_score")
        f["properties"]["prix"] = inf.get("prix_m2_appart")
    folium.GeoJson(
        geo,
        style_function=lambda ft: {
            "fillColor": colmap(ft["properties"]["v"]) if ft["properties"]["v"] is not None else "#eeeeee",
            "color": "#999", "weight": 0.4,
            "fillOpacity": 0.82 if ft["properties"]["v"] is not None else 0.12,
        },
        highlight_function=lambda _: {"weight": 2.5, "color": "black"},
        tooltip=folium.GeoJsonTooltip(
            fields=["nom_t", "sc", "s80", "dems", "pa", "prix"],
            aliases=["Commune :", "Score :", "Part 80+ (%) :", "Dist. EMS (km) :",
                     "Pouvoir d'achat :", "Prix CHF/m² :"]),
    ).add_to(m)
    colmap.add_to(m)
    st_folium(m, width=None, height=560, returned_objects=[])

st.subheader("🏅 Classement des opportunités")
det = dff.nsmallest(30, "rang")[[
    "rang", "nom", "district", "score", "part_80plus", "dist_ems_km",
    "pouvoir_achat_score", "prix_m2_appart", "prix_fiabilite"]].rename(columns={
    "rang": "Rang", "nom": "Commune", "district": "District", "score": "Score",
    "part_80plus": "Part 80+ (%)", "dist_ems_km": "Dist. EMS (km)",
    "pouvoir_achat_score": "Pouvoir d'achat", "prix_m2_appart": "Prix CHF/m²",
    "prix_fiabilite": "Fiab. prix"})
st.dataframe(det, hide_index=True, use_container_width=True)
st.caption("Outil d'aide à la décision configurable. « Éloignement des EMS » = distance "
           "du centre de la commune à l'EMS le plus proche (loin = zone mal desservie). "
           "Prix immobilier indicatif (annonces / estimations) — voir page Immobilier.")
