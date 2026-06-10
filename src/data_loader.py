"""
data_loader.py — Chargement des données
========================================
Fonctions de lecture du Parquet nettoyé, avec options d'échantillonnage
et de sélection de colonnes.

Usage :
    from src.data_loader import load_parquet, load_columns
    df = load_parquet(columns=[COL_MONTANT, COL_DATE])
"""

import pandas as pd
import numpy as np
import time
from . import config as cfg


def load_parquet(columns=None, sample_frac=None, verbose=True):
    """
    Charge le Parquet nettoyé.

    Args:
        columns      : liste de colonnes à charger (None = toutes)
        sample_frac  : fraction d'échantillon (None = tout, 0.1 = 10%)
        verbose      : affiche les infos de chargement

    Returns:
        DataFrame
    """
    debut = time.time()
    df = pd.read_parquet(cfg.PARQUET_PATH, columns=columns)

    if sample_frac is not None and 0 < sample_frac < 1:
        df = df.sample(frac=sample_frac, random_state=cfg.RANDOM_SEED).reset_index(drop=True)

    # S'assurer que la date est bien typée
    if cfg.COL_DATE in df.columns and not np.issubdtype(df[cfg.COL_DATE].dtype, np.datetime64):
        df[cfg.COL_DATE] = pd.to_datetime(df[cfg.COL_DATE], errors="coerce")

    if verbose:
        print(f"Chargé en {time.time()-debut:.1f}s")
        print(f"Dimensions : {df.shape[0]:,} lignes × {df.shape[1]} colonnes")
        print(f"RAM        : {df.memory_usage(deep=True).sum()/1024**3:.2f} Go")
        if cfg.COL_DATE in df.columns:
            print(f"Plage      : {df[cfg.COL_DATE].min()} → {df[cfg.COL_DATE].max()}")
            print(f"Jours      : {df[cfg.COL_DATE].dt.date.nunique()}")
    return df


def load_columns(model_name):
    """
    Retourne la liste des colonnes nécessaires à un modèle donné.

    Args:
        model_name : 'M1', 'M2', 'M4', 'M5', 'M6'
    """
    base = [cfg.COL_TRANSFER_ID, cfg.COL_DATE, cfg.COL_SENDER_ID,
            cfg.COL_RECVR_ID, cfg.COL_MONTANT, cfg.COL_SERVICE, cfg.COL_STATUT]

    specifique = {
        "M1": [cfg.COL_S_AVANT, cfg.COL_S_APRES, cfg.COL_R_AVANT, cfg.COL_R_APRES,
               cfg.COL_SUBTYPE, cfg.COL_ERREUR, cfg.COL_VILLE, cfg.COL_GATEWAY,
               cfg.COL_TAG, cfg.COL_ATTEMPT, cfg.COL_S_TYPE, cfg.COL_R_TYPE],
        "M2": [cfg.COL_MSISDN, cfg.COL_VILLE, cfg.COL_VILLE_RECV, cfg.COL_TAG,
               cfg.COL_S_TYPE, cfg.COL_R_TYPE],
        "M4": [cfg.COL_COMM_PAID, cfg.COL_COMM_RECV, cfg.COL_COMM_OTHER,
               cfg.COL_SCHARGE_RCV, cfg.COL_SCHARGE_PAID, cfg.COL_SUBTYPE],
        "M5": [cfg.COL_ERREUR, cfg.COL_S_AVANT, cfg.COL_SUBTYPE, cfg.COL_ATTEMPT,
               cfg.COL_GATEWAY, cfg.COL_S_TYPE, cfg.COL_R_TYPE],
        "M6": [cfg.COL_RECON_BY, cfg.COL_RECON_FOR, cfg.COL_ORIG_REF,
               cfg.COL_EXT_TXN, cfg.COL_REF_NUM, cfg.COL_ACTION, cfg.COL_TAG],
    }
    cols = base + specifique.get(model_name, [])
    return list(dict.fromkeys(cols))  # dédoublonnage en gardant l'ordre


def cast_numeric(df, columns=None):
    """Cast les colonnes numériques en float."""
    columns = columns or [c for c in cfg.COLS_NUM if c in df.columns]
    for col in columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df
