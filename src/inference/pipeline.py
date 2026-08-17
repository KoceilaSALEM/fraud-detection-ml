"""
Pipeline d'orchestration — exécute le run d'inférence complet.

    données -> validation -> features (1 fois) -> M1, M2, M4, M5, M6
            -> drift -> métriques -> exports horodatés

Garanties production :
  - ISOLATION : un modèle qui plante n'empêche pas les autres de tourner
  - chaque run a un ID horodaté, ses exports, son rapport JSON
  - le drift est évalué AVANT le scoring (avertit si données dérivées)
  - les features (blocs A-D) sont calculées UNE seule fois pour M1+M5
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from src import config as cfg
from src.exceptions import ModeleAbsentError, InferenceError
from src.inference.m1_fraude import InferenceM1
from src.inference.m2_mules import InferenceM2
from src.inference.m4_commissions import InferenceM4
from src.inference.m5_echec import InferenceM5
from src.inference.m6_reconciliation import InferenceM6
from src.logging_conf import get_logger
from src.monitoring.drift import rapport_drift
from src.monitoring.metrics import RunMetrics
from src.validation import valider_entree

logger = get_logger("pipeline")

MOTEURS = {
    "m1_fraude": InferenceM1,
    "m2_mules": InferenceM2,
    "m4_commissions": InferenceM4,
    "m5_echec": InferenceM5,
    "m6_reconciliation": InferenceM6,
}

# Modèles qui ont besoin des features blocs A-D
BESOIN_FEATURES = {"m1_fraude", "m5_echec"}


class PipelineInference:
    """Orchestrateur du run d'inférence complet."""

    def __init__(self, racine_projet: Path | None = None):
        self.racine = Path(racine_projet) if racine_projet else cfg.ROOT_DIR
        self.config = cfg.CFG or {}
        self.racine_modeles = self.racine / "models"

    # ─────────────────────────────────────────────────────────────────
    def executer(self, df: pd.DataFrame, modeles: list[str] | None = None,
                 version: str = "latest", source: str = "") -> dict:
        """
        Exécute le run complet sur un DataFrame de transactions.

        Args:
            df: nouvelles transactions (format export DWH)
            modeles: sous-ensemble à exécuter (défaut : tous les actifs du YAML)
            version: version des modèles au registre (défaut latest)

        Returns:
            Rapport de run complet (dict, aussi écrit en JSON).
        """
        run = RunMetrics()
        rep_run = (self.racine
                   / self.config.get("inference", {}).get("repertoire_sortie", "outputs/runs")
                   / run.run_id)
        rep_run.mkdir(parents=True, exist_ok=True)
        logger.info(f"═══ RUN {run.run_id} ═══ {len(df):,} transactions")

        # Métadonnées de période (pour la navigation par fichier dans le dashboard)
        try:
            dates = pd.to_datetime(df[cfg.COL_DATE], errors="coerce")
            periode = {"debut": str(dates.min().date()), "fin": str(dates.max().date())}
        except Exception:                            # noqa: BLE001
            periode = {}
        run.enregistrer_global(source=source, periode=periode,
                               n_transactions=int(len(df)))

        # Progression temps réel (consommée par le dashboard)
        self._rep_run = rep_run
        self._progression("validation", 2)

        # 1. VALIDATION (bloquant si fichier invalide)
        rapport_validation = valider_entree(df)
        run.enregistrer_global(validation=rapport_validation)

        self._progression("drift", 5)
        # 2. DRIFT (avertit, ne bloque pas — décision opérateur)
        drift = self._verifier_drift(df)
        run.enregistrer_global(drift=drift)
        if drift and drift.get("verdict_global") == "ALERTE":
            logger.warning(
                "⚠️ DRIFT EN ALERTE : les données ont significativement dérivé "
                "de la référence d'entraînement. Les scores restent calculés "
                "mais un réentraînement est recommandé.")

        # 3. FEATURES (une seule fois, pour M1 + M5)
        modeles_actifs = self._modeles_actifs(modeles)
        self._progression("features", 8)
        df_feat = None
        if BESOIN_FEATURES & set(modeles_actifs):
            df_feat = self._calculer_features(df)

        # 4. SCORING — isolation des erreurs par modèle
        # poids de progression par étape (features = le plus lourd)
        pct = 50 if df_feat is not None else 10
        pas = (96 - pct) / max(len(modeles_actifs), 1)
        resultats, erreurs = {}, {}
        for nom in modeles_actifs:
            self._progression(nom, int(pct))
            pct += pas
            try:
                moteur = MOTEURS[nom](
                    self.racine_modeles, version=version,
                    config=self.config.get("modeles", {}).get(nom, {}))
                donnees = df_feat if nom in BESOIN_FEATURES else df
                res = moteur.scorer(donnees)
                try:
                    moteur.exporter(res, rep_run)
                except Exception as e_exp:           # noqa: BLE001
                    logger.error(f"Export {nom} en échec (scoring OK) : {e_exp}")
                resultats[nom] = res["stats"]
                run.enregistrer_modele(nom, **res["stats"])
            except (ModeleAbsentError, InferenceError) as e:
                logger.error(f"❌ {nom} : {e}")
                erreurs[nom] = str(e)
            except Exception as e:                   # noqa: BLE001
                logger.error(f"❌ {nom} (inattendu) : {type(e).__name__}: {e}")
                erreurs[nom] = f"{type(e).__name__}: {e}"

        # 5. RAPPORT FINAL
        run.enregistrer_global(
            erreurs=erreurs,
            modeles_ok=sorted(resultats),
            modeles_ko=sorted(erreurs),
            repertoire_exports=str(rep_run))
        self._progression("finalisation", 98)
        rapport = run.finaliser(self.racine / "outputs" / "historique_runs.jsonl")
        (rep_run / "rapport_run.json").write_text(
            json.dumps(rapport, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8")
        self._progression("terminé", 100)
        statut = "✅ COMPLET" if not erreurs else f"⚠️ PARTIEL ({len(erreurs)} échec(s))"
        logger.info(f"═══ RUN {run.run_id} {statut} → {rep_run} ═══")
        return rapport

    def _progression(self, etape: str, pct: int) -> None:
        """Écrit l'avancement du run (consommé par le dashboard)."""
        try:
            f = self._rep_run / "progression.json"
            f.write_text(json.dumps({
                "etape": etape, "pct": pct,
                "maj": datetime.now().isoformat(timespec="seconds")}),
                encoding="utf-8")
        except Exception:                            # noqa: BLE001
            pass                                     # la progression ne doit jamais bloquer

    # ─────────────────────────────────────────────────────────────────
    def _modeles_actifs(self, demandes: list[str] | None) -> list[str]:
        conf = self.config.get("modeles", {})
        actifs = [m for m in MOTEURS
                  if conf.get(m, {}).get("actif", True)]
        if demandes:
            inconnus = set(demandes) - set(MOTEURS)
            if inconnus:
                raise ValueError(f"Modèles inconnus : {inconnus}")
            actifs = [m for m in demandes if m in actifs]
        logger.info(f"Modèles à exécuter : {actifs}")
        return actifs

    def _calculer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Blocs A-D : mêmes transformations qu'à l'entraînement."""
        from src.features import (bloc_a_transaction, bloc_b_temporel,
                                  bloc_c_comportemental, bloc_d_contextuel)
        logger.info("Feature engineering (blocs A-D)...")
        d = df.sort_values([cfg.COL_SENDER_ID, cfg.COL_DATE]).reset_index(drop=True)
        d = bloc_a_transaction.build(d)
        d = bloc_b_temporel.build(d)
        d = bloc_c_comportemental.build(d, verbose=False)
        d = bloc_d_contextuel.build(d)
        logger.info(f"Features OK : {sum(c.startswith('f_') for c in d.columns)} colonnes f_*")
        return d

    def _verifier_drift(self, df: pd.DataFrame) -> dict | None:
        """Compare le lot à la référence figée (si elle existe)."""
        chemin_refs = self.racine_modeles / "drift_references.json"
        if not chemin_refs.exists():
            logger.warning(
                "Pas de références de drift (models/drift_references.json). "
                "Générer via scripts/construire_references_drift.py")
            return None
        references = json.loads(chemin_refs.read_text(encoding="utf-8"))
        seuil_vol = self.config.get("drift", {}).get("variation_volume_max", 0.50)
        return rapport_drift(df, references, variation_volume_max=seuil_vol)
