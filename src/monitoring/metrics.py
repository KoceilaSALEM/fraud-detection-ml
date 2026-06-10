"""
Métriques de run — le journal de bord de chaque exécution.

Chaque run d'inférence enregistre : volumes traités, alertes produites,
durées, distribution des scores. Historisé en JSONL (1 ligne = 1 run)
-> lisible, diffable, et le dashboard le consomme directement.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from src.logging_conf import get_logger

logger = get_logger("monitoring.metrics")


class RunMetrics:
    """Collecte et persiste les métriques d'un run d'inférence."""

    def __init__(self, run_id: str | None = None):
        self.run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.debut = datetime.now()
        self.donnees: dict = {"run_id": self.run_id,
                              "debut": self.debut.isoformat(timespec="seconds"),
                              "modeles": {}}

    def enregistrer_modele(self, modele: str, **kwargs) -> None:
        """Métriques d'un modèle : n_alertes, duree_s, score_moyen, etc."""
        self.donnees["modeles"][modele] = kwargs
        logger.info(f"[{modele}] " + " | ".join(f"{k}={v}" for k, v in kwargs.items()))

    def enregistrer_global(self, **kwargs) -> None:
        self.donnees.update(kwargs)

    def finaliser(self, chemin_historique: Path) -> dict:
        """Clôt le run et l'ajoute à l'historique JSONL."""
        self.donnees["fin"] = datetime.now().isoformat(timespec="seconds")
        self.donnees["duree_totale_s"] = round(
            (datetime.now() - self.debut).total_seconds(), 1)
        chemin_historique.parent.mkdir(parents=True, exist_ok=True)
        with open(chemin_historique, "a", encoding="utf-8") as f:
            f.write(json.dumps(self.donnees, ensure_ascii=False, default=str) + "\n")
        logger.info(f"Run {self.run_id} finalisé ({self.donnees['duree_totale_s']}s)")
        return self.donnees


def charger_historique(chemin: Path) -> list[dict]:
    """Lit l'historique des runs (pour le dashboard et l'API)."""
    if not chemin.exists():
        return []
    runs = []
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        if ligne.strip():
            runs.append(json.loads(ligne))
    return runs
