"""
Étape 3 — Concurrence : les EMS face à la demande senior.

Données EMS : liste officielle LAMal 2025 du canton (165 établissements + lits),
géolocalisée (cf. scripts 03a et 03). Superpose l'offre (EMS) sur la demande
(part de 80+) et calcule un PROXY DE TENSION par commune :
    tension = personnes de 80+ / lits d'EMS de la commune
Plus le ratio est élevé, plus l'offre locale est sous pression (estimation).
"""

import json
from pathlib import Path

import branca.colormap as cm
import folium
import pandas as pd
import streamlit as st

import brand
from streamlit_folium import st_folium

ROOT = Path(__file__).resolve().parents[2]
GEO = ROOT / "data/processed/communes_vd.geojson"
DEMO = ROOT / "data/processed/demographie_vd.csv"
EMS = ROOT / "data/processed/ems.csv"  # unifié VD+GE+FR

# Repère d'occupation (référence vaudoise, INFOSAN / DGS Vaud)
VD_TAUX_OCCUPATION = 98  # %

brand.page_header("🏥", "Concurrence — EMS",
                  "L'offre d'EMS (lits) face à la demande senior · occupation VD réf. ~98 %.",
                  "Listes cantonales · 2025-2026")


@st.cache_data
def load(sig):  # sig = signature des fichiers (mtime) -> invalide le cache si maj
    geo = json.loads(GEO.read_text(encoding="utf-8"))
    demo = pd.read_csv(DEMO, dtype={"ofs": str})
    ems = pd.read_csv(EMS, dtype={"ofs": str})
    return geo, demo, ems


sig = tuple(p.stat().st_mtime for p in (GEO, DEMO, EMS))
geo, demo, ems = load(sig)
ems_loc = ems.dropna(subset=["lat", "lon"])
lits_total = int(ems["lits"].sum())
lits_localises = int(ems.dropna(subset=["ofs"])["lits"].sum())

# --- Agrégat par commune ---
par_commune = ems.dropna(subset=["ofs"]).groupby("ofs").agg(
    nb_ems=("nom_clean", "count"), lits_commune=("lits", "sum")).reset_index()
d = demo.merge(par_commune, on="ofs", how="left")
d["nb_ems"] = d["nb_ems"].fillna(0).astype(int)
d["lits_commune"] = d["lits_commune"].fillna(0)
# Proxy de tension : 80+ par lit (NaN si aucun lit recensé dans la commune)
d["tension"] = (d["pop_80plus"] / d["lits_commune"].where(d["lits_commune"] > 0)).round(1)

# --- Choix d'affichage ---
mode = st.sidebar.radio(
    "Couche de fond (communes)",
    ["Tension : 80+ par lit (estimation)", "Part des 80+ (%) — demande",
     "Lits d'EMS par commune — offre"])
seuil = st.sidebar.slider("Population min. de la commune", 0, 3000, 500, 250)
d_aff = d[d["pop_totale"] >= seuil].copy()

if mode.startswith("Tension"):
    col, cap, fmt = "tension", "80+ par lit (plus c'est haut, plus c'est tendu)", "{:.1f}"
elif mode.startswith("Part"):
    col, cap, fmt = "part_80plus", "Part des 80+ (%)", "{:.1f}"
else:
    col, cap, fmt = "lits_commune", "Lits d'EMS", "{:.0f}"

vals = {r.ofs: getattr(r, col) for r in d_aff.itertuples() if pd.notna(getattr(r, col))}
infos = d.set_index("ofs").to_dict("index")

col1, col2 = st.columns([3, 1])

with col2:
    st.metric("Établissements (listes off.)", len(ems))
    st.metric("Lits totaux (3 cantons)", f"{lits_total:,}".replace(",", "'"))
    st.metric("Occupation (réf. VD)", f"{VD_TAUX_OCCUPATION} %")
    ratio = lits_total / demo["pop_80plus"].sum() * 100
    st.metric("Lits pour 100 pers. de 80+", f"{ratio:.0f}")
    st.caption(f"Géolocalisés : {len(ems_loc)}/{len(ems)} EMS · "
               f"{lits_localises:,}/{lits_total:,} lits cartographiés".replace(",", "'"))
    st.info("💡 Pitch : 98 % d'occupation = marché saturé. Les communes les plus "
            "« tendues » (beaucoup de 80+ pour peu de lits) sont les cibles à creuser.")

with col1:
    m = folium.Map(location=[46.55, 6.75], zoom_start=8, tiles="CartoDB positron")
    if vals:
        cmap = cm.linear.YlOrRd_09.scale(min(vals.values()), max(vals.values()))
        cmap.caption = cap
        for f in geo["features"]:
            o = f["properties"]["ofs"]
            inf = infos.get(o, {})
            f["properties"].update({
                "v": vals.get(o),
                "part_80plus": inf.get("part_80plus"),
                "lits_commune": int(inf.get("lits_commune", 0)),
                "nb_ems": int(inf.get("nb_ems", 0)),
                "tension": inf.get("tension"),
            })

        def style(ft):
            v = ft["properties"]["v"]
            return {"fillColor": cmap(v) if v is not None else "#eeeeee",
                    "color": "#999", "weight": 0.4, "fillOpacity": 0.75}

        folium.GeoJson(
            geo, style_function=style,
            highlight_function=lambda _: {"weight": 2, "color": "black"},
            tooltip=folium.GeoJsonTooltip(
                fields=["nom", "part_80plus", "lits_commune", "nb_ems", "tension"],
                aliases=["Commune :", "Part 80+ (%) :", "Lits EMS :",
                         "Nb EMS :", "Tension (80+/lit) :"]),
        ).add_to(m)
        cmap.add_to(m)

    for e in ems_loc.itertuples():
        folium.CircleMarker(
            [e.lat, e.lon], radius=3 + (e.lits or 0) ** 0.5 / 2,
            color="#1a5276", fill=True, fill_color="#2980b9", fill_opacity=0.85,
            tooltip=f"{e.nom_clean} — {int(e.lits)} lits ({e.commune})").add_to(m)

    st_folium(m, width=None, height=600, returned_objects=[])
    st.caption("⚪ Communes en gris = aucun lit recensé localement (ou EMS non géolocalisé). "
               "Taille des points ∝ nombre de lits.")

# --- Tableaux ---
t1, t2 = st.tabs(["🎯 Communes les plus tendues", "📋 Liste des EMS (officielle)"])
with t1:
    n_non_loc = int(ems["ofs"].isna().sum())
    st.caption("Communes avec le plus de 80+ par lit d'EMS local (offre sous pression). "
               "Hors communes sans lit recensé. ⚠️ Biais possible : une commune dont "
               f"des EMS ne sont pas encore géolocalisés ({n_non_loc}/{len(ems)}) peut apparaître "
               "artificiellement « tendue » (lits sous-comptés). À vérifier avant un pitch.")
    cibles = d_aff.dropna(subset=["tension"]).nlargest(15, "tension")
    st.dataframe(cibles[["nom", "pop_totale", "pop_80plus", "lits_commune",
                         "nb_ems", "tension"]].rename(columns={
        "nom": "Commune", "pop_totale": "Population", "pop_80plus": "80+",
        "lits_commune": "Lits", "nb_ems": "Nb EMS", "tension": "80+/lit"}),
        hide_index=True, use_container_width=True)
with t2:
    st.caption(f"{len(ems)} établissements. Sources : liste LAMal VD 2025, "
               "SeSPA Genève 2026, ordonnance RSF 834.2.41 Fribourg.")
    st.dataframe(ems[["nom_clean", "canton", "type", "lits", "commune", "geo_source"]].rename(
        columns={"nom_clean": "Établissement", "canton": "Canton", "type": "Type",
                 "lits": "Lits", "commune": "Commune", "geo_source": "Géoloc."}).sort_values(
        "Lits", ascending=False), hide_index=True, use_container_width=True)
