# Fraud Detection ML

Pipeline batch générique pour la détection d'anomalies sur des transactions Mobile Money.
Le dépôt public contient uniquement le code : données, modèles entraînés, résultats et logs
sont exclus volontairement.

## Fonctionnalités

| Moteur | Finalité | Méthode |
|---|---|---|
| M1 | Anomalies transactionnelles | Isolation Forest par groupe de pairs |
| M2 | Comptes de transit et réseaux | Graphe sparse, PageRank et DBSCAN |
| M4 | Anomalies de commissions | Z-score contre une référence historique figée |
| M5 | Risque d'échec | LightGBM avec validation temporelle |
| M6 | Réconciliation | Blocking, parties et score de confiance |

La solution fonctionne en traitement différé sur fichiers CSV ou Parquet. Elle ne prétend
pas effectuer du scoring temps réel.

## Architecture

- `src/ingestion.py` : lecture, schéma, conversions, dédoublonnage et validation.
- `src/preprocessing.py` : catégories, fréquences et imputations figées.
- `src/features/` : construction des variables.
- `src/inference/` : moteurs et orchestration des runs.
- `src/monitoring/` : métriques et dérive des données.
- `api/` : API FastAPI protégée par clé.
- `dashboard/` : interface Dash retenue comme interface unique.
- `tests/` : tests pytest unitaires et d'intégration légère.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate  # Windows : .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest
