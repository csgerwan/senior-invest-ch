# 🤝 Guide de reprise — Senior Invest CH (Helvina)

Document de passation destiné au **maître de stage** (ou à toute personne qui reprend le
projet). Il explique ce qu'est l'outil, comment le faire tourner, comment rafraîchir chaque
donnée, où sont les accès, et ce qu'il reste à faire.

> Résumé en une phrase : un tableau de bord **Streamlit** qui croise démographie senior,
> concurrence EMS, pouvoir d'achat et immobilier sur **la Suisse romande (Vaud, Genève,
> Fribourg)** pour repérer des opportunités d'hébergement senior et préparer des pitchs
> investisseurs.

---

## 1. Les 4 accès à transférer

Le projet vit à quatre endroits. Pour une reprise complète, il faut récupérer les quatre :

| # | Brique | Où | À faire pour la reprise |
|---|--------|----|--------------------------|
| 1 | **Code** | GitHub `csgerwan/senior-invest-ch` | Transférer la propriété du dépôt (idéalement vers un compte/organisation **Helvina**), ou ajouter le repreneur en **admin**. |
| 2 | **App en ligne** | Streamlit Community Cloud | Redéployer depuis **le compte Streamlit du repreneur**, pointant sur le dépôt (fichier principal `app/Home.py`). L'ancien lien meurt avec le compte d'origine. |
| 3 | **Scraping immo** | Compte **Apify** (gratuit) | Le repreneur crée **son propre compte Apify gratuit** et remplace le token (voir §6). |
| 4 | **Sources brutes** | Poste local (`data/raw/`) | Non indispensable : tout se re-télécharge via les scripts. Le `data/processed/` (ce que l'app lit) est **dans le dépôt**. |

> ⚠️ **Aucun secret n'est dans le dépôt** (le token Apify est stocké hors dépôt, cf. §6).
> Ne jamais committer de token.

---

## 2. Lancer l'application en local

Prérequis : **Python 3.9+** (le projet a été développé sous 3.9.6, sans Node).

```bash
# 1. Récupérer le code
git clone https://github.com/csgerwan/senior-invest-ch.git
cd senior-invest-ch

# 2. Créer l'environnement et installer les dépendances de l'app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Lancer
streamlit run app/Home.py
```

L'app s'ouvre sur `http://localhost:8501`.

- `requirements.txt` = dépendances **légères** (l'app) : streamlit, pandas, folium, streamlit-folium, branca, plotly.
- `requirements-dev.txt` = dépendances **des scripts** de préparation de données (geopandas, openpyxl, pdfplumber…). À installer seulement si on veut **régénérer** les données.

---

## 3. Structure du projet

```
app/
  Home.py                 # point d'entrée + navigation
  brand.py                # identité visuelle (couleurs, en-têtes, CSS)
  assets/                 # logo Helvina
  pages/                  # les 7 pages (voir ci-dessous)
data/
  raw/                    # sources brutes téléchargées (souvent git-ignorées)
  processed/              # données prêtes à l'emploi -> LUES PAR L'APP
scripts/                  # chaîne de préparation des données (numérotée 01 -> 07)
requirements.txt          # deps app (déploiement)
requirements-dev.txt      # deps scripts (régénération données)
```

**Les 7 pages :**
1. Carte des communes · 2. Démographie · 3. Concurrence EMS · 4. Pouvoir d'achat ·
5. Immobilier · 6. Score d'opportunité · 7. Évaluer un bien (radar investisseur, page d'accueil).

> 🔎 **Convention de nommage** : par héritage du pilote vaudois, beaucoup de fichiers gardent
> le suffixe `_vd` (`demographie_vd.csv`, `score_opportunite_vd.csv`, `radar_vd.csv`…) **alors
> qu'ils contiennent les 3 cantons**. C'est voulu (éviter de casser les imports) — ne pas s'y fier.
> Le fichier EMS unifié, lui, s'appelle bien `ems.csv`.

---

## 4. D'où viennent les données (sources officielles)

| Donnée | Source officielle | Millésime |
|--------|-------------------|-----------|
| Limites communales | OFS / geo.admin via Opendatasoft | 2025 |
| Démographie (65+/80+) | OFS STAT-TAB `px-x-0102010000_103` | 2024 |
| EMS Vaud (lits) | Liste LAMal VD (PDF cantonal) | 2025 |
| EMS Genève (lits) | SeSPA Genève (PDF) + localisations SITG | 2026 |
| EMS Fribourg (lits) | Ordonnance RSF 834.2.41 (BDLF/lexfind) | 2018 en vigueur |
| Revenu | Impôt fédéral direct ESTV (xlsx, onglet 511) | 2022 |
| Coefficients d'impôt | VD : vd.ch · GE : centimes add. ge.ch · FR : opendata.fr.ch `18_03` | 2025-2026 |
| Immobilier (prix/m²) | Annonces Homegate via Apify (prix demandés, pas transactions) | 2026 |

> Un document Word détaillé avec **liens cliquables + explication des calculs** existe :
> `scripts/generer_document_sources.py` le régénère (`~/Desktop/Senior_Invest_CH_Sources_et_Methodologie.docx`).

---

## 5. Rafraîchir les données (chaîne complète)

Chaque script se lance **depuis la racine du projet**, environnement activé
(`source .venv/bin/activate`, et `pip install -r requirements-dev.txt` la 1re fois).
Les scripts sont numérotés dans l'ordre du pipeline :

```bash
# --- Communes & démographie ---
python scripts/01_prepare_communes_vd.py      # limites communales (VD+GE+FR)
python scripts/02_fetch_demographie_vd.py     # population par âge (OFS)

# --- EMS (concurrence) : un script par canton, puis unification ---
python scripts/03a_parse_liste_lamal.py       # VD : parse le PDF LAMal
python scripts/03_fetch_ems_vd.py             # VD : géolocalisation
python scripts/03_ge_ems.py                   # GE
python scripts/03_fr_ems.py                   # FR
python scripts/03z_unify_ems.py               # -> ems.csv (258 EMS unifiés)

# --- Pouvoir d'achat ---
python scripts/04a_parse_revenu_ifd.py        # revenu (ESTV, 3 cantons)
python scripts/04b_parse_coefficients.py      # coefficient VD
python scripts/04b2_coefficients_romandie.py  # coefficients VD+GE+FR unifiés
python scripts/04c_parse_fortune_districts.py # fortune (contexte, VD)
python scripts/04_build_pouvoir_achat.py      # -> indice pouvoir d'achat

# --- Immobilier (Apify, cf. §6) ---
APIFY_TOKEN=xxx python scripts/05_fetch_homegate_apify.py   # VD
APIFY_TOKEN=xxx python scripts/05_ge_fetch_homegate.py      # GE
python scripts/05b_build_prix_m2.py           # VD : prix/m² par commune
python scripts/05b_ge_build_prix_m2.py        # GE : prix/m² par commune
python scripts/04d_build_immobilier.py        # assemble VD+GE (+ estimation voisinage)

# --- Synthèse ---
python scripts/06_build_score.py              # score d'opportunité (4 critères)
python scripts/07_build_radar.py              # notes du radar « Évaluer un bien »
```

**Règle d'or** : après toute mise à jour de données, faire `git add` + `git commit` + `git push`.
Streamlit Cloud **redéploie automatiquement** l'app en ligne à chaque push sur `main`.

---

## 6. Le scraping immobilier (Apify) — à connaître absolument

Les prix de **transaction** immobilière ne sont pas publics en Suisse. On récupère donc les
**prix demandés** des annonces Homegate via un « actor » Apify (`santamaria-automations/homegate-scraper`).

- **Token** : stocké **hors dépôt**, dans `~/Desktop/.mcp.json` (config du serveur MCP Apify).
  Le repreneur doit créer **son** compte gratuit sur [console.apify.com](https://console.apify.com)
  et remplacer le token. Les scripts lisent le token via la variable d'environnement `APIFY_TOKEN`.
- **Coût** : ~0,003 $/annonce. Le plan gratuit offre **5 $/mois**.
- **⚠️ Piège du cycle** : le crédit gratuit se réinitialise à la **date d'inscription**, PAS le
  1er du mois. Vérifier le solde :
  ```bash
  curl -s "https://api.apify.com/v2/users/me/usage/monthly?token=$APIFY_TOKEN"
  ```
- **URL de recherche par canton** (paramètre `searchUrls`) :
  `https://www.homegate.ch/kaufen/immobilien/kanton-<slug>/trefferliste`
  avec `<slug>` = `waadt` (VD), `genf` (GE), `freiburg` (FR).

---

## 7. Ce qu'il reste à faire

- 🏗️ **Immobilier Fribourg** : pas encore scrapé (budget Apify épuisé au moment de la reprise).
  Marche à suivre quand le crédit est de nouveau ≥ ~1,5 $ :
  1. dupliquer `05_ge_fetch_homegate.py` → `05_fr_fetch_homegate.py` (searchUrl `kanton-freiburg`) ;
  2. dupliquer `05b_ge_build_prix_m2.py` → `05b_fr_build_prix_m2.py` (fourchette 3000-30000 CHF/m²,
     Fribourg étant moins cher que Genève) ;
  3. relancer `04d` → `06` → `07`, puis push.
- 🔤 Optionnel : renommer les fichiers `_vd` → `_romandie` (cosmétique, touche plusieurs imports).

---

## 8. Rappels importants

- **Nature des chiffres** : données officielles et sourcées, mais l'**immobilier** = prix
  *demandés* (annonces), pas des transactions → **valeurs indicatives**. Le **score** est un
  outil de *simulation de thèse* (poids ajustables), pas une vérité absolue. À valider avant
  tout engagement.
- **Comparabilité inter-cantons** : le revenu (base fédérale) est comparable ; le coefficient
  d'impôt est normalisé **par canton** (bases fiscales différentes). Les prix immobiliers ne
  sont **pas** comparés d'un canton à l'autre (estimation de voisinage limitée au même canton).
- **Cache Streamlit** : les pages passent une signature de fichiers (mtime) à `@st.cache_data`
  pour se rafraîchir. Si une page semble figée : `Cmd+Shift+R`, ou « Reboot app » sur Streamlit Cloud.

---

*Bonne reprise ! Le projet est modulaire : chaque donnée a son script dédié, et l'app ne lit
que le dossier `data/processed/`.*
