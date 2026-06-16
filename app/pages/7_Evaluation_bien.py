"""
V2 — Évaluation d'un bien : saisie d'une adresse -> remplissage automatique de
la zone VERTE du radar investisseur (qualification de la demande), + décote vs
marché si le prix du bien est renseigné.

- Géocodage via l'API officielle geo.admin (urllib, pas de dépendance lourde).
- Rattachement à la commune en pur Python (point-dans-polygone) -> pas de geopandas.
- Radar interactif Plotly.
"""

import json
import urllib.parse
import urllib.request
from pathlib import Path

import branca.colormap as cm
import folium
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

ROOT = Path(__file__).resolve().parents[2]
GEO = ROOT / "data/processed/communes_vd.geojson"
RADAR = ROOT / "data/processed/radar_vd.csv"
SCORE = ROOT / "data/processed/score_opportunite_vd.csv"
EMS = ROOT / "data/processed/ems_vd.csv"
UA = {"User-Agent": "senior-invest-ch/1.0"}

st.set_page_config(page_title="Évaluation d'un bien", page_icon="🏠", layout="wide")
st.title("🏠 Évaluation d'un bien — radar investisseur")
st.caption("Entre une adresse : la zone verte (qualification de la demande) se remplit "
           "automatiquement. Ajoute le prix pour la décote vs marché.")

# Axes du radar (ordre = image de référence). Zone verte + décote = automatiques.
AXES = [
    ("Pouvoir d'achat senior", "vert"),
    ("Proximité & saturation EMS", "vert"),
    ("Population senior de la zone", "vert"),
    ("Rendement net", "auto_non"),
    ("Coût total projet", "auto_non"),
    ("Décote vs marché", "decote"),
    ("Valeur ajoutée vendeur", "auto_non"),
    ("Fallback / réversibilité", "auto_non"),
    ("Facilité urbanisme", "auto_non"),
    ("Qualité espaces extérieurs", "auto_non"),
    ("Volumes (densité m²/senior)", "auto_non"),
    ("Esthétique bâtiment", "auto_non"),
]


@st.cache_data
def load(sig):
    geo = json.loads(GEO.read_text(encoding="utf-8"))
    radar = pd.read_csv(RADAR, dtype={"ofs": str})
    score = pd.read_csv(SCORE, dtype={"ofs": str})
    ems = pd.read_csv(EMS, dtype={"ofs": str}).dropna(subset=["lat", "lon"])
    return geo, radar, score, ems


geo, radar, score, ems = load(tuple(p.stat().st_mtime for p in (GEO, RADAR, SCORE, EMS)))


@st.cache_data(show_spinner=False)
def geocoder(adresse):
    """Adresse -> (lat, lon) via geo.admin SearchServer."""
    q = urllib.parse.urlencode({"type": "locations", "searchText": adresse,
                                "limit": 1, "sr": 4326, "origins": "address,gg25"})
    url = "https://api3.geo.admin.ch/rest/services/api/SearchServer?" + q
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=15) as r:
            res = json.loads(r.read()).get("results", [])
        if res:
            a = res[0]["attrs"]
            return a["lat"], a["lon"], a.get("label", "")
    except Exception:
        pass
    return None, None, None


def _in_ring(x, y, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def commune_de(lon, lat, geo):
    """Point-dans-polygone pur Python -> propriétés de la commune, ou None."""
    for f in geo["features"]:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            if poly and _in_ring(lon, lat, poly[0]):
                return f["properties"]
    return None


# --- Saisie ---
c1, c2, c3 = st.columns([2, 1, 1])
adresse = c1.text_input("Adresse du bien", placeholder="ex : Rue du Collège 5, 1110 Morges")
prix = c2.number_input("Prix demandé (CHF)", min_value=0, value=0, step=50000,
                       help="Optionnel — pour la décote vs marché")
surface = c3.number_input("Surface (m²)", min_value=0, value=0, step=10,
                          help="Optionnel — pour la décote vs marché")

if not adresse:
    st.info("👆 Entre une adresse pour lancer l'évaluation.")
    st.stop()

lat, lon, label = geocoder(adresse)
if lat is None:
    st.error("Adresse introuvable. Précise la rue, le NPA et la commune.")
    st.stop()

props = commune_de(lon, lat, geo)
if not props:
    st.error("Cette adresse ne semble pas dans le canton de Vaud (hors périmètre V1).")
    st.stop()

ofs = props["ofs"]
row = radar[radar["ofs"] == ofs]
if row.empty:
    st.error(f"Pas de données pour la commune {props['nom']}.")
    st.stop()
r = row.iloc[0]

# --- Décote vs marché ---
note_decote, decote_pct, prix_m2_bien = None, None, None
marche = r["prix_m2_appart"]
if prix > 0 and surface > 0 and pd.notna(marche):
    prix_m2_bien = prix / surface
    decote_pct = (marche - prix_m2_bien) / marche * 100
    note_decote = max(0.0, min(5.0, decote_pct / 25 * 5))  # 25%+ de décote -> 5/5

# --- Valeurs du radar ---
valeurs = {
    "Pouvoir d'achat senior": r["note_pouvoir_achat"],
    "Proximité & saturation EMS": r["note_tension_ems"],
    "Population senior de la zone": r["note_population"],
    "Décote vs marché": note_decote,
}

st.success(f"📍 **{props['nom']}** (district de {props['district']}) — {label.replace('<b>','').replace('</b>','')}")

colg, cold = st.columns([3, 2])

with colg:
    cats = [a for a, _ in AXES]
    vals = [valeurs.get(a) if valeurs.get(a) is not None else 0 for a in cats]
    # boucler le polygone
    cats_c = cats + [cats[0]]
    vals_c = vals + [vals[0]]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=vals_c, theta=cats_c, fill="toself",
        fillcolor="rgba(46,160,80,0.30)", line=dict(color="rgba(46,160,80,0.9)"),
        name="Évaluation"))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 5], dtick=1)),
        showlegend=False, height=520, margin=dict(l=60, r=60, t=40, b=40))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("🟢 Zone verte + décote = remplies automatiquement. Les autres axes "
               "(produit, risque, économie) sont à évaluer manuellement (hors V1).")

with cold:
    st.markdown("### 🟢 Qualification de la demande")
    st.metric("Pouvoir d'achat senior", f"{r['note_pouvoir_achat']:.1f} / 5",
              f"indice commune {r['indice_pouvoir_achat']:.0f}/100")
    st.metric("Proximité & saturation EMS", f"{r['note_tension_ems']:.1f} / 5",
              f"EMS le + proche : {r['dist_ems_km']} km · {r['lits_pour_100_district']:.0f} lits/100 (80+) district")
    st.metric("Population senior de la zone", f"{r['note_population']:.1f} / 5",
              f"{int(r['pop_80plus'])} pers. de 80+ ({r['part_80plus']:.1f}%)")

    st.markdown("### 🟠 Décote vs marché")
    if note_decote is not None:
        st.metric("Décote vs marché", f"{note_decote:.1f} / 5", f"{decote_pct:+.0f}% vs marché")
        st.caption(f"Bien : {prix_m2_bien:,.0f} CHF/m² · Marché {props['nom']} : "
                   f"{marche:,.0f} CHF/m² ({r['prix_fiabilite']})".replace(",", "'"))
    else:
        st.info("Renseigne **prix** + **surface** pour calculer la décote.")

st.divider()
st.caption("Notes /5. Pouvoir d'achat = indice (revenu+fiscalité+fortune)/20. "
           "Tension EMS = saturation du district (lits/senior) + éloignement. "
           "Population = nb de 80+ normalisé. Décote = (prix marché − prix bien)/prix marché "
           "(25 %+ → 5/5). Prix de marché = annonces/estimations (voir page Immobilier).")

# ----- Carte interactive + calques -----
st.divider()
st.subheader("🗺️ Localisation du bien & calques de données")

# Score d'opportunité à poids égaux (pour le calque)
sc = score.copy()
sc["score_eq"] = sc[["demande_score", "tension_score",
                     "pouvoir_achat_score", "prix_bas_score"]].mean(axis=1).round(1)

# calque -> (colonne, légende, palette, plus c'est haut = mieux)
CALQUES = {
    "Score d'opportunité": ("score_eq", "Score (poids égaux)", "RdYlGn", True),
    "Part de seniors 80+ (%)": ("part_80plus", "Part 80+ (%)", "YlOrRd", True),
    "Tension EMS (district)": ("tension_score", "Tension /100", "YlOrRd", True),
    "Pouvoir d'achat": ("pouvoir_achat_score", "Pouvoir d'achat /100", "RdYlGn", True),
    "Prix immobilier (CHF/m²)": ("prix_m2_appart", "Prix CHF/m²", "YlOrRd", True),
    "EMS à proximité": (None, "", None, True),
}
calque = st.selectbox("Calque à afficher", list(CALQUES),
                      help="Fais défiler les couches de données autour du bien.")
col, legende, palette, _ = CALQUES[calque]

m = folium.Map(location=[lat, lon], zoom_start=12, tiles="CartoDB positron")

if col:  # calque choroplèthe
    vals = dict(zip(sc["ofs"], sc[col]))
    vals = {k: v for k, v in vals.items() if pd.notna(v)}
    cmap = getattr(cm.linear, palette + "_09").scale(min(vals.values()), max(vals.values()))
    cmap.caption = legende
    infos_sc = sc.set_index("ofs").to_dict("index")
    for f in geo["features"]:
        o = f["properties"]["ofs"]
        f["properties"]["val"] = vals.get(o)
        f["properties"]["nom_t"] = f["properties"]["nom"]
        f["properties"]["est_bien"] = (o == ofs)
    folium.GeoJson(
        geo,
        style_function=lambda ft: {
            "fillColor": cmap(ft["properties"]["val"]) if ft["properties"]["val"] is not None else "#eee",
            "color": "#111" if ft["properties"]["est_bien"] else "#999",
            "weight": 3 if ft["properties"]["est_bien"] else 0.4,
            "fillOpacity": 0.7 if ft["properties"]["val"] is not None else 0.1,
        },
        tooltip=folium.GeoJsonTooltip(fields=["nom_t", "val"],
                                      aliases=["Commune :", legende + " :"]),
    ).add_to(m)
    cmap.add_to(m)
else:  # calque EMS : points des établissements autour du bien
    def dist_km(la, lo):
        import math
        return ((la - lat) * 110.57) ** 2 + ((lo - lon) * 111.32 * math.cos(math.radians(lat))) ** 2
    proches = sorted(ems.itertuples(), key=lambda e: dist_km(e.lat, e.lon))[:25]
    for e in proches:
        folium.CircleMarker(
            [e.lat, e.lon], radius=3 + (e.lits or 0) ** 0.5 / 2,
            color="#1a5276", fill=True, fill_color="#2980b9", fill_opacity=0.85,
            tooltip=f"{e.nom_clean} — {int(e.lits)} lits ({e.commune})").add_to(m)
    st.caption(f"🔵 Les {len(proches)} EMS les plus proches du bien (taille ∝ nombre de lits).")

# Marqueur du bien (toujours visible)
folium.Marker(
    [lat, lon], tooltip=f"📍 {adresse}",
    icon=folium.Icon(color="red", icon="home", prefix="fa")).add_to(m)

st_folium(m, width=None, height=500, returned_objects=[], key=f"map_{calque}")
