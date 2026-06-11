# 🏛️ Senior Invest CH

Outil d'aide à la décision pour l'**investissement en hébergement senior** dans le
canton de **Vaud**. Croise des données publiques fiables, par commune, pour repérer
les meilleures opportunités et préparer des pitchs investisseurs.

## Modules

| Module | Contenu | Sources |
|---|---|---|
| 🗺️ Carte des communes | Les 300 communes vaudoises | OFS / geo.admin |
| 📊 Démographie | Population 65+/80+, vieillissement | OFS STAT-TAB 2024 |
| 🏥 Concurrence EMS | 163 EMS + lits, tension du marché | Liste LAMal VD 2024 |
| 💰 Pouvoir d'achat | Revenu, fiscalité, fortune | ESTV / vd.ch / StatVD |
| 🏗️ Immobilier | Prix au m² (300/300 communes) | Annonces Homegate (Apify) |
| 🎯 Score d'opportunité | Classement interactif, 4 critères croisés | synthèse |

Le **score d'opportunité** met en avant les communes où : la part de seniors est
élevée, qui sont éloignées des EMS existants, au pouvoir d'achat élevé et au prix
immobilier bas. Les poids sont ajustables en direct.

## Lancer en local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app/Home.py
```

## Rafraîchir les données (optionnel)

```bash
pip install -r requirements-dev.txt
# Démographie / EMS / pouvoir d'achat / immobilier : voir scripts/ (01 à 06)
# Prix immobiliers (Apify) :
APIFY_TOKEN=xxx python scripts/05_fetch_homegate_apify.py
python scripts/05b_build_prix_m2.py && python scripts/04d_build_immobilier.py
python scripts/06_build_score.py
```

## Déploiement

Voir [DEPLOY.md](DEPLOY.md) — déploiement gratuit sur Streamlit Community Cloud.

---
⚠️ Outil d'aide à la décision. Données sourcées et datées ; prix immobiliers
indicatifs (annonces, pas transactions) et fortune au niveau district. À valider
avant tout engagement.
