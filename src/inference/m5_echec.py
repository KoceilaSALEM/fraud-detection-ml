"""
Inférence M5 — Prédiction d'échec de transaction (LightGBM).

Le plus direct des cinq : predict_proba avec les MÊMES features qu'au
training (vérifiées), pas de réentraînement. Le garde-fou anti-fuite
contrôle que les features interdites ne sont pas réintroduites.
"""
from __future__ import annotations

import pandas as pd

from src import config as cfg
from src.inference.base import BaseInference

# Features interdites (fuite : connues seulement après la transaction)
MOTIFS_FUITE = ["incoherence", "delta_solde", "solde_apres", "statut",
                "has_error", "attempt"]


class InferenceM5(BaseInference):
    NOM = "M5_echec"
    DOSSIER_MODELE = "M5_echec"

    def charger_artefacts(self) -> None:
        d = self._dossier_artefacts()
        self.artefacts["params"] = self._charger_params(d)
        self.artefacts["modele"] = self._charger_pkl(d, "*.pkl")
        feats = self.artefacts["params"].get("FEATURE_COLS", [])
        fuites = [f for f in feats if any(m in f for m in MOTIFS_FUITE)]
        if fuites:
            raise RuntimeError(
                f"Garde-fou anti-fuite : features interdites dans le modèle : {fuites}")
        self.logger.info(f"M5 chargé : LightGBM, {len(feats)} features (fuite contrôlée)")

    def _scorer_impl(self, df: pd.DataFrame) -> dict:
        params = self.artefacts["params"]
        feats = params["FEATURE_COLS"]
        seuil = self.config.get("seuil_alerte_proba", 0.80)

        manquantes = [c for c in feats if c not in df.columns]
        if manquantes:
            raise ValueError(f"Features manquantes : {manquantes[:5]}...")

        X = df[feats].copy()
        for c in feats:
            if not pd.api.types.is_numeric_dtype(X[c]):
                X[c] = pd.to_numeric(X[c], errors="coerce")
        X = X.astype("float32").fillna(X.median(numeric_only=True))

        proba = self.artefacts["modele"].predict_proba(X)[:, 1]
        out = df[[c for c in [cfg.COL_TRANSFER_ID, cfg.COL_DATE, cfg.COL_SENDER_ID,
                              cfg.COL_MONTANT, cfg.COL_SERVICE] if c in df.columns]].copy()
        out["proba_echec"] = proba
        out["ALERTE"] = (out["proba_echec"] >= seuil).astype(int)

        alertes = out[out["ALERTE"] == 1].sort_values("proba_echec", ascending=False)
        return {
            "alertes": alertes,
            "scores": out,
            "stats": {
                "n_alertes": int(out["ALERTE"].sum()),
                "pct_alertes": round(float(out["ALERTE"].mean() * 100), 3),
                "proba_moyenne": round(float(proba.mean()), 4),
                "seuil": seuil,
            },
        }
