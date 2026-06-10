"""
bloc_d_contextuel.py — Features contextuelles
==============================================
Encodages des variables catégorielles : statut, service, canal, etc.
OHE pour faible cardinalité, fréquence encoding sinon.
"""

import pandas as pd
from .. import config as cfg


def build(df):
    """Ajoute les features contextuelles (encodages)."""
    nouvelles = []

    # TRANSFER_STATUS — OHE
    dummies = pd.get_dummies(df[cfg.COL_STATUT], prefix="f_statut")
    df = pd.concat([df, dummies], axis=1)
    nouvelles += list(dummies.columns)

    # SERVICE_TYPE — fréquence
    df["f_service_freq"] = df[cfg.COL_SERVICE].map(
        df[cfg.COL_SERVICE].value_counts(normalize=True))
    nouvelles.append("f_service_freq")

    # ERROR_CODE — présence binaire
    df["f_has_error"] = df[cfg.COL_ERREUR].notna().astype(int)
    nouvelles.append("f_has_error")

    # SENDER_CITY — fréquence
    if cfg.COL_VILLE in df.columns:
        df["f_ville_freq"] = df[cfg.COL_VILLE].map(
            df[cfg.COL_VILLE].value_counts(normalize=True)).fillna(0)
        nouvelles.append("f_ville_freq")

    # GATEWAY_TYPE — OHE
    if cfg.COL_GATEWAY in df.columns and df[cfg.COL_GATEWAY].nunique() <= 5:
        dummies = pd.get_dummies(df[cfg.COL_GATEWAY], prefix="f_gw")
        df = pd.concat([df, dummies], axis=1)
        nouvelles += list(dummies.columns)

    # TRANSFER_SUBTYPE — fréquence
    if cfg.COL_SUBTYPE in df.columns:
        df["f_subtype_freq"] = df[cfg.COL_SUBTYPE].map(
            df[cfg.COL_SUBTYPE].value_counts(normalize=True)).fillna(0)
        nouvelles.append("f_subtype_freq")

    # TRANSACTION_TAG — fréquence
    if cfg.COL_TAG in df.columns:
        df["f_tag_freq"] = df[cfg.COL_TAG].map(
            df[cfg.COL_TAG].value_counts(normalize=True)).fillna(0)
        nouvelles.append("f_tag_freq")

    # ATTEMPT_STATUS — OHE
    if cfg.COL_ATTEMPT in df.columns:
        dummies = pd.get_dummies(df[cfg.COL_ATTEMPT], prefix="f_attempt")
        df = pd.concat([df, dummies], axis=1)
        nouvelles += list(dummies.columns)

    # USER_TYPE émetteur/récepteur — OHE
    for col, pfx in [(cfg.COL_S_TYPE, "f_stype"), (cfg.COL_R_TYPE, "f_rtype")]:
        if col in df.columns and df[col].nunique() <= 6:
            dummies = pd.get_dummies(df[col], prefix=pfx)
            df = pd.concat([df, dummies], axis=1)
            nouvelles += list(dummies.columns)

    df.attrs["bloc_d_features"] = nouvelles
    return df


def feature_names(df=None):
    """
    Les noms du Bloc D dépendent des modalités présentes (OHE dynamique).
    Passer le df après build() pour récupérer la liste exacte, ou lire
    df.attrs['bloc_d_features'].
    """
    if df is not None and "bloc_d_features" in df.attrs:
        return df.attrs["bloc_d_features"]
    return ["f_service_freq", "f_has_error", "f_ville_freq",
            "f_subtype_freq", "f_tag_freq"]  # minimum garanti
