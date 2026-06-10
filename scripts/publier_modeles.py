#!/usr/bin/env python3
"""
Publie les modèles déjà entraînés (dossiers plats models/Mx/) au registre
versionné. À lancer UNE FOIS après les entraînements, puis après chaque
réentraînement.

Usage : python scripts/publier_modeles.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.registry import ModelRegistry
from src.logging_conf import get_logger

logger = get_logger("cli.publier")

MODELES = ["M1_fraude", "M2_mules", "M4_commissions", "M5_echec", "M6_reconciliation"]


def main():
    racine = ROOT / "models"
    registre = ModelRegistry(racine)
    for modele in MODELES:
        dossier = racine / modele
        if not dossier.exists() or not any(dossier.glob("*.pkl")) \
                and not any(dossier.glob("params*.json")):
            logger.warning(f"{modele} : pas d'artefacts -> ignoré")
            continue
        deja = registre.infos(modele).get("latest")
        if deja:
            logger.info(f"{modele} : déjà publié (latest={deja}) -> ignoré "
                        f"(supprimer registry.json pour republier)")
            continue
        # copie temporaire sans les sous-dossiers de versions
        import tempfile, shutil
        with tempfile.TemporaryDirectory() as tmp:
            tmp_art = Path(tmp) / "artefacts"
            tmp_art.mkdir()
            for f in dossier.iterdir():
                if f.is_file():
                    shutil.copy2(f, tmp_art / f.name)
            tag = registre.publier(modele, tmp_art)
            logger.info(f"{modele} publié -> {tag}")


if __name__ == "__main__":
    main()
