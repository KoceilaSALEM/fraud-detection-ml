"""
Validation des données entrantes — la porte d'entrée du système.

En production, le modèle ne doit JAMAIS planter sur un fichier mal formé :
on valide AVANT de scorer, et on refuse proprement avec un rapport clair.

Contrôles effectués :
  1. Colonnes requises présentes
  2. Volume plausible (ni vide, ni anormalement réduit)
  3. Types convertibles (montants numériques, dates parsables)
  4. Taux de valeurs invalides sous le seuil
"""
from __future__ import annotations

import pandas as pd

from src import config as cfg
from src.exceptions import DonneesInvalidesError
from src.logging_conf import get_logger

logger = get_logger("validation")

# Colonnes indispensables au fonctionnement des 5 modèles
COLONNES_REQUISES = [
    cfg.COL_TRANSFER_ID,
    cfg.COL_DATE,
    cfg.COL_MONTANT,
    cfg.COL_SENDER_ID,
    cfg.COL_RECVR_ID,
    cfg.COL_STATUT,
    cfg.COL_SERVICE,
]


def valider_entree(df: pd.DataFrame, volume_min: int = 1000) -> dict:
    """
    Valide un DataFrame avant inférence. Lève DonneesInvalidesError si bloquant.

    Returns:
        Rapport de validation (dict) avec les contrôles passés et les avertissements.
    """
    rapport = {"controles": [], "avertissements": [], "valide": True}

    # 1. Colonnes requises
    manquantes = [c for c in COLONNES_REQUISES if c not in df.columns]
    if manquantes:
        raise DonneesInvalidesError(
            f"Colonnes requises absentes : {manquantes}. "
            f"Vérifier le format de l'export DWH."
        )
    rapport["controles"].append(f"Colonnes requises présentes ({len(COLONNES_REQUISES)})")

    # 2. Volume
    if len(df) == 0:
        raise DonneesInvalidesError("Fichier vide : aucune transaction.")
    if len(df) < volume_min:
        rapport["avertissements"].append(
            f"Volume faible : {len(df):,} transactions (< {volume_min:,}). "
            "Vérifier que l'export est complet."
        )
    rapport["controles"].append(f"Volume : {len(df):,} transactions")

    # 3. Montants convertibles
    montants = pd.to_numeric(df[cfg.COL_MONTANT], errors="coerce")
    pct_invalides = montants.isna().mean()
    if pct_invalides > 0.05:
        raise DonneesInvalidesError(
            f"{pct_invalides*100:.1f}% de montants non numériques (max 5%). "
            "Fichier probablement corrompu ou mauvais séparateur."
        )
    if pct_invalides > 0:
        rapport["avertissements"].append(
            f"{pct_invalides*100:.2f}% de montants invalides (imputés à 0)"
        )
    rapport["controles"].append("Montants numériques OK")

    # 4. Dates parsables
    if not pd.api.types.is_datetime64_any_dtype(df[cfg.COL_DATE]):
        dates = pd.to_datetime(df[cfg.COL_DATE], errors="coerce")
        pct_dates_ko = dates.isna().mean()
        if pct_dates_ko > 0.05:
            raise DonneesInvalidesError(
                f"{pct_dates_ko*100:.1f}% de dates non parsables (max 5%)."
            )
    rapport["controles"].append("Dates parsables OK")

    # 5. Doublons d'identifiants (information, pas bloquant)
    nb_dups = df[cfg.COL_TRANSFER_ID].duplicated().sum()
    if nb_dups > 0:
        rapport["avertissements"].append(
            f"{nb_dups:,} TRANSFER_ID dupliqués (dédoublonnage appliqué en aval)"
        )

    for c in rapport["controles"]:
        logger.info(f"✓ {c}")
    for a in rapport["avertissements"]:
        logger.warning(f"⚠ {a}")

    return rapport
