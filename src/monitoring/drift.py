"""
Détection de dérive des données (data drift) — PSI.

Pourquoi le PSI (Population Stability Index) :
  - métrique de référence en finance pour le suivi de distribution
  - adapté au batch (compare le nouveau lot à la référence d'entraînement)
  - interprétable : un nombre, des seuils standards
      PSI < 0.10        -> stable
      0.10 <= PSI < 0.25 -> ATTENTION (à surveiller)
      PSI >= 0.25       -> ALERTE (investigation/réentraînement)

Référence figée à l'entraînement (quantiles), comparée à chaque run.
On surveille aussi la distribution des SCORES produits (prediction drift) :
un glissement des scores signale que le modèle voit des données inhabituelles.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.logging_conf import get_logger

logger = get_logger("monitoring.drift")

# Seuils standards de l'industrie (cf. littérature PSI)
PSI_ATTENTION = 0.10
PSI_ALERTE = 0.25


# ─────────────────────────────────────────────────────────────────────
# 1. À L'ENTRAÎNEMENT : figer la référence
# ─────────────────────────────────────────────────────────────────────
def construire_reference(serie: pd.Series, n_bins: int = 10) -> dict:
    """
    Construit la référence de distribution d'une variable (à l'entraînement).
    Bins par quantiles -> robuste aux distributions asymétriques (montants).
    """
    s = pd.to_numeric(serie, errors="coerce").dropna()
    quantiles = np.quantile(s, np.linspace(0, 1, n_bins + 1))
    quantiles = np.unique(quantiles)               # gère les valeurs répétées
    effectifs, _ = np.histogram(s, bins=quantiles)
    proportions = effectifs / max(effectifs.sum(), 1)
    return {
        "bins": quantiles.tolist(),
        "proportions": proportions.tolist(),
        "n_reference": int(len(s)),
        "moyenne": float(s.mean()),
        "mediane": float(s.median()),
    }


def sauvegarder_references(references: dict, chemin: Path) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(references, indent=2), encoding="utf-8")
    logger.info(f"Références de drift sauvegardées : {chemin}")


# ─────────────────────────────────────────────────────────────────────
# 2. À L'INFÉRENCE : comparer le nouveau lot
# ─────────────────────────────────────────────────────────────────────
def psi(serie_nouvelle: pd.Series, reference: dict) -> float:
    """
    PSI entre la distribution du nouveau lot et la référence figée.
    PSI = somme[(p_nouveau - p_ref) * ln(p_nouveau / p_ref)] par bin.
    """
    s = pd.to_numeric(serie_nouvelle, errors="coerce").dropna()
    bins = np.array(reference["bins"])
    p_ref = np.array(reference["proportions"], dtype=float)

    effectifs, _ = np.histogram(s, bins=bins)
    p_new = effectifs / max(effectifs.sum(), 1)

    # éviter log(0) : plancher epsilon standard
    eps = 1e-4
    p_ref = np.clip(p_ref, eps, None)
    p_new = np.clip(p_new, eps, None)
    return float(np.sum((p_new - p_ref) * np.log(p_new / p_ref)))


def verdict_psi(valeur: float) -> str:
    if valeur >= PSI_ALERTE:
        return "ALERTE"
    if valeur >= PSI_ATTENTION:
        return "ATTENTION"
    return "stable"


def rapport_drift(df_nouveau: pd.DataFrame, references: dict,
                  variation_volume_max: float = 0.50) -> dict:
    """
    Rapport de drift complet d'un nouveau lot vs la référence d'entraînement.

    Args:
        df_nouveau: données du nouveau run
        references: dict {nom_variable: reference} produit à l'entraînement
                    + clé spéciale '_volume' (nb de lignes de référence)
    Returns:
        dict avec PSI par variable, verdicts, et drift de volume.
    """
    rapport = {"variables": {}, "globaux": {}, "verdict_global": "stable"}
    pire = "stable"
    ordre = {"stable": 0, "ATTENTION": 1, "ALERTE": 2}

    for var, ref in references.items():
        if var.startswith("_") or var not in df_nouveau.columns:
            continue
        valeur = psi(df_nouveau[var], ref)
        v = verdict_psi(valeur)
        rapport["variables"][var] = {"psi": round(valeur, 4), "verdict": v}
        if ordre[v] > ordre[pire]:
            pire = v
        logger.info(f"PSI {var} = {valeur:.4f} [{v}]")

    # Drift de volume (un export à moitié vide est un signal majeur)
    if "_volume" in references:
        n_ref = references["_volume"]
        n_new = len(df_nouveau)
        variation = abs(n_new - n_ref) / max(n_ref, 1)
        verdict_vol = "ALERTE" if variation > variation_volume_max else "stable"
        rapport["globaux"]["volume"] = {
            "reference": n_ref, "nouveau": n_new,
            "variation_pct": round(variation * 100, 1), "verdict": verdict_vol,
        }
        if ordre[verdict_vol] > ordre[pire]:
            pire = verdict_vol

    rapport["verdict_global"] = pire
    logger.info(f"Verdict drift global : {pire}")
    return rapport
