"""
Étape 5 (v2) — Récupération des annonces immobilières VD via Apify (Homegate).

Lance l'actor santamaria-automations/homegate-scraper sur tout le canton de Vaud
(annonces à l'achat), en mode asynchrone (démarrage -> attente -> récupération).

Budget maîtrisé : maxResults plafonné (0,003 $/annonce) pour rester sous 5 $.
Le token est lu depuis la variable d'environnement APIFY_TOKEN (jamais en dur).

Sortie : data/raw/homegate_vd_raw.json

Lancer depuis la racine du projet :
    APIFY_TOKEN=xxx python scripts/05_fetch_homegate_apify.py
"""

import json
import os
import time
import urllib.request
from pathlib import Path

TOKEN = os.environ["APIFY_TOKEN"]
ACTOR = "santamaria-automations~homegate-scraper"
SEARCH_URL = "https://www.homegate.ch/kaufen/immobilien/kanton-waadt/trefferliste"
MAX_RESULTS = 1400  # ~4.20 $ ; marge sous le quota gratuit de 5 $
OUT = Path("data/raw/homegate_vd_raw.json")


def api(method, url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    # 1. Démarrer le run
    start = api("POST",
                f"https://api.apify.com/v2/acts/{ACTOR}/runs?token={TOKEN}",
                {"searchUrls": [SEARCH_URL], "maxResults": MAX_RESULTS,
                 "includeDetails": False})
    run_id = start["data"]["id"]
    dataset_id = start["data"]["defaultDatasetId"]
    print(f"Run démarré : {run_id} (dataset {dataset_id})", flush=True)

    # 2. Attendre la fin (poll)
    for _ in range(180):  # max ~30 min
        time.sleep(10)
        run = api("GET", f"https://api.apify.com/v2/actor-runs/{run_id}?token={TOKEN}")
        st = run["data"]["status"]
        items = run["data"].get("stats", {}).get("itemCount") or "?"
        print(f"  statut={st}  items={items}", flush=True)
        if st in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            break

    # 3. Récupérer les items (pagination)
    all_items, offset = [], 0
    while True:
        page = api("GET",
                   f"https://api.apify.com/v2/datasets/{dataset_id}/items"
                   f"?token={TOKEN}&clean=true&limit=1000&offset={offset}")
        if not page:
            break
        all_items.extend(page)
        offset += len(page)
        if len(page) < 1000:
            break

    OUT.write_text(json.dumps(all_items, ensure_ascii=False), encoding="utf-8")
    print(f"DONE: {len(all_items)} annonces écrites dans {OUT}", flush=True)


if __name__ == "__main__":
    main()
