# Orange Money — Fraud Monitor Dashboard (M1)

Dashboard Streamlit pour le **Modèle 1 — Détection de fraude**  
Isolation Forest v2 · 67 features · Direction RA&FM

---

## Structure du projet

```
streamlit_M1/
├── app.py                              ← Page principale (Fraud Monitor D1)
├── pages/
│   ├── 1_🔍_Scorer_une_transaction.py  ← Scoring temps réel d'une transaction
│   ├── 2_👤_Analyse_compte.py          ← Fiche comportementale par compte
│   └── 3_📊_Rapport_modèle.py          ← Stats globales & fiche technique IF
├── .streamlit/
│   └── config.toml                     ← Thème dark Orange Money
├── requirements.txt
└── README.md
```

---

## Prérequis

### 1. Environnement Python

```bash
pip install -r requirements.txt
```

### 2. Fichiers nécessaires (générés par le notebook 02 v2)

Placer dans le répertoire de lancement :

```
outputs/M1_fraude_v2/
├── M1_scored_v2.parquet           ← Dataset 500k lignes scoré
├── M1_isolation_forest_v2.pkl     ← Modèle Isolation Forest
├── M1_scaler_v2.pkl               ← RobustScaler
└── M1_params_v2.json              ← Paramètres & feature list
```

---

## Lancement

```bash
# Depuis le dossier streamlit_M1/
streamlit run app.py
```

Le dashboard s'ouvre automatiquement sur `http://localhost:8501`

---

## Pages du dashboard

| Page | Description |
|------|-------------|
| **Fraud Monitor** (app.py) | Vue principale : KPIs, distribution des scores, alertes par service/ville, top comptes suspects, table des alertes exportable |
| **Scorer une transaction** | Formulaire de saisie manuelle → score 0–100 en temps réel avec jauge et liste des facteurs de risque |
| **Analyse compte** | Fiche individuelle d'un compte : timeline du score, répartition des services, top destinataires, détail des alertes |
| **Rapport modèle** | Pyramide des risques, boxplots par service/statut, heatmap heure×service, matrice de concordance IF vs règles métier, fiche technique |

---

## Paramétrage

### Changer les seuils d'alerte

Dans `app.py` (et les autres pages), modifier les constantes :

```python
SEUIL_OPERATIONNEL = 70.0   # Seuil modéré (bleu)
SEUIL_ELEVE        = 85.0   # Seuil élevé (orange)
SEUIL_CRITIQUE     = 95.0   # Seuil critique (rouge)
```

### Changer les chemins des fichiers

Via la **sidebar** de chaque page, ou directement dans le code :

```python
parquet_path = "outputs/M1_fraude_v2/M1_scored_v2.parquet"
model_path   = "outputs/M1_fraude_v2/M1_isolation_forest_v2.pkl"
scaler_path  = "outputs/M1_fraude_v2/M1_scaler_v2.pkl"
params_path  = "outputs/M1_fraude_v2/M1_params_v2.json"
```

### Mise à jour quotidienne des données

Remplacer `M1_scored_v2.parquet` par le nouveau fichier scoré après chaque export DWH.  
Le modèle `.pkl` n'a pas besoin d'être ré-entraîné chaque jour — il peut scorer les nouvelles transactions directement.

---

## Architecture technique

```
Flux de données quotidien :
DWH Export (CSV) → Notebook 02 v2 → M1_scored_v2.parquet → Streamlit Dashboard
                                  ↘ M1_alertes_v2.csv (pour les analystes)
```

### Modèle Isolation Forest v2

| Paramètre | Valeur |
|-----------|--------|
| Algorithme | Isolation Forest |
| n_estimators | 300 |
| contamination | 1% |
| max_samples | auto (256) |
| Scaler | RobustScaler |
| Features | 67 (4 blocs A/B/C/D) |
| Base compte | SENDER_USER_ID |

### Corrections v2 vs v1

| Fix | Problème v1 | Solution v2 |
|-----|-------------|-------------|
| FIX 1 | INITIATOR_MSISDN NaN pour 50% des tx | Feature `f_has_msisdn` + Bloc C sur `SENDER_USER_ID` |
| FIX 2 | Règle R2 capte 12.8% (RC avec solde=0) | Ratio montant/solde désactivé pour RC, CASHIN, B2BCASHOUT, ENT2REG |
| FIX 3 | Bloc C : 499 680 NaN → signal nul | Recalcul sur `SENDER_USER_ID` (100% rempli) |

---

## Export des alertes

Chaque page offre un bouton **⬇ Exporter CSV** pour télécharger :
- La liste des alertes filtrées (page principale)
- Les alertes d'un compte spécifique (page analyse compte)

Format : CSV UTF-8 avec BOM (compatible Excel)

---

## Auteur

**Koceila SALEM**  
Direction Revenue Assurance & Fraude Télécom — Orange Money  
Projet ML Fraude & Revenue Assurance
