"""
Senior Invest CH — Espace data d'aide à la décision
Dashboard pour repérer des opportunités d'investissement en hébergement senior
en Suisse romande (pilote : canton de Vaud).
"""

import streamlit as st

# --- Configuration de la page ---
st.set_page_config(
    page_title="Senior Invest CH",
    page_icon="🏛️",
    layout="wide",
)

# --- En-tête ---
st.title("🏛️ Senior Invest CH")
st.subheader("Espace data — opportunités d'investissement en hébergement senior")
st.caption("Pilote : canton de Vaud · Données publiques sourcées et datées")

st.divider()

# --- Présentation ---
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown(
        """
        ### Bienvenue 👋
        Cet espace regroupe des **données fiables et géolocalisées** pour :
        - 🔍 **Repérer des opportunités** : où la demande senior va croître et où l'offre manque
        - 📊 **Préparer des pitchs investisseurs** : des chiffres crédibles, sourcés et datés
        - 🗺️ **Analyser une localisation précise** : démographie, concurrence, immobilier

        Utilise le menu de gauche pour naviguer entre les modules.
        """
    )

with col2:
    st.info(
        "**Statut du projet**\n\n"
        "✅ Étape 0 — Setup\n\n"
        "✅ Étape 1 — Carte des communes VD\n\n"
        "✅ Étape 2 — Démographie & vieillissement\n\n"
        "✅ Étape 3 — Concurrence (EMS) — 163 EMS officiels + lits\n\n"
        "✅ Étape 4 — Pouvoir d'achat (revenu, fiscalité, fortune)\n\n"
        "🟡 Étape 5 — Immobilier (prix indicatifs, short-list)\n\n"
        "✅ Étape 6 — Score d'opportunité (interactif)\n\n"
        "⬜ Étape 7 — Fiche pitch"
    )

st.divider()
st.caption(
    "⚠️ Chaque chiffre affiché dans l'app sera accompagné de sa source et de sa date. "
    "La fiabilité prime sur la fraîcheur : on indique toujours l'année de référence."
)
