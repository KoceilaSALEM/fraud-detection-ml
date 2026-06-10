"""
Inférence M4 — Anomalies commissions/frais.

COHÉRENCE GARANTIE : l'agrégation jour×service est factorisée ici
(`agreger_jour_service`) et utilisée À LA FOIS par la construction de la
référence (scripts/construire_reference_m4.py) et par l'inférence.
Référence et scoring mesurent donc exactement la même chose.

Robustesse : plancher sur l'écart-type (5% de la moyenne) pour éviter
les z-scores absurdes (10^10) quand un service a une référence quasi
constante.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src import config as cfg
from src.inference.base import BaseInference

METRIQUES = ["taux_comm_paid", "taux_comm_recv", "comm_par_tx"]


def agreger_jour_service(df: pd.DataFrame, vol_min_pct: float = 0.50) -> pd.DataFrame:
    """
    Agrégation jour×service avec métriques normalisées.
    CODE UNIQUE partagé référence/inférence — ne pas dupliquer ailleurs.
    """
    d = df.copy()
    for c in [cfg.COL_MONTANT, cfg.COL_COMM_PAID, cfg.COL_COMM_RECV]:
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0)
    d = d[d[cfg.COL_STATUT] == "TS"]
    d["_jour"] = pd.to_datetime(d[cfg.COL_DATE]).dt.date

    agg = d.groupby(["_jour", cfg.COL_SERVICE], observed=True).agg(
        volume=(cfg.COL_MONTANT, "count"),
        montant=(cfg.COL_MONTANT, "sum"),
        comm_paid=(cfg.COL_COMM_PAID, "sum"),
        comm_recv=(cfg.COL_COMM_RECV, "sum"),
    ).reset_index()
    agg["taux_comm_paid"] = agg["comm_paid"] / (agg["montant"] + 1)
    agg["taux_comm_recv"] = agg["comm_recv"] / (agg["montant"] + 1)
    agg["comm_par_tx"] = (agg["comm_paid"] + agg["comm_recv"]) / (agg["volume"] + 1)

    # Exclusion jours partiels (volume < x% de la médiane du service)
    med_vol = agg.groupby(cfg.COL_SERVICE, observed=True)["volume"].transform("median")
    return agg[agg["volume"] >= vol_min_pct * med_vol]


def construire_reference_m4(df: pd.DataFrame, vol_min_pct: float = 0.50) -> pd.DataFrame:
    """Stats de référence par service (mean/std des métriques), TOUS services."""
    agg = agreger_jour_service(df, vol_min_pct)
    return agg.groupby(cfg.COL_SERVICE, observed=True).agg(
        **{f"{m}_{s}": (m, s) for m in METRIQUES for s in ["mean", "std"]})


class InferenceM4(BaseInference):
    NOM = "M4_commissions"
    DOSSIER_MODELE = "M4_commissions"

    def charger_artefacts(self) -> None:
        d = self._dossier_artefacts()
        self.artefacts["params"] = self._charger_params(d)
        stats = None
        for motif in ("stats_par_service*.json", "stats_par_service*.pkl",
                      "stats_par_service*.csv"):
            cands = sorted(d.glob(motif))
            if cands:
                f = cands[0]
                if f.suffix == ".json":
                    stats = pd.read_json(f, orient="index")
                elif f.suffix == ".pkl":
                    stats = pd.read_pickle(f)
                else:
                    stats = pd.read_csv(f, index_col=0)
                break
        if stats is None:
            raise RuntimeError(
                "stats_par_service introuvable. Générer la référence via "
                "scripts/construire_reference_m4.py puis republier M4.")
        self.artefacts["stats_ref"] = stats
        self.logger.info(f"M4 chargé : {len(stats)} services de référence")

    def _scorer_impl(self, df: pd.DataFrame) -> dict:
        seuil_z = self.config.get("seuil_z", 3.0)
        vol_min_pct = self.config.get("volume_min_pct_mediane", 0.50)
        ref = self.artefacts["stats_ref"]

        agg = agreger_jour_service(df, vol_min_pct)

        alertes = []
        for _, row in agg.iterrows():
            svc = row[cfg.COL_SERVICE]
            if svc not in ref.index:
                continue
            for metrique in METRIQUES:
                mu = ref.loc[svc].get(f"{metrique}_mean", np.nan)
                sd = ref.loc[svc].get(f"{metrique}_std", np.nan)
                if pd.isna(mu) or pd.isna(sd):
                    continue
                # PLANCHER : évite les z-scores absurdes sur référence
                # quasi constante (sd minimal = 5% de |mu|, et > 0)
                sd = max(float(sd), abs(float(mu)) * 0.05, 1e-9)
                z = (row[metrique] - mu) / sd
                if abs(z) > seuil_z:
                    ratio = f"x{row[metrique] / mu:.1f}" if mu > 0 else "réf. nulle"
                    alertes.append({
                        "jour": row["_jour"], "service": svc, "metrique": metrique,
                        "valeur": round(float(row[metrique]), 6),
                        "reference": round(float(mu), 6),
                        "z_score": round(float(np.clip(z, -100, 100)), 2),
                        "volume": int(row["volume"]),
                        "RAISON": f"{metrique} anormal ({ratio} vs norme, "
                                  f"z={min(abs(z), 100):.1f})",
                    })
        alertes_df = pd.DataFrame(alertes)
        if len(alertes_df):
            alertes_df = alertes_df.sort_values("z_score", key=abs, ascending=False)
        return {
            "alertes": alertes_df,
            "scores": agg,
            "stats": {
                "n_alertes": int(len(alertes_df)),
                "n_jours_services": int(len(agg)),
                "services_inconnus": sorted(
                    set(agg[cfg.COL_SERVICE].astype(str)) - set(ref.index.astype(str))),
            },
        }
