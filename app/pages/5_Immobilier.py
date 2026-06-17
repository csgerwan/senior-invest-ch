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

import brand
from streamlit_folium import st_folium

ROOT = Path(__file__).resolve().parents[2]
GEO = ROOT / "data/processed/communes_vd.geojson"
IMMO = ROOT / "data/processed/immobilier_vd.csv"

brand.page_header("🏗️", "Immobilier — prix au m²",
                  "Prix indicatifs (annonces Homegate) · couverture 300/300 communes.",
                  "Homegate · 2026")

st.warning(
    "**Prix issus des annonces (≈ prix demandés), pas de transactions.** Trois niveaux de "
    "fiabilité (colonne dédiée) :\n"
    "1. **Réel / indicatif** — calculé sur les annonces d'achat de la commune (surface "
    "extraite des descriptions) ;\n"
    "2. **Surface estimée** — annonces sans surface, imputée via le nombre de pièces ;\n"
    "3. **Estimé (voisinage)** — communes sans bien en vente : médiane des communes les plus "
    "proches.\n\n"
    "À valider par une source pro (Wüest/FPRE) avant tout engagement."
)


@st.cache_data
def load(sig):
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
    st.metric("Prix médian (canton)", f"{avec_prix['prix_m2_appart'].median():,.0f} CHF/m²".replace(",", "'"))
    st.metric("Min / Max", f"{avec_prix['prix_m2_appart'].min():,.0f} / {avec_prix['prix_m2_appart'].max():,.0f}".replace(",", "'"))
    st.caption("💡 Croise prix bas + forte demande seniors + bon pouvoir d'achat "
               "= terrain d'opportunité (ex : Yverdon, Gland, Epalinges).")

# Style par niveau de fiabilité : (opacité, bordure dash, couleur, épaisseur)
def tier_de(fiab):
    if fiab == "estimé (voisinage)":
        return "voisinage"
    if fiab == "annonces (surface estimée)":
        return "surface_estimee"
    return "annonces"  # solide / indicative


STYLE_TIER = {
    "annonces":        {"opa": 0.88, "dash": None,  "col": "#666", "w": 0.4},
    "surface_estimee": {"opa": 0.70, "dash": "3,3", "col": "#666", "w": 0.5},
    "voisinage":       {"opa": 0.38, "dash": "6,5", "col": "#333", "w": 0.9},
}

with col1:
    m = folium.Map(location=[46.55, 6.6], zoom_start=10, tiles="CartoDB positron")
    for f in geo["features"]:
        o = f["properties"]["ofs"]
        inf = infos.get(o, {})
        f["properties"]["prix"] = vals.get(o)
        f["properties"]["nom_t"] = f["properties"]["nom"]
        f["properties"]["pop80"] = int(inf["pop_80plus"]) if inf.get("pop_80plus") == inf.get("pop_80plus") and inf.get("pop_80plus") is not None else None
        f["properties"]["pa"] = inf.get("indice_pouvoir_achat")
        f["properties"]["fiab"] = inf.get("fiabilite")
        f["properties"]["tier"] = tier_de(inf.get("fiabilite"))

    def style(ft):
        p = ft["properties"]
        if not p["prix"]:
            return {"fillColor": "#e8e8e8", "color": "#ccc", "weight": 0.3, "fillOpacity": 0.1}
        s = STYLE_TIER[p["tier"]]
        return {"fillColor": colmap(p["prix"]), "color": s["col"], "weight": s["w"],
                "fillOpacity": s["opa"], "dashArray": s["dash"]}

    folium.GeoJson(
        geo, style_function=style,
        highlight_function=lambda _: {"weight": 2.5, "color": "black"},
        tooltip=folium.GeoJsonTooltip(
            fields=["nom_t", "prix", "fiab", "pop80", "pa"],
            aliases=["Commune :", "Prix CHF/m² :", "Fiabilité :", "Pop. 80+ :", "Pouvoir d'achat :"]),
    ).add_to(m)
    colmap.add_to(m)

    # Légende des niveaux de fiabilité
    legende = """
    <div style="position: fixed; bottom: 30px; left: 12px; z-index: 9999;
         background: white; padding: 8px 10px; border: 1px solid #999; border-radius: 6px;
         font-size: 12px; line-height: 1.5;">
      <b>Fiabilité du prix</b><br>
      <span style="opacity:0.9">⬛</span> Annonces réelles<br>
      <span style="opacity:0.6">⬛</span> Surface estimée (annonces)<br>
      <span style="opacity:0.35">⬛</span> Estimé (voisinage) — bordure tiretée
    </div>"""
    m.get_root().html.add_child(folium.Element(legende))
    st_folium(m, width=None, height=560, returned_objects=[])

st.subheader("📋 Prix au m² par commune — vs demande & pouvoir d'achat")
cols = ["nom", "district", "prix_m2_appart", "prix_m2_median", "n_annonces",
        "fiabilite", "pop_80plus", "indice_pouvoir_achat"]
cols = [c for c in cols if c in avec_prix.columns]
tab = avec_prix[cols].rename(columns={
    "nom": "Commune", "district": "District", "prix_m2_appart": "Prix/m² moyen",
    "prix_m2_median": "Prix/m² médian", "n_annonces": "Nb annonces",
    "fiabilite": "Fiabilité", "pop_80plus": "Pop. 80+",
    "indice_pouvoir_achat": "Pouvoir d'achat"})
st.dataframe(tab, hide_index=True, use_container_width=True)
st.caption("Prix réels = annonces Homegate via Apify (2026). « Fiabilité » dépend du nombre "
           "d'annonces (5+ = solide). Rafraîchir : relancer scripts 05 → 05b → 04d.")
