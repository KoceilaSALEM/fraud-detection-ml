"""
config.py — Configuration centrale du projet Orange Money ML
=============================================================
Toutes les constantes (chemins, noms de colonnes, seuils) sont ici.
Un seul endroit à modifier si quelque chose change.

Usage :
    from src.config import COL_MONTANT, PARQUET_PATH, SEUILS
"""

from pathlib import Path

# ════════════════════════════════════════════════════════════
# CHEMINS
# ════════════════════════════════════════════════════════════
# Racine du projet (2 niveaux au-dessus de ce fichier : src/ -> racine)
ROOT_DIR      = Path(__file__).resolve().parent.parent

DATA_RAW      = ROOT_DIR / "data" / "raw"
DATA_PROC     = ROOT_DIR / "data" / "processed"
MODELS_DIR    = ROOT_DIR / "models"
OUTPUTS_DIR   = ROOT_DIR / "outputs"

CSV_RAW       = DATA_RAW  / "OM_Koceila.csv"
PARQUET_PATH  = DATA_PROC / "OM_clean.parquet"

# Paramètres de lecture du CSV brut
CSV_ENCODING  = "latin-1"
CSV_SEP       = "|"
CHUNK_SIZE    = 500_000

RANDOM_SEED   = 42
DEVISE        = "MGA"   # Ariary malgache

# ════════════════════════════════════════════════════════════
# NOMS DE COLONNES RÉELS (validés par le diagnostic des 80 colonnes)
# ════════════════════════════════════════════════════════════

# --- Identifiants ---
COL_TRANSFER_ID = "TRANSFER_ID"
COL_SENDER_ID   = "SENDER_USER_ID"       # ~100% rempli — clé pour graphe/comportement
COL_RECVR_ID    = "RECEIVER_USER_ID"     # ~99.7% rempli
COL_MSISDN      = "OTHER_MSISDN"          # 27% — usage limité
# NB: INITIATOR_MSISDN abandonné (0.07% rempli, inutilisable)

# --- Montants / soldes ---
COL_MONTANT     = "TRANSACTION_AMOUNT"
COL_S_AVANT     = "SENDER_PRE_BAL"
COL_S_APRES     = "SENDER_POST_BAL"
COL_R_AVANT     = "RECEIVER_PRE_BAL"
COL_R_APRES     = "RECEIVER_POST_BAL"

# --- Commissions (M4) ---
COL_COMM_PAID   = "COMMISSIONS_PAID"
COL_COMM_RECV   = "COMMISSIONS_RECEIVED"
COL_COMM_OTHER  = "COMMISSIONS_OTHERS"
COL_SCHARGE_RCV = "SERVICE_CHARGE_RECEIVED"
COL_SCHARGE_PAID= "SERVICE_CHARGE_PAID"
# NB: TAXES abandonné (1 seule valeur = 0)

# --- Statut / service ---
COL_STATUT      = "TRANSFER_STATUS"      # CIBLE de M5 (TF = échec)
COL_SERVICE     = "SERVICE_TYPE"
COL_SUBTYPE     = "TRANSFER_SUBTYPE"
COL_TAG         = "TRANSACTION_TAG"
COL_ACTION      = "ACTION_TYPE"           # CREATION / ROLLBACK / ... (utile M6)

# --- Erreurs (M5) ---
COL_ERREUR      = "ERROR_CODE"            # 5.85% rempli (présent si échec)
COL_ERR_DESC    = "ERROR_DESC"
COL_ATTEMPT     = "ATTEMPT_STATUS"

# --- Temporel ---
COL_DATE        = "CREATED_ON"
COL_MODIFIED    = "MODIFIED_ON"
COL_TXN_DATETIME= "TRANSFER_DATETIME"

# --- Géo / canal ---
COL_VILLE       = "SENDER_CITY"
COL_VILLE_RECV  = "RECEIVER_CITY"
COL_GATEWAY     = "GATEWAY_TYPE"          # USSD / WEB
COL_REQ_SRC     = "REQUEST_SOURCE"
COL_TXNMODE     = "TXNMODE"

# --- Catégories de compte ---
COL_S_TYPE      = "SENDER_USER_TYPE"      # SUBSCRIBER / MERCHANT / ...
COL_R_TYPE      = "RECEIVER_USER_TYPE"
COL_S_CAT       = "SENDER_CATEGORY_CODE"
COL_R_CAT       = "RECEIVER_CATEGORY_CODE"

# --- Réconciliation (M6) ---
COL_RECON_BY    = "RECONCILIATION_BY"     # 0.3% — c'est la cible de M6
COL_RECON_FOR   = "RECONCILIATION_FOR"
COL_ORIG_REF    = "ORIGINAL_REF_NUMBER"
COL_EXT_TXN     = "EXT_TXN_NUMBER"
COL_REF_NUM     = "REFERENCE_NUMBER"

# ════════════════════════════════════════════════════════════
# GROUPES DE COLONNES
# ════════════════════════════════════════════════════════════

# Colonnes à conserver lors de la conversion Parquet (44 utiles sur 80)
COLS_PARQUET = [
    COL_TRANSFER_ID, COL_SENDER_ID, COL_RECVR_ID, COL_MSISDN,
    "SENDER_WALLET_NUMBER", "RECEIVER_WALLET_NUMBER",
    COL_MONTANT, COL_S_AVANT, COL_S_APRES, COL_R_AVANT, COL_R_APRES,
    COL_COMM_PAID, COL_COMM_RECV, COL_COMM_OTHER, COL_SCHARGE_RCV, COL_SCHARGE_PAID,
    COL_STATUT, COL_SERVICE, COL_SUBTYPE, COL_TAG, COL_ACTION,
    "IS_FINANCIAL", "TRANSFER_DONE",
    COL_ERREUR, COL_ERR_DESC, COL_ATTEMPT,
    COL_DATE, COL_MODIFIED, COL_TXN_DATETIME,
    COL_VILLE, COL_VILLE_RECV, COL_GATEWAY, COL_REQ_SRC, COL_TXNMODE,
    COL_S_TYPE, COL_R_TYPE, COL_S_CAT, COL_R_CAT,
    "SENDER_DOMAIN_CODE", "RECEIVER_DOMAIN_CODE",
    COL_RECON_BY, COL_RECON_FOR, COL_ORIG_REF, COL_EXT_TXN, COL_REF_NUM,
]

# Colonnes numériques (à caster en float)
COLS_NUM = [
    COL_MONTANT, COL_S_AVANT, COL_S_APRES, COL_R_AVANT, COL_R_APRES,
    COL_COMM_PAID, COL_COMM_RECV, COL_COMM_OTHER,
    COL_SCHARGE_RCV, COL_SCHARGE_PAID, COL_ERREUR,
]

# Colonnes dates (à parser)
COLS_DATE = [COL_DATE, COL_MODIFIED, COL_TXN_DATETIME]

# Services dont SENDER_PRE_BAL est structurellement 0 (exclure des ratios solde)
SERVICES_SANS_SOLDE = ["RC", "CASHIN", "B2BCASHOUT", "ENT2REG"]

# ════════════════════════════════════════════════════════════
# SEUILS DE RISQUE (communs à M1, M2, M4)
# ════════════════════════════════════════════════════════════
SEUILS = {
    "operationnel": 70,   # seuil modéré (bleu)
    "eleve":        85,   # seuil élevé (orange)
    "critique":     95,   # seuil critique (rouge) — alerte immédiate
}

# ════════════════════════════════════════════════════════════
# PARAMÈTRES MODÈLES
# ════════════════════════════════════════════════════════════
IFOREST_PARAMS = {
    "n_estimators":  300,
    "contamination": 0.01,
    "max_samples":   "auto",
    "max_features":  1.0,
    "n_jobs":        -1,
    "random_state":  RANDOM_SEED,
}

LIGHTGBM_PARAMS = {
    "objective":      "binary",
    "metric":         "auc",
    "n_estimators":   500,
    "learning_rate":  0.05,
    "num_leaves":     31,
    "class_weight":   "balanced",
    "random_state":   RANDOM_SEED,
    "n_jobs":         -1,
}

# Palette Orange Money (pour dashboard + graphiques)
COULEURS = {
    "orange":   "#FF6B00",
    "bg":       "#0A0D14",
    "card":     "#111827",
    "border":   "#1E2540",
    "critique": "#EF4444",
    "eleve":    "#F59E0B",
    "modere":   "#3B82F6",
    "normal":   "#22C55E",
    "text_dim": "#6B7A99",
}

# ════════════════════════════════════════════════════════════
# LECTURE DE config/config.yaml (ajout v1.0 — rétrocompatible)
# Les constantes ci-dessus restent la référence pour les noms de
# colonnes et chemins. Le YAML pilote les paramètres MÉTIER
# (seuils, budgets d'alertes) modifiables sans toucher au code.
# ════════════════════════════════════════════════════════════
import yaml as _yaml

_CONFIG_YAML = ROOT_DIR / "config" / "config.yaml"


def charger_config() -> dict:
    """Charge config/config.yaml. Retourne {} si absent (rétrocompatible)."""
    if _CONFIG_YAML.exists():
        with open(_CONFIG_YAML, "r", encoding="utf-8") as f:
            return _yaml.safe_load(f) or {}
    return {}


CFG = charger_config()
