"""
Étape 1 — Carte interactive des communes vaudoises.

Affiche les ~300 communes du canton de Vaud avec leurs limites officielles.
Survole une commune pour voir son nom, son district et son numéro OFS.
Filtre possible par district dans la barre latérale.
"""

import json
from pathlib import Path

import folium
import streamlit as st

import brand
from streamlit_folium import st_folium

# Chemin robuste : remonte à la racine du projet depuis ce fichier
PROJECT_ROOT = Path(__file__).resolve().parents[2]
GEOJSON_PATH = PROJECT_ROOT / "data" / "processed" / "communes_vd.geojson"

brand.page_header("🗺️", "Carte des communes",
                  "Les 300 communes vaudoises et leurs limites officielles.", "OFS · 2025")


@st.cache_data
def load_communes():
    """Charge le GeoJSON (mis en cache pour ne pas relire à chaque interaction)."""
    return json.loads(GEOJSON_PATH.read_text(encoding="utf-8"))


geo = load_communes()
features = geo["features"]

# --- Filtre par district ---
districts = sorted({f["properties"]["district"] for f in features})
choix = st.sidebar.multiselect(
    "Filtrer par district",
    options=districts,
    default=districts,
    help="Décoche des districts pour n'afficher que certaines zones.",
)

features_filtrees = [f for f in features if f["properties"]["district"] in choix]
geo_filtre = {"type": "FeatureCollection", "features": features_filtrees}

col1, col2 = st.columns([3, 1])

with col2:
    st.metric("Communes affichées", len(features_filtrees))
    st.metric("Districts", len(choix))
    st.info(
        "👉 **Survole** une commune pour voir son nom, son district et son **numéro OFS** "
        "(la clé qui reliera bientôt la démographie, la concurrence, etc.)."
    )

with col1:
    # Carte centrée sur le canton de Vaud
    m = folium.Map(location=[46.6, 6.6], zoom_start=9, tiles="CartoDB positron")

    folium.GeoJson(
        geo_filtre,
        name="Communes VD",
        style_function=lambda _: {
            "fillColor": "#4C78A8",
            "color": "#2C3E50",
            "weight": 1,
            "fillOpacity": 0.35,
        },
        highlight_function=lambda _: {"fillOpacity": 0.7, "weight": 2},
        tooltip=folium.GeoJsonTooltip(
            fields=["nom", "district", "ofs"],
            aliases=["Commune :", "District :", "N° OFS :"],
            sticky=True,
        ),
    ).add_to(m)

    st_folium(m, width=None, height=600, returned_objects=[])
