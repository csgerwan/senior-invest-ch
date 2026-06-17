"""
Senior Invest CH — point d'entrée & navigation (V2).

Navigation groupée (st.navigation) :
  • « Évaluer un bien » (accueil par défaut : adresse → radar investisseur)
  • « Explorer le marché » (carte, démographie, EMS, pouvoir d'achat, immobilier, score)
La config de page est centralisée ici (les pages n'appellent plus set_page_config).
"""

import streamlit as st

st.set_page_config(
    page_title="Senior Invest CH",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
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
