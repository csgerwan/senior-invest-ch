"""
Identité visuelle Helvina — composants partagés par toutes les pages.

Fournit : inject_css() (thème global), page_header() (en-tête uniforme),
footer() (bandeau de marque). Couleurs : navy #0E1E2E + teal #138D78.
"""

from datetime import date

import streamlit as st

NAVY = "#0E1E2E"
TEAL = "#138D78"
TEAL_LIGHT = "#E1F5F0"
SLATE = "#33485E"
SURFACE = "#F2F5F8"


def inject_css():
    """Thème global : police géométrique, barre latérale navy, KPI teal, etc."""
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"], [class*="st-"] {{ font-family:'Inter',sans-serif; }}
    /* Ne PAS écraser la police des icônes Material (sinon la ligature « expand_more »
       s'affiche en toutes lettres dans la navigation) */
    [data-testid="stIconMaterial"], span[class*="material-symbols"], span[class*="material-icons"] {{
        font-family:'Material Symbols Rounded','Material Symbols Outlined','Material Icons' !important;
    }}

    /* Barre latérale navy */
    section[data-testid="stSidebar"] {{ background-color:{NAVY}; }}
    section[data-testid="stSidebar"] * {{ color:#DCE6F0; }}
    section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"]:hover {{ background-color:rgba(19,141,120,.22); }}
    section[data-testid="stSidebar"] [aria-current="page"] {{ background-color:{TEAL} !important; }}
    section[data-testid="stSidebar"] [aria-current="page"] * {{ color:#fff !important; }}
    /* garder les champs de saisie lisibles (fond clair, texte navy) */
    section[data-testid="stSidebar"] input,
    section[data-testid="stSidebar"] [data-baseweb="select"] > div {{ color:{NAVY}; background-color:#fff; }}

    /* KPI (st.metric) en cartes douces */
    [data-testid="stMetric"] {{ background:{SURFACE}; border-radius:10px; padding:12px 14px; }}
    [data-testid="stMetricValue"] {{ color:{NAVY}; }}
    [data-testid="stMetricLabel"] p {{ color:{SLATE}; font-weight:500; }}

    /* Liens & focus en teal */
    a {{ color:{TEAL}; }}
    </style>
    """, unsafe_allow_html=True)


def page_header(icon, titre, description, millesime=None):
    """En-tête de page homogène : icône + titre + description + badge millésime."""
    badge = (f'<span style="margin-left:auto;background:{TEAL_LIGHT};color:{TEAL};'
             f'font-size:12px;font-weight:600;padding:4px 11px;border-radius:8px;'
             f'white-space:nowrap;">{millesime}</span>') if millesime else ""
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:12px;margin:2px 0 4px;">
      <span style="font-size:26px;line-height:1;">{icon}</span>
      <span style="font-size:22px;font-weight:600;color:{NAVY};">{titre}</span>
      {badge}
    </div>
    <p style="color:{SLATE};font-size:14px;margin:0 0 14px;">{description}</p>
    <hr style="border:none;border-top:2px solid {TEAL};opacity:.5;margin:0 0 16px;">
    """, unsafe_allow_html=True)


def footer():
    """Bandeau de marque en pied de page."""
    st.markdown(f"""
    <hr style="border:none;border-top:0.5px solid #d9e0e7;margin:2.5rem 0 10px;">
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;
                color:{SLATE};font-size:12px;padding-bottom:10px;">
      <span style="font-weight:700;color:{NAVY};">Helvina</span>
      <span>Données officielles sourcées · millésimes 2024-2026 ·
            mise à jour {date.today():%d.%m.%Y}</span>
      <span style="margin-left:auto;">Outil d'aide à la décision — à valider avant engagement</span>
    </div>
    """, unsafe_allow_html=True)
