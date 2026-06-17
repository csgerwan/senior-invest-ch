"""
Senior Invest CH — point d'entrée & navigation (V2).

Navigation groupée (st.navigation) :
  • « Évaluer un bien » (accueil par défaut : adresse → radar investisseur)
  • « Explorer le marché » (carte, démographie, EMS, pouvoir d'achat, immobilier, score)
La config de page est centralisée ici (les pages n'appellent plus set_page_config).
"""

from pathlib import Path

import streamlit as st

import brand

ASSETS = Path(__file__).parent / "assets"

st.set_page_config(
    page_title="Helvina · Senior Invest",
    page_icon=str(ASSETS / "helvina_mark.svg"),
    layout="wide",
    initial_sidebar_state="expanded",
)

brand.inject_css()

# Logo Helvina (barre latérale) + monogramme en icône réduite
st.logo(str(ASSETS / "helvina_logo.svg"), size="large",
        icon_image=str(ASSETS / "helvina_mark.svg"))

# Bandeau d'en-tête navy (marque Helvina) — affiché sur chaque page
st.markdown(
    """
    <div style="background:#0E1E2E;border-radius:10px;padding:12px 20px;margin-bottom:14px;
                display:flex;align-items:center;gap:16px;flex-wrap:wrap;">
      <span style="color:#ffffff;font-size:26px;font-weight:700;letter-spacing:.5px;
                   font-family:'Inter','Trebuchet MS',sans-serif;">Helvina</span>
      <span style="color:#7FD8C4;font-size:13px;font-weight:500;border-left:1px solid #33485e;
                   padding-left:16px;">L'investissement senior, éclairé par la donnée</span>
      <span style="color:#9fb3c8;font-size:12px;margin-left:auto;">Canton de Vaud</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# --- Pages (chemins relatifs à app/) ---
evaluation = st.Page("pages/7_Evaluation_bien.py", title="Évaluer un bien",
                     icon="🏠", default=True)
carte = st.Page("pages/1_Carte_des_communes.py", title="Carte des communes", icon="🗺️")
demographie = st.Page("pages/2_Demographie.py", title="Démographie", icon="📊")
ems = st.Page("pages/3_Concurrence_EMS.py", title="Concurrence EMS", icon="🏥")
pouvoir_achat = st.Page("pages/4_Pouvoir_achat.py", title="Pouvoir d'achat", icon="💰")
immobilier = st.Page("pages/5_Immobilier.py", title="Immobilier", icon="🏗️")
score = st.Page("pages/6_Score_opportunite.py", title="Score d'opportunité", icon="🎯")

pg = st.navigation({
    "Évaluer un bien": [evaluation],
    "Explorer le marché": [carte, demographie, ems, pouvoir_achat, immobilier, score],
})
pg.run()

brand.footer()
