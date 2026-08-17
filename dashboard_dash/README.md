# Dashboard Sentinelle — Dash

Interface web principale du projet **Sentinelle**, développée avec **Dash** pour consulter les résultats des traitements batch Mobile Money et piloter les principales vues d'analyse.

Le dashboard propose deux pages fonctionnelles et six vues analytiques :

- Synthèse ;
- M1 — anomalies transactionnelles ;
- M2 — réseaux suspects ;
- M4 — anomalies de commissions ;
- M5 — risque d'échec ;
- M6 — réconciliation.

## Arborescence

```text
dashboard_dash/
├── app.py
├── theme.py
├── data_access.py
├── network_view.py
├── pages/
│   ├── tableau_de_bord.py
│   └── donnees_inference.py
├── assets/
│   └── generated_theme.css
└── requirements.txt
```

Le dossier est situé à la racine du projet, au même niveau que `outputs/`, `scripts/`, `src/` et les autres composants applicatifs.

## Installation

Depuis la racine du dépôt :

```bash
pip install -r dashboard_dash/requirements.txt
```

Ou depuis le dossier du dashboard :

```bash
cd dashboard_dash
pip install -r requirements.txt
```

## Lancement local

Depuis la racine :

```bash
python dashboard_dash/app.py
```

Ou depuis `dashboard_dash/` :

```bash
python app.py
```

L'interface est accessible localement sur :

```text
http://localhost:8050
```

## Architecture de l'interface

### `app.py`

Point d'entrée de l'application Dash. Il initialise l'application, la navigation, le cache et les composants partagés.

### `pages/tableau_de_bord.py`

Page principale de consultation des résultats. Elle regroupe la synthèse et les vues dédiées aux moteurs M1, M2, M4, M5 et M6.

### `pages/donnees_inference.py`

Page permettant de sélectionner les données nécessaires à l'exécution du pipeline et de suivre les traitements associés.

### `data_access.py`

Centralise l'accès aux résultats produits par le pipeline batch, notamment dans `outputs/` et `outputs/runs/`.

### `network_view.py`

Contient les fonctions de visualisation des réseaux du moteur M2 : graphe interactif, vue arborescente et tableaux associés.

### `theme.py`

Centralise les paramètres visuels et les composants de style de l'interface.

### `assets/generated_theme.css`

Feuille de style générée pour l'application Dash. Elle fournit la mise en forme globale du dashboard.

## Composants techniques

L'interface s'appuie notamment sur :

- **Dash** pour l'application web ;
- **Plotly** pour les graphiques ;
- **Dash AG Grid** pour les tableaux interactifs ;
- **Flask-Caching** pour la mise en cache ;
- **PyVis** pour la visualisation du graphe M2 ;
- **PyArrow** pour la lecture des fichiers Parquet ;
- **Gunicorn** pour l'exécution dans un environnement de déploiement compatible.

## Fonctionnement

Le dashboard ne réalise pas directement l'entraînement des modèles. Il exploite les artefacts et résultats générés par le pipeline batch.

Les résultats sont principalement récupérés depuis :

```text
outputs/
outputs/runs/
```

Le dashboard permet notamment :

- de sélectionner un run ;
- de consulter les indicateurs consolidés ;
- d'afficher les alertes par moteur ;
- d'explorer les réseaux suspects du moteur M2 ;
- de filtrer et trier les résultats ;
- d'exporter certains résultats ;
- de déclencher une nouvelle inférence lorsque cette fonctionnalité est disponible dans l'environnement d'exécution ;
- de suivre l'avancement des traitements.

## Vue réseau M2

La vue M2 fournit plusieurs représentations complémentaires :

- graphe interactif PyVis ;
- représentation arborescente ;
- tableau des comptes et relations détectés.

La représentation arborescente utilise des bibliothèques JavaScript chargées côté navigateur. Dans un environnement sans accès Internet sortant, ces dépendances doivent être hébergées localement ou remplacées par un rendu serveur.

## Thème graphique

L'interface utilise un thème clair destiné à une consultation professionnelle :

- fond général gris très clair ;
- cartes et surfaces blanches ;
- texte bleu-noir à fort contraste ;
- orange `#FF7900` comme couleur d'accent et d'action ;
- couleurs sémantiques distinctes pour les niveaux de risque et les états.

Les niveaux de risque restent explicitement nommés dans les badges, légendes et tableaux afin que l'information ne repose pas uniquement sur la couleur.

## Déploiement

Dash repose sur Flask et expose le serveur via `app.server`. L'application peut donc être exécutée avec Gunicorn dans un environnement de conteneurisation ou sur une plateforme compatible.

Exemple de commande :

```bash
gunicorn --bind 0.0.0.0:8050 --workers 2 app:server
```

Dans un conteneur compatible Cloud Run :

```bash
gunicorn --bind :$PORT --workers 2 app:server
```

Les répertoires de données et de résultats nécessaires au dashboard doivent être accessibles depuis l'environnement d'exécution.

## Sécurité

L'application doit être déployée derrière les mécanismes de sécurité adaptés à l'environnement cible :

- contrôle d'accès ;
- authentification centralisée ou reverse proxy ;
- HTTPS/TLS ;
- restrictions réseau ;
- contrôle des fichiers manipulés ;
- gestion des secrets en dehors du dépôt Git.

Les données transactionnelles réelles et les résultats sensibles ne doivent pas être publiés dans le dépôt.

## Production

Avant un déploiement de production :

1. désactiver le mode debug ;
2. exécuter l'application via un serveur WSGI adapté tel que Gunicorn ;
3. vérifier l'accès aux répertoires `outputs/` et aux artefacts nécessaires ;
4. vérifier les règles de sécurité réseau et d'authentification ;
5. tester les différentes vues avec un run représentatif ;
6. valider les performances de la vue réseau M2 sur des volumes réalistes.
