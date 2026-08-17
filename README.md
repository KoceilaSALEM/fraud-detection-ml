# Fraud Detection ML

Pipeline batch de détection et d'analyse d'anomalies appliqué à des transactions **Mobile Money**.

Ce dépôt public contient uniquement le **code source** du projet. Les données, modèles entraînés, résultats d'exécution, artefacts et logs sont volontairement exclus afin de préserver la confidentialité des données et de garantir un dépôt reproductible et publiable.

La solution fonctionne en **traitement différé (batch)** à partir de fichiers CSV ou Parquet. Elle ne réalise pas de scoring en temps réel.

## Fonctionnalités

| Moteur | Finalité                                               | Méthode principale                                      |
| ------ | ------------------------------------------------------ | ------------------------------------------------------- |
| **M1** | Détection d'anomalies transactionnelles                | Isolation Forest par groupe de pairs                    |
| **M2** | Détection de comptes de transit et de réseaux suspects | Graphe sparse, PageRank et DBSCAN                       |
| **M4** | Détection d'anomalies de commissions                   | Z-score sur référence historique figée                  |
| **M5** | Estimation du risque d'échec d'une transaction         | LightGBM avec validation temporelle                     |
| **M6** | Réconciliation automatique des transactions            | Blocking, appariement par parties et score de confiance |

## Architecture du projet

```text
fraud-detection-ml/
├── api/
│   └── main.py
│
├── dashboard/
│   └── app.py
│
├── scripts/
│   ├── construire_pretraitement.py
│   ├── construire_references_drift.py
│   ├── publier_modeles.py
│   ├── run_inference.py
│   └── evaluer_hors_temps.py
│
├── src/
│   ├── features/
│   ├── inference/
│   ├── monitoring/
│   ├── ingestion.py
│   └── preprocessing.py
│
├── tests/
│
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

### Composants principaux

* `src/ingestion.py` : lecture des fichiers, contrôle du schéma, conversions de types, dédoublonnage et validation des données.
* `src/preprocessing.py` : gestion des catégories, fréquences, valeurs manquantes et transformations figées à partir des données d'entraînement.
* `src/features/` : construction des variables utilisées par les différents moteurs.
* `src/inference/` : moteurs de détection et orchestration des exécutions.
* `src/monitoring/` : métriques de suivi et détection de dérive des données.
* `api/` : API FastAPI protégée par clé d'accès.
* `dashboard/` : interface web Dash utilisée comme interface unique du projet.
* `tests/` : suite de tests `pytest` unitaires et d'intégration légère.

## Installation

### 1. Créer un environnement virtuel

```bash
python -m venv .venv
```

Sous Linux ou macOS :

```bash
source .venv/bin/activate
```

Sous Windows :

```powershell
.venv\Scripts\activate
```

### 2. Installer les dépendances

```bash
pip install -r requirements-dev.txt
```

### 3. Exécuter les tests

```bash
pytest
```

## Préparation des artefacts

Les répertoires suivants contiennent des éléments générés localement et **ne doivent jamais être publiés** :

```text
data/
models/
outputs/
logs/
```

Les artefacts nécessaires à l'inférence sont construits à partir des données d'entraînement :

```bash
python scripts/construire_pretraitement.py \
  --donnees data/processed/train.parquet

python scripts/construire_references_drift.py \
  --donnees data/processed/train.parquet

python scripts/publier_modeles.py
```

Chaque version publiée des modèles **M1** et **M5** embarque son propre fichier :

```text
preprocessing.json
```

Cet artefact contient notamment :

* les catégories connues ;
* les fréquences calculées ;
* les médianes utilisées pour les imputations ;
* les paramètres de prétraitement nécessaires à l'inférence.

Ces informations sont calculées **uniquement sur la période d'entraînement** afin d'éviter toute fuite d'information provenant des données futures.

L'inférence refuse l'exécution lorsqu'un artefact obligatoire est absent. Elle contrôle également la cohérence des artefacts de prétraitement utilisés par M1 et M5.

## Exécution d'une inférence

Pour analyser un nouveau fichier :

```bash
python scripts/run_inference.py \
  --donnees data/processed/nouveau_mois.parquet
```

Le pipeline d'ingestion est exécuté avant les différents moteurs afin d'appliquer de manière homogène :

1. la lecture des données ;
2. la normalisation du schéma ;
3. les conversions de types ;
4. la validation ;
5. le dédoublonnage.

Les données dédoublonnées sont ensuite transmises aux moteurs de détection.

## Sorties de M6 — Réconciliation

Le moteur M6 distingue les rapprochements automatiques des cas nécessitant une intervention humaine.

Il génère notamment :

```text
M6_reconciliation_scores.parquet
M6_reconciliation_alertes.csv
M6_reconciliation_manuels.csv
```

### `M6_reconciliation_scores.parquet`

Contient les rapprochements automatiques ainsi que leurs scores de confiance.

### `M6_reconciliation_alertes.csv`

Contient les rapprochements proposés lorsque le niveau de confiance nécessite une validation.

### `M6_reconciliation_manuels.csv`

Contient les transactions pour lesquelles aucun candidat suffisamment pertinent n'a été identifié et qui doivent être examinées manuellement.

## Évaluation hors temps

Afin d'éviter d'évaluer les modèles sur une période déjà utilisée lors de leur développement, une évaluation temporelle peut être réalisée sur un mois réellement postérieur à la période d'entraînement.

```bash
python scripts/evaluer_hors_temps.py \
  --donnees data/processed/mois_ulterieur.parquet \
  --fin-entrainement AAAA-MM-JJ \
  --sortie evaluation_hors_temps.json
```

Le script vérifie que la période d'évaluation ne chevauche pas la période d'entraînement.

Dans le cas contraire, l'évaluation est interrompue.

Pour **M5**, les principales métriques supervisées sont notamment :

* ROC-AUC ;
* PR-AUC.

Pour les moteurs non supervisés ou fondés sur des règles statistiques, notamment **M1, M2 et M4**, l'analyse quantitative est complétée par une **validation métier des alertes produites**.

## API FastAPI

L'API permet de déclencher les traitements tout en appliquant plusieurs contrôles de sécurité.

### Configuration

Définir une clé API avant le lancement.

Sous Linux ou macOS :

```bash
export FRAUD_API_KEY="une-cle-longue-et-aleatoire"
```

Sous Windows PowerShell :

```powershell
$env:FRAUD_API_KEY="une-cle-longue-et-aleatoire"
```

Lancer ensuite l'API :

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Les requêtes protégées doivent transmettre l'en-tête :

```text
X-API-Key
```

### Mesures de sécurité

L'API applique notamment les contrôles suivants :

* authentification par clé API ;
* restriction des fichiers aux répertoires autorisés ;
* contrôle des extensions ;
* limitation de la taille des fichiers ;
* validation des chemins ;
* prévention des traversées de répertoires ;
* prévention des exécutions concurrentes non autorisées.

Les fichiers analysés doivent se trouver sous :

```text
data/raw/
```

ou :

```text
data/processed/
```

Les secrets ne doivent jamais être stockés directement dans le code source ou versionnés dans Git.

## Dashboard Dash

Dash constitue l'interface web retenue pour le projet.

### Configuration

Définir les identifiants avant le lancement.

Sous Linux ou macOS :

```bash
export FRAUD_DASH_USER="analyste"
export FRAUD_DASH_PASSWORD="un-secret-long-et-aleatoire"
```

Sous Windows PowerShell :

```powershell
$env:FRAUD_DASH_USER="analyste"
$env:FRAUD_DASH_PASSWORD="un-secret-long-et-aleatoire"
```

Lancer ensuite le dashboard :

```bash
python dashboard/app.py
```

### Sécurisation du téléversement

Le mécanisme de téléversement applique plusieurs contrôles :

* limitation de la taille des fichiers ;
* liste d'extensions autorisées ;
* validation du nom et du chemin du fichier ;
* prévention des traversées de répertoires ;
* rejet des formats non pris en charge.

Les routes du dashboard sont protégées côté serveur par **HTTP Basic**.

Pour un déploiement en production, l'authentification doit idéalement être centralisée au niveau du reverse proxy ou du fournisseur SSO de l'environnement cible. La terminaison TLS doit également être assurée en amont de l'application.

## Tests

La suite de tests repose sur `pytest`.

Pour exécuter l'ensemble des tests :

```bash
pytest
```

Pour obtenir davantage de détails :

```bash
pytest -v
```

Les tests couvrent notamment :

* l'ingestion ;
* la validation du schéma ;
* le dédoublonnage ;
* le prétraitement ;
* les principaux moteurs ;
* les contrôles de sécurité ;
* les scénarios d'intégration légère.

## Confidentialité et publication

Ce dépôt est conçu pour pouvoir être publié sans exposer de données ou d'artefacts internes.

Les éléments suivants doivent rester exclus du versionnement :

```text
data/
models/
outputs/
logs/
.env
*.parquet
*.csv
```

Aucune donnée transactionnelle réelle, clé API, mot de passe, modèle entraîné ou sortie contenant des informations sensibles ne doit être ajoutée au dépôt.

Avant toute publication, vérifier systématiquement les fichiers suivis par Git :

```bash
git status
git ls-files
```

Les secrets doivent être fournis exclusivement par des variables d'environnement ou par le gestionnaire de secrets de l'environnement de déploiement.

## Principes de reproductibilité

Le projet applique plusieurs principes destinés à limiter les écarts entre entraînement, évaluation et inférence :

* pipeline d'ingestion commun aux différents moteurs ;
* dédoublonnage effectué avant l'analyse ;
* prétraitement figé à partir de la période d'entraînement ;
* versionnement des artefacts associés aux modèles ;
* séparation entre données d'entraînement et données d'évaluation ;
* validation temporelle pour les modèles supervisés ;
* contrôles de cohérence avant l'inférence ;
* tests automatisés avec `pytest`.

## Limites du périmètre

La solution est actuellement conçue pour fonctionner en **mode batch** à partir de fichiers CSV ou Parquet.

Elle ne suppose pas l'existence d'un flux transactionnel temps réel et ne revendique donc pas de capacité de scoring en temps réel.

L'architecture permet néanmoins de séparer clairement l'ingestion, le prétraitement, les moteurs de détection, l'API et l'interface afin de faciliter les évolutions futures.
