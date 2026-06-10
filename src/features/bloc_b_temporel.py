"""
bloc_b_temporel.py — Features temporelles
==========================================
Heure (encodage cyclique), jour de semaine, nuit/soirée/weekend.
Nécessite 32 jours de données pour que le weekend soit pertinent.
"""

import numpy as np
import pandas as pd
from .. import config as cfg


def build(df):
    """
    Ajoute les features temporelles. Prérequis : COL_DATE typé datetime.
    """
    h = df[cfg.COL_DATE].dt.hour
    j = df[cfg.COL_DATE].dt.dayofweek

    # Encodage cyclique heure (continuité 23h -> 0h)
    df["f_heure_sin"] = np.sin(2 * np.pi * h / 24)
    df["f_heure_cos"] = np.cos(2 * np.pi * h / 24)

    # Encodage cyclique jour de semaine
    df["f_jour_sin"] = np.sin(2 * np.pi * j / 7)
    df["f_jour_cos"] = np.cos(2 * np.pi * j / 7)

    # Flags binaires
    df["f_est_nuit"]    = h.between(0, 5).astype(int)
    df["f_est_soiree"]  = h.between(20, 23).astype(int)
    df["f_est_weekend"] = j.isin([5, 6]).astype(int)

    return df


def feature_names():
    return ["f_heure_sin", "f_heure_cos", "f_jour_sin", "f_jour_cos",
            "f_est_nuit", "f_est_soiree", "f_est_weekend"]
