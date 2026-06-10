"""
Inférence M1 — Détection de fraude par groupe de pairs.

Reprend EXACTEMENT la logique d'entraînement (M1 v2) :
  1. features blocs A-D (déjà calculées en amont par le pipeline)
  2. segmentation par bandes de volume (seuils FIXES identiques au training)
  3. Isolation Forest par segment : scaler.transform() + score_samples()
  4. ensemble : score IF (percentile intra-segment) + écart au profil pair
  5. budget d'alertes top N/jour + raison par alerte

Le budget top-N rend le seuil auto-adaptatif au volume du nouveau lot.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src import config as cfg
from src.inference.base import BaseInference


def _segmenter(v: float, seuils: dict) -> str:
    if v <= seuils.get("faible", 10):
        return "faible"
    if v <= seuils.get("moyen", 100):
        return "moyen"
    if v <= seuils.get("eleve", 1000):
        return "eleve"
    return "technique"


class InferenceM1(BaseInference):
    NOM = "M1_fraude"
    DOSSIER_MODELE = "M1_fraude"

    def charger_artefacts(self) -> None:
        d = self._dossier_artefacts()
        self.artefacts["params"] = self._charger_params(d)
        segments = self.artefacts["params"].get(
            "segments", ["faible", "moyen", "eleve", "technique"])
        self.artefacts["modeles"] = {}
        self.artefacts["scalers"] = {}
        for seg in segments:
            try:
                self.artefacts["modeles"][seg] = self._charger_pkl(d, f"iforest_{seg}.pkl")
                self.artefacts["scalers"][seg] = self._charger_pkl(d, f"scaler_{seg}.pkl")
            except Exception:                        # segment absent au training
                self.logger.warning(f"Segment {seg} : artefacts absents (ignoré)")
        if not self.artefacts["modeles"]:
            raise RuntimeError("Aucun modèle de segment chargé pour M1.")
        self.logger.info(
            f"M1 chargé : {len(self.artefacts['modeles'])} segments, "
            f"{len(self.artefacts['params'].get('FEATURE_COLS', []))} features")

    def _scorer_impl(self, df: pd.DataFrame) -> dict:
        params = self.artefacts["params"]
        feature_cols = params["FEATURE_COLS"]
        budget_jour = self.config.get("budget_alertes_jour",
                                      params.get("budget_jour", 200))
        seuils_seg = self.config.get("seuils_segments",
                                     {"faible": 10, "moyen": 100, "eleve": 1000})

        manquantes = [c for c in feature_cols if c not in df.columns]
        if manquantes:
            raise ValueError(
                f"Features manquantes (le feature engineering doit tourner avant) : "
                f"{manquantes[:5]}{'...' if len(manquantes) > 5 else ''}")

        df = df.copy()

        # 1. Segmentation (seuils fixes = mêmes pairs qu'au training)
        vol = df.groupby(cfg.COL_SENDER_ID, observed=True).size().rename("vol_compte")
        df = df.merge(vol, left_on=cfg.COL_SENDER_ID, right_index=True, how="left")
        df["SEGMENT"] = df["vol_compte"].fillna(1).apply(lambda v: _segmenter(v, seuils_seg))

        # 2. Features numériques + imputation (médiane du LOT : imputation neutre)
        for c in feature_cols:
            if not pd.api.types.is_numeric_dtype(df[c]):
                df[c] = pd.to_numeric(df[c], errors="coerce")
        X_df = df[feature_cols].astype("float32")
        X_df = X_df.fillna(X_df.median(numeric_only=True))

        # 3. Score IF par segment — transform() puis score_samples() (PAS de fit)
        df["iso_score"] = 0.0
        for seg, modele in self.artefacts["modeles"].items():
            mask = (df["SEGMENT"] == seg).values
            if mask.sum() == 0:
                continue
            Xs = self.artefacts["scalers"][seg].transform(X_df[mask]).astype(np.float32)
            df.loc[mask, "iso_score"] = modele.score_samples(Xs)

        # 4. Ensemble : percentile intra-segment + écart montant aux pairs
        df["montant_z_segment"] = df.groupby("SEGMENT", observed=True)[cfg.COL_MONTANT] \
            .transform(lambda x: (x - x.median()) / (x.std() + 1e-9))
        df["ecart_pairs"] = df["montant_z_segment"].abs().clip(0, 10)
        df["iso_risk"] = df.groupby("SEGMENT", observed=True)["iso_score"] \
            .transform(lambda s: (-s).rank(pct=True) * 100)
        df["ecart_risk"] = df.groupby("SEGMENT", observed=True)["ecart_pairs"] \
            .transform(lambda s: s.rank(pct=True) * 100)
        poids = params.get("poids_ensemble", {"iso": 0.7, "ecart_pairs": 0.3})
        df["RISK_SCORE"] = (poids["iso"] * df["iso_risk"]
                            + poids["ecart_pairs"] * df["ecart_risk"]).clip(0, 100)

        # 5. Budget d'alertes top N/jour
        df["_jour"] = pd.to_datetime(df[cfg.COL_DATE]).dt.date
        df["rang_jour"] = df.groupby("_jour")["RISK_SCORE"] \
            .rank(method="first", ascending=False)
        df["ALERTE"] = (df["rang_jour"] <= budget_jour).astype(int)

        # 6. Explicabilité
        alertes = df[df["ALERTE"] == 1].copy()
        q99_velocite = (df["f_velocite_7j"].quantile(0.99)
                        if "f_velocite_7j" in df.columns else np.inf)

        def raison(row):
            r = []
            if row["montant_z_segment"] > 3:
                r.append("montant très élevé vs pairs")
            if row.get("f_velocite_7j", 0) > q99_velocite:
                r.append("vélocité anormale")
            if row.get("f_taux_echec_hist", 0) > 0.5:
                r.append("historique d'échec élevé")
            if row.get("f_montant_tres_arrondi", 0) == 1:
                r.append("montant très arrondi")
            if row.get("f_est_nuit", 0) == 1:
                r.append("transaction nocturne")
            return " + ".join(r) if r else "profil globalement atypique"

        alertes["RAISON"] = alertes.apply(raison, axis=1)

        cols_alerte = [c for c in [cfg.COL_TRANSFER_ID, cfg.COL_DATE, cfg.COL_SENDER_ID,
                                   cfg.COL_MONTANT, cfg.COL_SERVICE, "SEGMENT",
                                   "RISK_SCORE", "RAISON"] if c in alertes.columns]
        cols_scores = [c for c in [cfg.COL_TRANSFER_ID, "SEGMENT", "RISK_SCORE",
                                   "ALERTE"] if c in df.columns]
        return {
            "alertes": alertes.sort_values("RISK_SCORE", ascending=False)[cols_alerte],
            "scores": df[cols_scores],
            "stats": {
                "n_alertes": int(df["ALERTE"].sum()),
                "pct_alertes": round(df["ALERTE"].mean() * 100, 4),
                "budget_jour": budget_jour,
                "segments": df["SEGMENT"].value_counts().to_dict(),
                "score_moyen_alertes": round(float(alertes["RISK_SCORE"].mean()), 1)
                if len(alertes) else None,
            },
        }
