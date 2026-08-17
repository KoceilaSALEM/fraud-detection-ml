# Dashboard Sentinelle — portage Dash

Portage fidèle du dashboard Streamlit (`dashboard/app.py`, `network_view.py`,
`theme.py`) vers Dash. Charte Orange claire et accessible, mêmes 2 onglets, mêmes 6 vues
(Synthèse, M1, M2, M4, M5, M6), même vue réseau M2 (pyvis + arbre + table).

## 1 · Où placer ces fichiers

Ce dossier (`dashboard_dash/`) est conçu pour remplacer `dashboard/` dans
l'arborescence du projet Sentinelle, **au même niveau** (donc avec `outputs/`,
`data/`, `scripts/` comme dossiers frères) :

```
ML/                              ← ROOT (racine du projet)
├── dashboard_dash/               ← ce dossier
│   ├── app.py
│   ├── theme.py
│   ├── data_access.py
│   ├── network_view.py
│   ├── pages/
│   │   ├── tableau_de_bord.py
│   │   └── donnees_inference.py
│   ├── assets/
│   │   ├── generated_theme.css   ← généré automatiquement, ne pas éditer à la main
│   │   └── logo_orange.png       ← à copier depuis dashboard/assets/
│   └── requirements.txt
├── outputs/runs/…
├── data/raw/, data/processed/
└── scripts/run_inference.py
```

**Étape à faire manuellement** : copier `dashboard/assets/logo_orange.png`
vers `dashboard_dash/assets/logo_orange.png` (le logo n'était pas dans les
fichiers que tu m'as transmis).

## 2 · Installation

```bash
# dans ton venv existant (local ou conda ml312 sur la VM)
cd dashboard_dash
pip install -r requirements.txt
```

`pyarrow` est ajouté explicitement (lecture des `.parquet` M2 et M5) — à
retirer du fichier si déjà présent ailleurs dans ton environnement.

## 3 · Lancer en local

```bash
python app.py
```

Ouvre `http://localhost:8050`. Rechargement automatique activé (`debug=True`
dans `app.py` — à repasser à `False` en production).

## 4 · Ce qui a changé structurellement (à connaître avant de modifier le code)

| Aspect | Streamlit | Dash (ce portage) |
|---|---|---|
| Navigation 2 onglets | `st.navigation` / `st.Page` | `dash.register_page` (dossier `pages/`) |
| Vue active (Synthèse/M1…) | `st.radio` + rerun complet | `dcc.RadioItems` + callback ciblé |
| Partage d'état run_id/rapport | variables globales de module | contexte explicite passé en paramètre (plus sûr en multi-utilisateur) |
| Cache 60 s | `@st.cache_data(ttl=60)` | `flask-caching` (`@cache.memoize(timeout=60)`) |
| Graphe M2 interactif | `components.html` (pyvis) | `html.Iframe(srcDoc=...)` (pyvis, inchangé) |
| Arbre M2 | `st.graphviz_chart` (rendu navigateur) | `html.Iframe` + `d3-graphviz` via CDN (même principe : **aucune dépendance système**, mais le poste client doit atteindre `cdnjs.cloudflare.com` et `cdn.jsdelivr.net` — voir §6) |
| Tableaux | `st.dataframe` | `dash-ag-grid` (tri/filtre/pagination intégrés) |
| Rafraîchissement pendant un run | `time.sleep(10)` + `st.rerun()` (bloquant) | `dcc.Interval` 10 s (non bloquant — le serveur reste dispo pour les autres analystes) |
| Export CSV | `st.download_button` | boutons + `dcc.Download`, un callback par page en pattern-matching |

**Important** : la vue M2 lit toujours `outputs/M2_mules/` (chemin fixe, pas
par run) — c'est la limitation déjà documentée dans le mémoire, reproduite à
l'identique ici. Le correctif (écrire `edges_graph.parquet` par run) reste à
faire côté pipeline, pas dans le dashboard.

## 5 · Différence de robustesse notable

La version Streamlit utilisait des variables globales de module (`run_id`,
`rapport`, `ok`, `ko`) réécrites à chaque script-run pour les partager entre
fonctions. Ce pattern est risqué avec un serveur Dash multi-utilisateur (un
seul process Flask sert potentiellement plusieurs analystes en parallèle) —
il a donc été éliminé : chaque vue reçoit maintenant son contexte
explicitement en paramètre.

## 6 · Dépendance réseau côté navigateur (vue arbre M2)

Le rendu de l'arbre Graphviz charge `d3.js`, `@hpcc-js/wasm` et `d3-graphviz`
depuis un CDN, exécuté dans le **navigateur de l'analyste** (pas depuis la
VM). Si les postes des analystes n'ont pas d'accès internet sortant :
- soit héberger ces 3 fichiers JS en local et changer les URLs dans
  `network_view.py::build_graphviz_iframe_srcdoc`,
- soit installer le paquet système `graphviz` sur la VM et rendre le SVG
  côté serveur avec le paquet Python `graphviz` (`pip install graphviz` +
  `apt install graphviz`) — je peux faire ce portage si besoin.

## 7 · Déploiement (cohérent avec ton architecture GCP cible)

Dash = une app Flask sous le capot (`app.server`), donc déployable sur
Cloud Run comme ton FastAPI, via `gunicorn` :

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY dashboard_dash/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY dashboard_dash/ .
# outputs/, data/, scripts/ doivent être accessibles au même niveau relatif
# (montage GCS FUSE ou volume partagé, selon ton architecture)
CMD exec gunicorn --bind :$PORT --workers 2 app:server
```

## 8 · Tests effectués avant livraison

Toutes les vues et tous les callbacks ont été exercés avec un jeu de données
synthétique (run factice, comptes/arêtes M2 générés aléatoirement) :
chargement des 2 pages, sélection de run, bascule entre les 6 vues, les 3
onglets M2 (graphe pyvis / arbre / table), export CSV, upload de fichier,
lancement d'inférence, sondage de progression. Un bug a été trouvé et corrigé
en cours de route (gestion des clics sur les boutons d'export en
pattern-matching). Sans accès à tes vraies données `outputs/runs/`, je n'ai
pas pu valider le rendu avec les volumes et schémas réels — à vérifier en
premier lieu une fois branché sur un vrai run.

## 9 · Étude et principes du thème clair

Le thème privilégie une interface professionnelle de consultation : fond gris
très clair (`#F6F7F9`), surfaces blanches, texte principal bleu-noir
(`#17212B`) et séparateurs gris discrets. L'orange officiel (`#FF7900`) est
conservé comme signature de marque et couleur d'action, mais il n'est pas
utilisé pour du texte courant sur fond blanc, où son contraste serait trop
faible.

Les états utilisent des teintes sémantiques plus sombres : rouge critique
`#B42318`, ambre élevé `#8A4B08`, bleu informatif `#175CD3` et vert conforme
`#067647`. Les couples texte/fond principaux présentent des ratios de contraste
compris entre **5,4:1 et 16,3:1**, supérieurs au seuil WCAG AA de 4,5:1 pour le
texte normal. Les niveaux de risque ne reposent pas uniquement sur la couleur :
ils restent nommés dans les badges, légendes et tableaux.
