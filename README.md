# Fraud Detection ML — Sentinelle

Pipeline batch d'analyse de transactions **Mobile Money** combinant détection d'anomalies, analyse de réseaux, contrôle des commissions, estimation du risque d'échec et réconciliation.

Le projet est conçu pour fonctionner en **traitement différé (batch)** à partir de fichiers CSV ou Parquet. Il ne réalise pas de scoring transactionnel en temps réel.

> **Confidentialité** — Les données transactionnelles réelles, secrets, journaux d'exécution et résultats contenant des informations sensibles ne doivent pas être versionnés. Les répertoires prévus pour les artefacts locaux sont conservés dans l'arborescence mais leur contenu généré est exclu par `.gitignore`.

## Fonctionnalités

| Moteur | Finalité | Méthode principale |
| --- | --- | --- |
| **M1** | Détection d'anomalies transactionnelles | Isolation Forest par groupe de pairs |
| **M2** | Détection de comptes de transit et réseaux suspects | Graphe sparse, PageRank et DBSCAN |
| **M4** | Détection d'anomalies de commissions | Référence historique et détection statistique |
| **M5** | Estimation du risque d'échec d'une transaction | LightGBM |
| **M6** | Réconciliation automatique des transactions | Blocking, appariement et score de confiance |

Le moteur M3, étudié pendant la phase d'exploration, n'est pas inclus dans la version retenue du pipeline.

## Architecture

```text
fraud-detection-ml/
├── api/                 # API FastAPI de consultation et déclenchement batch
├── config/              # Configuration du pipeline
├── dashboard_dash/      # Interface web Dash
├── logs/                # Journaux générés localement
├── models/              # Artefacts et versions de modèles
├── notebooks/           # Notebooks de préparation et d'expérimentation retenus
├── outputs/             # Résultats des exécutions batch
├── scripts/             # Scripts d'exploitation et de préparation
├── src/                 # Code Python principal
│   ├── features/        # Construction des variables
│   ├── inference/       # Pipeline et moteurs d'inférence
│   └── monitoring/      # Suivi des exécutions et dérive
├── tests/               # Tests automatisés
├── requirements.txt
└── README.md
```

### Code principal

Le package `src/` regroupe notamment :

- `config.py` : chargement et gestion de la configuration ;
- `data_loader.py` : chargement des données ;
- `validation.py` : contrôles de validation ;
- `registry.py` : gestion des versions et artefacts des modèles ;
- `logging_conf.py` : configuration des journaux ;
- `features/` : feature engineering ;
- `inference/` : orchestration et exécution des moteurs ;
- `monitoring/` : métriques et suivi de dérive.

## Installation

Python 3.10 ou version ultérieure est recommandé.

### 1. Cloner le dépôt et créer un environnement virtuel

```bash
git clone <URL_DU_DEPOT>
cd fraud-detection-ml
python -m venv .venv
```

Activation sous Linux/macOS :

```bash
source .venv/bin/activate
```

Activation sous Windows PowerShell :

```powershell
.venv\Scripts\Activate.ps1
```

### 2. Installer les dépendances du pipeline

```bash
pip install -r requirements.txt
```

### 3. Installer les dépendances du dashboard

```bash
pip install -r dashboard_dash/requirements.txt
```

## Données

Le pipeline travaille à partir de fichiers **CSV** ou **Parquet**.

Les données réelles ne font pas partie du dépôt et doivent être fournies séparément dans l'environnement d'exécution autorisé.

Les fichiers de données (`*.csv`, `*.parquet`, `*.xlsx`, etc.) sont exclus du versionnement par `.gitignore`.

## Notebooks conservés

La version de remise conserve uniquement les notebooks nécessaires à la traçabilité des principales étapes :

```text
notebooks/
├── 01_conversion_parquet.ipynb
├── 01_conversion_parquet_executed.ipynb
├── M1_fraude/02_M1_isolation_forest_executed.ipynb
├── M2_mules/03_M2_mules_executed.ipynb
├── M4_commissions/04_M4_anomalies_commissions_executed.ipynb
├── M5_echec/05_M5_lightgbm_echec_executed.ipynb
└── M6_reconciliation/06_M6_reconciliation_v3_executed.ipynb
```

Les versions intermédiaires et notebooks d'exploration devenus obsolètes ne font pas partie de la version de remise.

## Scripts disponibles

Le dossier `scripts/` contient les points d'entrée d'exploitation actuellement conservés :

```text
scripts/
├── construire_reference_m4.py
├── construire_references_drift.py
├── publier_modeles.py
└── run_inference.py
```

### Construire la référence M4

```bash
python scripts/construire_reference_m4.py --help
```

### Construire les références de dérive

```bash
python scripts/construire_references_drift.py --help
```

### Publier les modèles

```bash
python scripts/publier_modeles.py --help
```

### Lancer une inférence batch

```bash
python scripts/run_inference.py --help
```

L'option `--help` permet de consulter les paramètres attendus par la version du script présente dans le dépôt avant toute exécution sur des données.

## Résultats et artefacts

Les répertoires suivants sont utilisés à l'exécution :

```text
models/
outputs/
logs/
```

- `models/` contient les artefacts nécessaires aux moteurs lorsqu'ils sont disponibles localement ;
- `outputs/` reçoit les résultats des traitements et les rapports de runs ;
- `logs/` reçoit les journaux applicatifs.

Ces éléments doivent être manipulés conformément aux règles de confidentialité de l'environnement cible. Les nouveaux artefacts générés dans ces répertoires sont exclus du versionnement.

## API FastAPI

L'API se trouve dans `api/main.py`.

Elle permet principalement :

- de vérifier l'état du système avec `/health` ;
- de consulter les modèles publiés avec `/modeles` ;
- de consulter l'historique et les rapports de runs ;
- de consulter les alertes et informations de drift ;
- de déclencher une inférence batch avec `POST /inference`.

Lancement :

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Documentation OpenAPI une fois le serveur démarré :

```text
http://localhost:8000/docs
```

### Sécurité de l'API

La version actuelle de `api/main.py` ne doit **pas être exposée directement sur Internet**. L'authentification et le contrôle d'accès doivent être assurés par l'environnement de déploiement (reverse proxy, IAM, réseau privé ou mécanisme équivalent) avant une utilisation en production.

Le paramètre transmis à `POST /inference` correspond à un chemin de fichier accessible par le serveur. Il doit donc être contrôlé dans un environnement de production.

## Dashboard Dash

L'interface utilisateur active est située dans `dashboard_dash/`.

Installation et lancement depuis la racine :

```bash
pip install -r dashboard_dash/requirements.txt
python dashboard_dash/app.py
```

Par défaut, l'application Dash est accessible localement sur le port configuré par l'application, généralement :

```text
http://localhost:8050
```

Le dashboard fournit des vues dédiées à la synthèse et aux moteurs M1, M2, M4, M5 et M6. Il exploite les résultats produits par le pipeline batch.

Pour les détails spécifiques à l'interface, consulter `dashboard_dash/README.md`.

## Tests

Les tests automatisés sont regroupés dans `tests/` et utilisent `pytest`.

```bash
pytest
```

ou, en mode détaillé :

```bash
pytest -v
```

Avant toute remise ou mise en production, la suite de tests doit être exécutée dans un environnement propre avec les dépendances installées.

## Confidentialité et règles de versionnement

Ne jamais ajouter au dépôt :

- données transactionnelles réelles ;
- identifiants clients ou données personnelles ;
- mots de passe, clés API ou jetons ;
- fichiers `.env` ;
- credentials cloud ;
- journaux contenant des informations internes ;
- exports CSV/Parquet issus de données réelles ;
- nouveaux artefacts de modèles ou résultats non validés pour diffusion.

Avant chaque publication :

```bash
git status
git diff --cached
git ls-files
```

La suppression d'un fichier dans un commit récent ne le retire pas automatiquement de l'historique Git. Pour une publication externe, l'historique du dépôt doit donc également faire l'objet d'une vérification de confidentialité.

## Reproductibilité

Le projet sépare volontairement :

1. les données d'entrée ;
2. le code de préparation et de feature engineering ;
3. les moteurs d'analyse ;
4. les artefacts de modèles ;
5. les résultats d'exécution ;
6. l'API de consultation ;
7. le dashboard de restitution.

Cette organisation permet de faire évoluer les différents composants sans confondre le code source, les données et les sorties générées.

## Périmètre

Cette version constitue un pipeline analytique **batch** pour l'étude et la détection de comportements à risque dans des transactions Mobile Money.

Elle est destinée à l'analyse différée de fichiers et à la restitution des résultats via une API et un dashboard. Elle ne revendique pas de traitement ni de scoring transactionnel temps réel.
