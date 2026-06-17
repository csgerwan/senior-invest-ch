"""
Senior Invest CH — point d'entrée & navigation (V2).

Navigation groupée (st.navigation) :
  • « Évaluer un bien » (accueil par défaut : adresse → radar investisseur)
  • « Explorer le marché » (carte, démographie, EMS, pouvoir d'achat, immobilier, score)
La config de page est centralisée ici (les pages n'appellent plus set_page_config).
"""

from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).parent / "assets"

st.set_page_config(
    page_title="Helvina · Senior Invest",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Logo Helvina en haut de la barre latérale
st.logo(str(ASSETS / "helvina_logo.svg"), size="large")

# Bandeau d'en-tête navy (marque Helvina) — affiché sur chaque page
st.markdown(
    """
    <div style="background:#0E1E2E;border-radius:10px;padding:12px 20px;margin-bottom:14px;
                display:flex;align-items:center;gap:16px;flex-wrap:wrap;">
      <span style="color:#ffffff;font-size:26px;font-weight:700;letter-spacing:.5px;
                   font-family:'Trebuchet MS','Segoe UI',sans-serif;">Helvina</span>
      <span style="color:#9fb3c8;font-size:13px;border-left:1px solid #33485e;
                   padding-left:16px;">Senior Invest · aide à la décision d'investissement
                   en hébergement senior · canton de Vaud</span>
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
