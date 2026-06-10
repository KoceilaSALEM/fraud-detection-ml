"""
Contrat commun d'inférence — tous les modèles suivent le même cycle de vie.

    charger_artefacts() -> scorer(df) -> exporter(resultats)

Garanties production :
  - les artefacts viennent du registre versionné (ou fallback dossier plat)
  - AUCUN fit() à l'inférence : transform() uniquement (norme figée)
  - chaque erreur est une InferenceError avec le nom du modèle en cause
  - chaque run trace : durée, volumes, alertes produites
"""
from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from pathlib import Path

import joblib
import pandas as pd

from src.exceptions import InferenceError, ModeleAbsentError
from src.logging_conf import get_logger
from src.registry import ModelRegistry


class BaseInference(ABC):
    """Classe mère des 5 moteurs d'inférence (M1, M2, M4, M5, M6)."""

    NOM: str = "M?"                 # ex "M1_fraude"
    DOSSIER_MODELE: str = ""        # ex "M1_fraude" (sous models/)

    def __init__(self, racine_modeles: Path, version: str = "latest",
                 config: dict | None = None):
        self.racine_modeles = Path(racine_modeles)
        self.version = version
        self.config = config or {}
        self.logger = get_logger(f"inference.{self.NOM}")
        self.artefacts: dict = {}
        self._charge = False

    # ── localisation des artefacts ──────────────────────────────────
    def _dossier_artefacts(self) -> Path:
        """
        Registre versionné si disponible, sinon fallback sur le dossier plat
        (compatible avec les modèles déjà entraînés par les notebooks).
        """
        registre = ModelRegistry(self.racine_modeles)
        dossier_plat = self.racine_modeles / self.DOSSIER_MODELE
        try:
            return registre.chemin_version(self.DOSSIER_MODELE, self.version)
        except ModeleAbsentError:
            if dossier_plat.exists() and (any(dossier_plat.glob("*.pkl"))
                                          or any(dossier_plat.glob("params*.json"))):
                self.logger.warning(
                    f"Pas de version publiée au registre pour {self.DOSSIER_MODELE} "
                    f"-> fallback sur le dossier plat {dossier_plat}. "
                    f"Conseil : publier via scripts/publier_modeles.py"
                )
                return dossier_plat
            raise

    def _charger_pkl(self, dossier: Path, motif: str):
        """Charge un .pkl par motif glob. Erreur claire si absent."""
        candidats = sorted(dossier.glob(motif))
        if not candidats:
            raise ModeleAbsentError(
                f"[{self.NOM}] Aucun fichier '{motif}' dans {dossier}. "
                f"Le modèle a-t-il été entraîné et sauvegardé ?")
        return joblib.load(candidats[0])

    def _charger_params(self, dossier: Path) -> dict:
        """Charge le params*.json le plus récent du dossier."""
        candidats = sorted(dossier.glob("params*.json"), reverse=True)
        if not candidats:
            raise ModeleAbsentError(
                f"[{self.NOM}] Aucun params*.json dans {dossier}.")
        return json.loads(candidats[0].read_text(encoding="utf-8"))

    # ── cycle de vie ─────────────────────────────────────────────────
    @abstractmethod
    def charger_artefacts(self) -> None:
        """Charge modèles/scalers/params depuis le registre. Remplit self.artefacts."""

    @abstractmethod
    def _scorer_impl(self, df: pd.DataFrame) -> dict:
        """Logique de scoring propre au modèle. Retourne le dict de résultats."""

    def scorer(self, df: pd.DataFrame) -> dict:
        """
        Point d'entrée unique : charge si besoin, score, trace, encapsule les erreurs.

        Returns:
            dict avec au minimum : {'alertes': DataFrame, 'stats': dict}
        """
        t0 = time.time()
        try:
            if not self._charge:
                self.charger_artefacts()
                self._charge = True
            resultats = self._scorer_impl(df)
            resultats.setdefault("stats", {})
            resultats["stats"]["duree_s"] = round(time.time() - t0, 1)
            resultats["stats"]["n_entree"] = len(df)
            self.logger.info(
                f"Scoring terminé : {resultats['stats'].get('n_alertes', '?')} alertes "
                f"en {resultats['stats']['duree_s']}s")
            return resultats
        except ModeleAbsentError:
            raise
        except Exception as e:                       # noqa: BLE001
            raise InferenceError(self.NOM, f"{type(e).__name__}: {e}") from e

    def exporter(self, resultats: dict, rep_sortie: Path) -> list[Path]:
        """Exporte les alertes (csv) + scores (parquet si présents)."""
        rep_sortie.mkdir(parents=True, exist_ok=True)
        fichiers = []
        alertes = resultats.get("alertes")
        if alertes is not None and len(alertes) > 0:
            f_alertes = rep_sortie / f"{self.NOM}_alertes.csv"
            alertes.to_csv(f_alertes, index=False, encoding="utf-8-sig")
            fichiers.append(f_alertes)
        scores = resultats.get("scores")
        if scores is not None and len(scores) > 0:
            try:
                f_scores = rep_sortie / f"{self.NOM}_scores.parquet"
                scores.to_parquet(f_scores, index=False)
            except ImportError:                      # pyarrow absent -> CSV
                f_scores = rep_sortie / f"{self.NOM}_scores.csv"
                scores.to_csv(f_scores, index=False, encoding="utf-8-sig")
                self.logger.warning("pyarrow absent : scores exportés en CSV")
            fichiers.append(f_scores)
        stats = resultats.get("stats", {})
        f_stats = rep_sortie / f"{self.NOM}_stats.json"
        f_stats.write_text(json.dumps(stats, indent=2, ensure_ascii=False, default=str),
                           encoding="utf-8")
        fichiers.append(f_stats)
        self.logger.info(f"Exports : {[f.name for f in fichiers]}")
        return fichiers
