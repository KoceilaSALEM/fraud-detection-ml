# Orange Money — Système ML Fraude & Revenue Assurance

Système de 5 modèles ML + dashboard unifié pour la direction RA&FM.
Auteur : Koceila SALEM.

## Données
- Source : export DWH Orange Money (CSV, séparateur `|`, encodage latin-1)
- Période : 32 jours (29/08/2025 → 30/09/2025), ~30M transactions
- Devise : Ariary malgache (MGA)

## Modèles
| ID | Modèle | Algorithme | Statut |
|----|--------|-----------|--------|
| M1 | Détection fraude | Isolation Forest (non supervisé) | En cours |
| M2 | Réseaux de mules | Graphe + DBSCAN | À faire |
| M4 | Anomalies commissions | Z-score vs référence historique figée | Fonctionnel |
| M5 | Prédiction d'échec | LightGBM (supervisé, cible=TF) | À faire |
| M6 | Réconciliation | Record linkage (blocking + parties) | Fonctionnel |

### Sorties de la réconciliation M6
- `M6_reconciliation_scores.parquet` : appariements automatiques (confiance ≥ seuil)
- `M6_reconciliation_alertes.csv` : suggestions à valider par un analyste
- `M6_reconciliation_manuels.csv` : cas sans candidat compatible

La somme des trois catégories est contrôlée à chaque run et doit être égale
au nombre total de transactions à réconcilier.

> M3 (SIM Swap) abandonné : signaux insuffisants dans les données
> (SENDER_ACC_STATUS constant, INITIATOR_MSISDN à 0.07%).

## Workflow
```
1. notebooks/01_conversion_parquet.ipynb   # CSV → Parquet (une fois)
2. notebooks/Mx_xxx/...                      # entraîner chaque modèle
3. dashboard/  → streamlit run app.py        # visualiser
```

## Architecture
- `src/config.py` : toutes les constantes (colonnes, seuils, chemins)
- `src/features/` : 4 blocs de features réutilisables (A/B/C/D)
- `src/data_loader.py` : chargement Parquet
- `src/utils.py` : scoring 0-100, formatage MGA

## Installation
```bash
pip install -r requirements.txt
```
