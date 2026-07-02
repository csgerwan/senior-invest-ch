#!/usr/bin/env bash
#
# setup.sh — Démarrage en une commande de Senior Invest CH.
#
# À lancer depuis la racine du dépôt (après `git clone` et `cd senior-invest-ch`) :
#     bash setup.sh            # installe et prépare l'app
#     bash setup.sh --run      # installe PUIS lance l'app
#     bash setup.sh --dev      # installe AUSSI les dépendances des scripts de données
#
set -e

RUN=false
DEV=false
for arg in "$@"; do
  case "$arg" in
    --run) RUN=true ;;
    --dev) DEV=true ;;
  esac
done

# 1. Vérifier Python
if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ Python 3 introuvable. Installe Python 3.9+ puis relance ce script."
  exit 1
fi
echo "✅ $(python3 --version)"

# 2. Environnement virtuel
if [ ! -d ".venv" ]; then
  echo "→ Création de l'environnement virtuel (.venv)…"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# 3. Dépendances
echo "→ Installation des dépendances de l'app (requirements.txt)…"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

if [ "$DEV" = true ]; then
  echo "→ Installation des dépendances des scripts de données (requirements-dev.txt)…"
  pip install --quiet -r requirements-dev.txt
fi

echo ""
echo "✅ Prêt."
echo "   • Lancer l'app :        source .venv/bin/activate && streamlit run app/Home.py"
echo "   • Mettre à jour les données : voir HANDOVER.md, section 5"
echo ""

# 4. Lancement optionnel
if [ "$RUN" = true ]; then
  echo "→ Lancement de l'app sur http://localhost:8501 …"
  streamlit run app/Home.py
fi
