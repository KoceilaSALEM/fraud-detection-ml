"""
utils.py — Fonctions utilitaires
=================================
Helpers communs : normalisation de score 0-100, formatage des montants,
niveaux de risque.
"""

import numpy as np
import pandas as pd
from . import config as cfg


def score_to_risk(scores_bruts, method="percentile"):
    """
    Convertit les scores bruts d'un détecteur d'anomalies (ex: Isolation
    Forest score_samples, négatif = anormal) en score de risque 0-100.

    Args:
        scores_bruts : array de scores (plus négatif = plus anormal)
        method : 'percentile' (recommandé) ou 'minmax'
            - 'percentile' : rang percentile -> distribution uniforme 0-100,
              les seuils 70/85/95 correspondent aux 30%/15%/5% plus suspects.
              Évite que quelques scores extrêmes écrasent toute la distribution.
            - 'minmax' : normalisation linéaire (sensible aux outliers).

    Returns:
        (risk_score array, meta dict) — meta à sauvegarder pour rescorer
        de nouvelles transactions de façon cohérente.
    """
    scores_inv = -np.asarray(scores_bruts)  # plus élevé = plus suspect

    if method == "percentile":
        # Rang percentile : chaque score devient son rang relatif (0-100)
        ranks = pd.Series(scores_inv).rank(pct=True).to_numpy()
        risk = (ranks * 100).clip(0, 100)
        meta = {
            "method": "percentile",
            # quantiles de référence pour rescorer de nouvelles données
            "ref_scores": np.quantile(scores_inv, np.linspace(0, 1, 101)).tolist(),
        }
    else:  # minmax
        s_min, s_max = scores_inv.min(), scores_inv.max()
        risk = ((scores_inv - s_min) / (s_max - s_min) * 100).clip(0, 100)
        meta = {"method": "minmax", "score_min": float(s_min), "score_max": float(s_max)}

    return risk, meta


def rescore_new(scores_bruts, meta):
    """Rescore de nouvelles transactions avec la calibration sauvegardée."""
    scores_inv = -np.asarray(scores_bruts)
    if meta["method"] == "percentile":
        ref = np.asarray(meta["ref_scores"])
        # position de chaque score dans la distribution de référence
        ranks = np.searchsorted(ref, scores_inv) / (len(ref) - 1)
        return (ranks * 100).clip(0, 100)
    else:
        s_min, s_max = meta["score_min"], meta["score_max"]
        return ((scores_inv - s_min) / (s_max - s_min) * 100).clip(0, 100)


def apply_risk_levels(df, score_col="RISK_SCORE"):
    """Ajoute une colonne RISK_LEVEL (Normal/Modéré/Élevé/Critique)."""
    df["RISK_LEVEL"] = pd.cut(
        df[score_col],
        bins=[0, cfg.SEUILS["operationnel"], cfg.SEUILS["eleve"],
              cfg.SEUILS["critique"], 100],
        labels=["Normal", "Modéré", "Élevé", "Critique"],
        include_lowest=True,
    )
    return df


def format_montant(x, devise=None):
    """
    Formate un montant avec l'unité adaptée à son échelle.
    Ex: 1_500_000_000 -> '1.50 Mrd MGA'
    """
    devise = devise or cfg.DEVISE
    if pd.isna(x):
        return "—"
    if x >= 1e9:
        return f"{x/1e9:.2f} Mrd {devise}"
    if x >= 1e6:
        return f"{x/1e6:.1f} M {devise}"
    if x >= 1e3:
        return f"{x/1e3:.0f} K {devise}"
    return f"{x:.0f} {devise}"


def niveau_badge(score):
    """Retourne (label, couleur, emoji) selon le score."""
    if score >= cfg.SEUILS["critique"]:
        return "CRITIQUE", cfg.COULEURS["critique"], "🔴"
    if score >= cfg.SEUILS["eleve"]:
        return "ÉLEVÉ", cfg.COULEURS["eleve"], "🟠"
    if score >= cfg.SEUILS["operationnel"]:
        return "MODÉRÉ", cfg.COULEURS["modere"], "🟡"
    return "NORMAL", cfg.COULEURS["normal"], "🟢"
