"""
Étape 3 — Concurrence : les EMS face à la demande senior.

Superpose les EMS (offre) sur la part de 80+ par commune (demande), et calcule
un PROXY DE TENSION = nb de personnes de 80+ par lit d'EMS dans la commune.
Plus le ratio est élevé, plus l'offre locale est sous pression (estimation).
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
DEMO = ROOT / "data/processed/demographie_vd.csv"
EMS = ROOT / "data/processed/ems_vd.csv"

# Chiffres officiels cantonaux (INFOSAN / DGS Vaud, 2024) — contexte pitch
VD_LITS_TOTAL = 6986
VD_TAUX_OCCUPATION = 98  # %

st.set_page_config(page_title="Concurrence EMS", page_icon="🏥", layout="wide")
st.title("🏥 Concurrence — EMS face à la demande senior")
st.caption("EMS : OpenStreetMap (partiel) · Démographie : OFS 2024 · "
           "Lits/occupation canton : INFOSAN/DGS Vaud 2024")


@st.cache_data
def load():
    geo = json.loads(GEO.read_text(encoding="utf-8"))
    demo = pd.read_csv(DEMO, dtype={"ofs": str})
    ems = pd.read_csv(EMS, dtype={"ofs": str})
    return geo, demo, ems


geo, demo, ems = load()

ems_geo = ems.dropna(subset=["lat", "lon"])
lits_dispo = ems["lits"].notna().any() and ems["lits"].fillna(0).sum() > 0

# --- Bandeau d'avertissement sur la complétude des données ---
if not lits_dispo:
    st.warning(
        f"**Données EMS partielles** : {len(ems_geo)} EMS localisés (source OpenStreetMap), "
        "**sans nombre de lits**. Le proxy de tension par commune s'affichera dès qu'on "
        "aura branché la liste officielle DGS (lits par EMS) via `data/raw/ems_vd_source.csv`. "
        f"En attendant : repère officiel cantonal = **{VD_LITS_TOTAL:,} lits**, "
        f"**{VD_TAUX_OCCUPATION}% d'occupation**.".replace(",", "'")
    )

# --- Agrégat EMS par commune ---
par_commune = ems_geo.groupby("ofs").agg(
    nb_ems=("nom", "count"),
    lits_commune=("lits", "sum"),
).reset_index()
d = demo.merge(par_commune, on="ofs", how="left")
d["nb_ems"] = d["nb_ems"].fillna(0).astype(int)
d["lits_commune"] = d["lits_commune"].fillna(0)

# Proxy de tension (si lits dispo) sinon indicateur de repli = nb d'EMS
if lits_dispo:
    d["tension"] = (d["pop_80plus"] / d["lits_commune"].replace(0, pd.NA)).round(1)
    indic_col, indic_lbl = "tension", "Tension : 80+ par lit d'EMS (estimation)"
else:
    indic_col, indic_lbl = "nb_ems", "Nombre d'EMS localisés (OSM, partiel)"

infos = d.set_index("ofs").to_dict("index")

# --- Couches carte ---
col1, col2 = st.columns([3, 1])

with col2:
    st.metric("EMS localisés", len(ems_geo))
    st.metric("Lits (canton, officiel)", f"{VD_LITS_TOTAL:,}".replace(",", "'"))
    st.metric("Occupation (canton)", f"{VD_TAUX_OCCUPATION} %")
    ratio = VD_LITS_TOTAL / demo["pop_80plus"].sum() * 100
    st.metric("Lits pour 100 pers. de 80+", f"{ratio:.0f}")
    st.info("💡 Pitch : 98% d'occupation = marché saturé. "
            "Croise les communes foncées (forte part 80+) avec le manque d'EMS = opportunité.")

with col1:
    m = folium.Map(location=[46.6, 6.6], zoom_start=9, tiles="CartoDB positron")

    # Fond : part des 80+ (la demande)
    vals = dict(zip(demo["ofs"], demo["part_80plus"]))
    cmap = cm.linear.YlOrRd_09.scale(min(vals.values()), max(vals.values()))
    cmap.caption = "Part des 80+ (%) — la demande"
    for f in geo["features"]:
        f["properties"]["part_80plus"] = vals.get(f["properties"]["ofs"])
        f["properties"]["nb_ems"] = infos.get(f["properties"]["ofs"], {}).get("nb_ems", 0)

    folium.GeoJson(
        geo,
        style_function=lambda ft: {
            "fillColor": cmap(ft["properties"]["part_80plus"]),
            "color": "#999", "weight": 0.4, "fillOpacity": 0.7,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["nom", "part_80plus", "nb_ems"],
            aliases=["Commune :", "Part 80+ (%) :", "EMS (OSM) :"],
        ),
    ).add_to(m)
    cmap.add_to(m)

    # Points : EMS (l'offre)
    for _, e in ems_geo.iterrows():
        lits = f" — {int(e['lits'])} lits" if pd.notna(e["lits"]) else ""
        folium.CircleMarker(
            [e["lat"], e["lon"]], radius=4, color="#1a5276",
            fill=True, fill_color="#2980b9", fill_opacity=0.9,
            tooltip=f"{e['nom']}{lits}",
        ).add_to(m)

    st_folium(m, width=None, height=600, returned_objects=[])

# --- Tableau : communes à fort potentiel (forte demande, peu/pas d'EMS) ---
st.subheader("🎯 Communes à creuser (forte part de 80+ et peu d'EMS recensés)")
cibles = d[d["pop_totale"] >= 1500].sort_values(
    ["nb_ems", "part_80plus"], ascending=[True, False]
).head(12)
st.dataframe(
    cibles[["nom", "pop_totale", "part_80plus", "pop_80plus", "nb_ems"]].rename(columns={
        "nom": "Commune", "pop_totale": "Population", "part_80plus": "Part 80+ (%)",
        "pop_80plus": "Nombre 80+", "nb_ems": "EMS (OSM)",
    }),
    hide_index=True, use_container_width=True,
)
st.caption("⚠️ « EMS (OSM) » est partiel : une commune à 0 peut avoir un EMS non recensé. "
           "À fiabiliser avec la liste officielle DGS.")
