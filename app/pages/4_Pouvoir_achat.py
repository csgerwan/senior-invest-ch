"""
Étape 4 — Pouvoir d'achat par commune.

Carte choroplèthe combinant revenu (ESTV 2022, par commune), charge fiscale
communale (coefficient d'impôt 2026, par commune) et fortune (StatVD, par district,
en contexte). Indice composite de pouvoir d'achat 0-100.
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
PA = ROOT / "data/processed/pouvoir_achat_vd.csv"

st.set_page_config(page_title="Pouvoir d'achat VD", page_icon="💰", layout="wide")
st.title("💰 Pouvoir d'achat — Canton de Vaud")
st.caption("Revenu : impôt fédéral direct ESTV 2022 (par commune) · "
           "Charge fiscale : coefficient communal 2026 · "
           "Fortune : StatVD 2022 (par district)")

# (libellé, colonne, format, légende, plus c'est haut = mieux ?)
INDICATEURS = {
    "Indice de pouvoir d'achat (0-100)": ("indice_pouvoir_achat", "{:.0f}", "Indice composite", True),
    "Revenu net médian estimé (CHF)": ("revenu_median_est", "{:,.0f}", "Revenu médian (CHF)", True),
    "Part de hauts revenus (>100k, %)": ("part_haut_revenu", "{:.1f}", "Part >100k CHF (%)", True),
    "Charge fiscale (coefficient communal)": ("coefficient", "{:.0f}", "Coefficient d'impôt", False),
    "Fortune moy./contribuable — district (CHF)": ("fortune_moy_chf", "{:,.0f}", "Fortune district (CHF)", True),
}


@st.cache_data
def load(sig):  # sig = mtime des fichiers -> rafraîchit le cache si maj
    geo = json.loads(GEO.read_text(encoding="utf-8"))
    df = pd.read_csv(PA, dtype={"ofs": str})
    return geo, df


geo, df = load(tuple(p.stat().st_mtime for p in (GEO, PA)))

libelle = st.sidebar.selectbox("Indicateur à cartographier", list(INDICATEURS.keys()))
col, fmt, cap, plus_mieux = INDICATEURS[libelle]

dfx = df.dropna(subset=[col])
vals = dict(zip(dfx["ofs"], dfx[col]))
infos = df.set_index("ofs").to_dict("index")

# Échelle vert->rouge ; inversée si "plus c'est haut = moins bien" (charge fiscale)
vmin, vmax = min(vals.values()), max(vals.values())
colormap = (cm.linear.RdYlGn_09.scale(vmin, vmax) if plus_mieux
            else cm.linear.RdYlGn_09.scale(vmax, vmin))
colormap.caption = cap + ("" if plus_mieux else " (élevé = plus taxé)")

col1, col2 = st.columns([3, 1])

with col2:
    st.metric("Communes avec indice", int(df["indice_pouvoir_achat"].notna().sum()))
    st.metric("Revenu médian (canton)", f"{df['revenu_median_est'].median():,.0f} CHF".replace(",", "'"))
    st.metric("Coefficient médian", f"{df['coefficient'].median():.0f}")
    st.markdown(f"**Top 5 — {libelle.split('(')[0].strip()}**")
    asc = not plus_mieux
    for _, r in dfx.sort_values(col, ascending=asc).head(5).iterrows():
        st.write(f"• {r['nom']} — **{fmt.format(r[col]).replace(',', chr(39))}**")

with col1:
    m = folium.Map(location=[46.6, 6.6], zoom_start=9, tiles="CartoDB positron")

    for f in geo["features"]:
        o = f["properties"]["ofs"]
        inf = infos.get(o, {})
        f["properties"]["v"] = vals.get(o)
        f["properties"]["nom_t"] = f["properties"]["nom"]
        f["properties"]["indice"] = inf.get("indice_pouvoir_achat")
        f["properties"]["revenu"] = inf.get("revenu_median_est")
        f["properties"]["coeff"] = inf.get("coefficient")
        f["properties"]["fortune"] = inf.get("fortune_moy_chf")

    folium.GeoJson(
        geo,
        style_function=lambda ft: {
            "fillColor": colormap(ft["properties"]["v"]) if ft["properties"]["v"] is not None else "#dddddd",
            "color": "#888", "weight": 0.4, "fillOpacity": 0.8,
        },
        highlight_function=lambda _: {"weight": 2, "color": "black"},
        tooltip=folium.GeoJsonTooltip(
            fields=["nom_t", "indice", "revenu", "coeff", "fortune"],
            aliases=["Commune :", "Indice :", "Revenu médian :",
                     "Coefficient :", "Fortune district :"]),
    ).add_to(m)
    colormap.add_to(m)
    st_folium(m, width=None, height=600, returned_objects=[])

st.caption("⚠️ Revenu = impôt fédéral direct (sous-estime les bas revenus, millésime 2022). "
           "Fortune = moyenne par district (pas par commune ; toutes les communes d'un district "
           "partagent la valeur). Indice composite = revenu + charge fiscale (indicateurs communaux).")

# --- Tableau complet ---
with st.expander("📋 Voir le tableau complet par commune"):
    st.dataframe(
        df[["nom", "district", "indice_pouvoir_achat", "revenu_median_est",
            "part_haut_revenu", "coefficient", "fortune_moy_chf"]].rename(columns={
            "nom": "Commune", "district": "District",
            "indice_pouvoir_achat": "Indice", "revenu_median_est": "Revenu médian",
            "part_haut_revenu": "% >100k", "coefficient": "Coeff. impôt",
            "fortune_moy_chf": "Fortune district"}),
        hide_index=True, use_container_width=True)
