"""
Étape 5 — Immobilier : prix indicatif au m² sur une short-list de communes.

⚠️ Prix INDICATIFS (appartements, ~2025) collectés via recherche web sur des
portails (RealAdvisor, Neho, Comparis...). Les prix de transaction par commune
ne sont pas publics en Suisse. À utiliser comme ordre de grandeur, pas comme
valeur officielle. Source éditable : data/raw/prix_m2_manuel.csv
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
IMMO = ROOT / "data/processed/immobilier_vd.csv"

st.set_page_config(page_title="Immobilier VD", page_icon="🏗️", layout="wide")
st.title("🏗️ Immobilier — prix indicatif au m² (short-list)")
st.caption("Prix indicatifs appartements ~2025 (portails via recherche web) · "
           "short-list de communes prioritaires")

st.warning(
    "**Prix indicatifs et non officiels.** Les prix de transaction par commune ne sont "
    "pas en open data en Suisse. Ces valeurs (appartements, ~2025) viennent de portails "
    "immobiliers via recherche web : à prendre comme **ordre de grandeur**. Pour un pitch "
    "engageant, faire valider par une source pro (Wüest/FPRE) ou un courtier local."
)


@st.cache_data
def load(_sig):
    geo = json.loads(GEO.read_text(encoding="utf-8"))
    df = pd.read_csv(IMMO, dtype={"ofs": str})
    return geo, df


geo, df = load(tuple(p.stat().st_mtime for p in (GEO, IMMO)))
avec_prix = df.dropna(subset=["prix_m2_appart"])
vals = dict(zip(avec_prix["ofs"], avec_prix["prix_m2_appart"]))
infos = df.set_index("ofs").to_dict("index")

colmap = cm.linear.YlOrRd_09.scale(min(vals.values()), max(vals.values()))
colmap.caption = "Prix indicatif appartement (CHF/m²)"

col1, col2 = st.columns([3, 1])
with col2:
    st.metric("Communes avec prix", len(avec_prix))
    st.metric("Prix médian (short-list)", f"{avec_prix['prix_m2_appart'].median():,.0f} CHF/m²".replace(",", "'"))
    st.metric("Min / Max", f"{avec_prix['prix_m2_appart'].min():,.0f} / {avec_prix['prix_m2_appart'].max():,.0f}".replace(",", "'"))
    st.caption("💡 Croise prix bas + forte demande seniors + bon pouvoir d'achat "
               "= terrain d'opportunité (ex : Yverdon, Gland, Epalinges).")

with col1:
    m = folium.Map(location=[46.55, 6.6], zoom_start=10, tiles="CartoDB positron")
    for f in geo["features"]:
        o = f["properties"]["ofs"]
        inf = infos.get(o, {})
        f["properties"]["prix"] = vals.get(o)
        f["properties"]["nom_t"] = f["properties"]["nom"]
        f["properties"]["pop80"] = int(inf["pop_80plus"]) if inf.get("pop_80plus") == inf.get("pop_80plus") and inf.get("pop_80plus") is not None else None
        f["properties"]["pa"] = inf.get("indice_pouvoir_achat")

    folium.GeoJson(
        geo,
        style_function=lambda ft: {
            "fillColor": colmap(ft["properties"]["prix"]) if ft["properties"]["prix"] else "#e8e8e8",
            "color": "#bbb", "weight": 0.4,
            "fillOpacity": 0.85 if ft["properties"]["prix"] else 0.15,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["nom_t", "prix", "pop80", "pa"],
            aliases=["Commune :", "Prix CHF/m² :", "Pop. 80+ :", "Pouvoir d'achat :"]),
    ).add_to(m)
    colmap.add_to(m)
    st_folium(m, width=None, height=560, returned_objects=[])

st.subheader("📋 Short-list — prix vs demande vs pouvoir d'achat")
tab = avec_prix[["nom", "district", "prix_m2_appart", "pop_80plus",
                 "indice_pouvoir_achat", "revenu_median_est", "prix_date"]].rename(columns={
    "nom": "Commune", "district": "District", "prix_m2_appart": "Prix CHF/m²",
    "pop_80plus": "Pop. 80+", "indice_pouvoir_achat": "Pouvoir d'achat",
    "revenu_median_est": "Revenu médian", "prix_date": "Année prix"})
st.dataframe(tab, hide_index=True, use_container_width=True)
st.caption("Pour ajouter/corriger une commune : éditer data/raw/prix_m2_manuel.csv "
           "puis relancer `python scripts/04d_build_immobilier.py`.")
