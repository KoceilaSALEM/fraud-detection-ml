"""
Registre de modèles versionné — traçabilité des artefacts en production.

Principe : pas de serveur MLflow à maintenir, un registre par FICHIERS :

models/
├── M1_fraude/
│   ├── registry.json            <- historique des versions + métadonnées
│   ├── latest -> 2025-09-30_v1  <- lien symbolique (ou champ 'latest' du json)
│   └── 2025-09-30_v1/
│       ├── iforest_faible.pkl, scaler_faible.pkl, ...
│       └── params.json
└── ...

Chaque version porte : date, métriques d'entraînement, features utilisées,
hash de config. On sait TOUJOURS quel modèle a produit quelle alerte.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from src.exceptions import ModeleAbsentError
from src.logging_conf import get_logger

logger = get_logger("registry")


class ModelRegistry:
    """Registre fichier des modèles : publier, lister, charger une version."""

    def __init__(self, racine_modeles: Path):
        self.racine = Path(racine_modeles)

    # ── PUBLICATION (après entraînement) ──────────────────────────────
    def publier(self, modele: str, dossier_artefacts: Path,
                metriques: dict | None = None, tag: str | None = None) -> str:
        """
        Enregistre une nouvelle version d'un modèle dans le registre.

        Args:
            modele: ex 'M1_fraude'
            dossier_artefacts: dossier contenant les .pkl / params.json produits
            metriques: métriques d'entraînement à tracer (auc, n_alertes, ...)
            tag: nom de version ; défaut = date du jour + incrément

        Returns:
            Le tag de la version publiée.
        """
        rep_modele = self.racine / modele
        rep_modele.mkdir(parents=True, exist_ok=True)

        if tag is None:
            base = datetime.now().strftime("%Y-%m-%d")
            existants = [d.name for d in rep_modele.iterdir() if d.is_dir()]
            i = 1
            while f"{base}_v{i}" in existants:
                i += 1
            tag = f"{base}_v{i}"

        cible = rep_modele / tag
        if cible.exists():
            shutil.rmtree(cible)
        shutil.copytree(dossier_artefacts, cible)

        registry = self._lire_registry(modele)
        registry["versions"].append({
            "tag": tag,
            "date_publication": datetime.now().isoformat(timespec="seconds"),
            "metriques": metriques or {},
            "fichiers": sorted(p.name for p in cible.iterdir()),
        })
        registry["latest"] = tag
        self._ecrire_registry(modele, registry)
        logger.info(f"Modèle {modele} publié : version {tag}")
        return tag

    # ── CHARGEMENT (à l'inférence) ────────────────────────────────────
    def chemin_version(self, modele: str, version: str = "latest") -> Path:
        """Retourne le dossier d'une version (résout 'latest'). Lève si absent."""
        registry = self._lire_registry(modele)
        if version == "latest":
            version = registry.get("latest")
            if not version:
                raise ModeleAbsentError(
                    f"Aucune version publiée pour {modele}. "
                    f"Lancer l'entraînement puis registry.publier()."
                )
        chemin = self.racine / modele / version
        if not chemin.exists():
            raise ModeleAbsentError(f"Version {version} de {modele} introuvable ({chemin}).")
        return chemin

    def infos(self, modele: str) -> dict:
        """Métadonnées complètes d'un modèle (toutes versions)."""
        return self._lire_registry(modele)

    def lister_modeles(self) -> list[str]:
        if not self.racine.exists():
            return []
        return sorted(d.name for d in self.racine.iterdir()
                      if d.is_dir() and (d / "registry.json").exists())

    # ── interne ───────────────────────────────────────────────────────
    def _lire_registry(self, modele: str) -> dict:
        f = self.racine / modele / "registry.json"
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
        return {"modele": modele, "latest": None, "versions": []}

    def _ecrire_registry(self, modele: str, registry: dict) -> None:
        f = self.racine / modele / "registry.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(registry, indent=2, ensure_ascii=False, default=str),
                     encoding="utf-8")
