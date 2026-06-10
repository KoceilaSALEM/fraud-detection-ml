"""
bloc_a_transaction.py — Features transactionnelles
===================================================
Montants, soldes, ratios, cohérence comptable.
Partagé par M1 (fraude) et M5 (échec).
"""

import numpy as np
import pandas as pd
from .. import config as cfg


def build(df):
    """
    Ajoute les features du Bloc A au DataFrame (in place + retour).
    Préfixe : f_

    Prérequis : colonnes numériques déjà castées (data_loader.cast_numeric).
    """
    mask_sans_solde = df[cfg.COL_SERVICE].isin(cfg.SERVICES_SANS_SOLDE)

    # Log du montant (compresse la distribution skewed)
    df["f_log_montant"] = np.log1p(df[cfg.COL_MONTANT].clip(lower=0))

    # Ratio montant / solde émetteur — sentinelle -2 pour services sans solde
    df["f_ratio_montant_solde"] = np.where(
        mask_sans_solde, -2,
        np.where(df[cfg.COL_S_AVANT] > 0,
                 (df[cfg.COL_MONTANT] / (df[cfg.COL_S_AVANT] + 1)).clip(0, 10), -1)
    )

    # Cohérence comptable émetteur
    df["f_delta_solde"]     = df[cfg.COL_S_APRES] - df[cfg.COL_S_AVANT]
    df["f_log_incoherence"] = np.log1p(
        np.abs(df["f_delta_solde"] + df[cfg.COL_MONTANT]).clip(lower=0))

    # Solde après nul (vide total du compte)
    df["f_solde_apres_nul"] = (df[cfg.COL_S_APRES] <= 0).astype(int)

    # Montants ronds
    df["f_montant_arrondi"]      = (df[cfg.COL_MONTANT] % 1_000  == 0).astype(int)
    df["f_montant_tres_arrondi"] = (df[cfg.COL_MONTANT] % 10_000 == 0).astype(int)

    # Log solde avant
    df["f_log_solde_avant"] = np.log1p(df[cfg.COL_S_AVANT].clip(lower=0))

    # Cohérence solde récepteur
    df["f_incoherence_recvr"] = np.log1p(
        np.abs((df[cfg.COL_R_APRES] - df[cfg.COL_R_AVANT]) - df[cfg.COL_MONTANT]).clip(lower=0))

    return df


def feature_names():
    """Liste des features produites par ce bloc."""
    return ["f_log_montant", "f_ratio_montant_solde", "f_delta_solde",
            "f_log_incoherence", "f_solde_apres_nul", "f_montant_arrondi",
            "f_montant_tres_arrondi", "f_log_solde_avant", "f_incoherence_recvr"]
