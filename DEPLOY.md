# Déployer Senior Invest CH (lien partageable, gratuit)

Objectif : obtenir une URL publique (type `https://senior-invest-ch.streamlit.app`)
à partager avec ton maître de stage. **Gratuit**, permanent, sans laisser ton Mac allumé.

## Méthode recommandée — Streamlit Community Cloud

### 1. Mettre le projet sur GitHub (~5 min)
1. Crée un compte sur https://github.com (si pas déjà fait).
2. Crée un nouveau dépôt **public** nommé `senior-invest-ch` (sans README, il existe déjà).
3. Dans le terminal, depuis le dossier du projet :
   ```bash
   cd ~/Desktop/senior-invest-ch
   git branch -M main
   git remote add origin https://github.com/<TON_PSEUDO>/senior-invest-ch.git
   git push -u origin main
   ```
   (GitHub demandera ton identifiant + un *Personal Access Token* comme mot de passe :
   créer un token sur https://github.com/settings/tokens, droits « repo ».)

### 2. Déployer sur Streamlit Cloud (~2 min)
1. Va sur https://share.streamlit.io et connecte-toi **avec GitHub**.
2. Clique **« Create app »** → **« Deploy a public app from GitHub »**.
3. Renseigne :
   - **Repository** : `<TON_PSEUDO>/senior-invest-ch`
   - **Branch** : `main`
   - **Main file path** : `app/Home.py`
4. Clique **Deploy**. Au bout de 1-2 min, tu obtiens ton URL publique. 🎉

### 3. Partager
Copie l'URL (`https://....streamlit.app`) et envoie-la à ton maître de stage.
À chaque `git push`, l'app se met à jour automatiquement.

---

## Notes
- L'app ne lit que des fichiers de données **déjà inclus** dans le dépôt
  (`data/processed/`) — rien à configurer côté secrets.
- ⚠️ Ne mets **jamais** ton token Apify dans le dépôt (il est dans `~/Desktop/.mcp.json`,
  hors du projet ; le `.gitignore` exclut déjà les caches et données brutes).
- `requirements.txt` est volontairement léger (l'app n'a pas besoin de geopandas) pour
  un déploiement rapide et fiable.
