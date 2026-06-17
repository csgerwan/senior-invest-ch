"""
Étape 2 — Démographie & vieillissement (carte choroplèthe).

Colore chaque commune vaudoise selon un indicateur de vieillissement choisi.
Plus une commune est foncée, plus sa population senior est importante.
"""

import json
from pathlib import Path

import branca.colormap as cm
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GEOJSON_PATH = PROJECT_ROOT / "data" / "processed" / "communes_vd.geojson"
DEMO_PATH = PROJECT_ROOT / "data" / "processed" / "demographie_vd.csv"

st.title("📊 Démographie & vieillissement — Canton de Vaud")
st.caption("Source : OFS / STAT-TAB (px-x-0102010000_103), population résidante permanente 2024")

# Indicateurs proposés : (libellé, colonne, unité)
INDICATEURS = {
    "Part des 80+ (%)": ("part_80plus", "%"),
    "Part des 65+ (%)": ("part_65plus", "%"),
    "Nombre de 80+ (habitants)": ("pop_80plus", "hab."),
    "Nombre de 65+ (habitants)": ("pop_65plus", "hab."),
}


@st.cache_data
def load_data(sig):  # sig = mtime des fichiers -> rafraîchit le cache si maj
    geo = json.loads(GEOJSON_PATH.read_text(encoding="utf-8"))
    demo = pd.read_csv(DEMO_PATH, dtype={"ofs": str})
    return geo, demo


geo, demo = load_data(tuple(p.stat().st_mtime for p in (GEOJSON_PATH, DEMO_PATH)))

# --- Choix de l'indicateur ---
libelle = st.sidebar.selectbox("Indicateur à cartographier", list(INDICATEURS.keys()))
colonne, unite = INDICATEURS[libelle]
min_hab = st.sidebar.slider(
    "Taille min. de commune (habitants)", 0, 5000, 0, step=250,
    help="Masque les très petites communes où les pourcentages sont volatils.",
)

demo_f = demo[demo["pop_totale"] >= min_hab].copy()
valeurs = dict(zip(demo_f["ofs"], demo_f[colonne]))
infos = demo_f.set_index("ofs").to_dict("index")

# Injecte les valeurs dans le GeoJSON pour l'infobulle
features_aff = []
for f in geo["features"]:
    ofs = f["properties"]["ofs"]
    if ofs in infos:
        d = infos[ofs]
        f["properties"].update({
            "valeur": valeurs[ofs],
            "pop_totale": int(d["pop_totale"]),
            "part_65plus": d["part_65plus"],
            "part_80plus": d["part_80plus"],
            "pop_65plus": int(d["pop_65plus"]),
            "pop_80plus": int(d["pop_80plus"]),
        })
        features_aff.append(f)
geo_aff = {"type": "FeatureCollection", "features": features_aff}

# --- Échelle de couleurs ---
vmin = min(valeurs.values())
vmax = max(valeurs.values())
colormap = cm.linear.YlOrRd_09.scale(vmin, vmax)
colormap.caption = libelle

col1, col2 = st.columns([3, 1])

with col2:
    tot = demo_f["pop_totale"].sum()
    st.metric("Population (communes affichées)", f"{tot:,.0f}".replace(",", "'"))
    st.metric("Part 65+", f"{demo_f['pop_65plus'].sum() / tot * 100:.1f} %")
    st.metric("Part 80+", f"{demo_f['pop_80plus'].sum() / tot * 100:.1f} %")
    st.markdown("**Top 5 communes** — " + libelle)
    top = demo_f.nlargest(5, colonne)[["nom", colonne]]
    for _, r in top.iterrows():
        st.write(f"• {r['nom']} — **{r[colonne]:g} {unite}**")

with col1:
    m = folium.Map(location=[46.6, 6.6], zoom_start=9, tiles="CartoDB positron")

    def style(feat):
        return {
            "fillColor": colormap(feat["properties"]["valeur"]),
            "color": "#555",
            "weight": 0.5,
            "fillOpacity": 0.8,
        }

    folium.GeoJson(
        geo_aff,
        style_function=style,
        highlight_function=lambda _: {"weight": 2, "color": "black"},
        tooltip=folium.GeoJsonTooltip(
            fields=["nom", "pop_totale", "part_65plus", "part_80plus"],
            aliases=["Commune :", "Population :", "Part 65+ (%) :", "Part 80+ (%) :"],
            sticky=True,
        ),
    ).add_to(m)
    colormap.add_to(m)

    st_folium(m, width=None, height=600, returned_objects=[])

st.caption(
    "💡 Lecture pitch : une part de 80+ élevée signale une demande actuelle ; "
    "à croiser bientôt avec l'offre d'EMS (étape 3) pour repérer les zones sous-équipées."
)
