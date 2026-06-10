#!/usr/bin/env python3
"""
Régénère la référence M4 (stats_par_service.json) depuis les données
d'entraînement, en utilisant LE MÊME code d'agrégation que l'inférence
-> cohérence garantie par construction.

Usage : python scripts/construire_reference_m4.py [--donnees ...]
Puis  : republier M4 (supprimer registry.json + dossier version,
        relancer scripts/publier_modeles.py)
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd

from src import config as cfg
from src.inference.m4_commissions import construire_reference_m4
from src.logging_conf import get_logger

logger = get_logger("cli.ref_m4")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--donnees", default=str(cfg.PARQUET_PATH))
    args = p.parse_args()

    cols = [cfg.COL_DATE, cfg.COL_SERVICE, cfg.COL_STATUT, cfg.COL_MONTANT,
            cfg.COL_COMM_PAID, cfg.COL_COMM_RECV]
    logger.info(f"Lecture {args.donnees}")
    df = pd.read_parquet(args.donnees, columns=cols)

    vol_min = cfg.CFG.get("modeles", {}).get("m4_commissions", {}) \
                     .get("volume_min_pct_mediane", 0.50)
    ref = construire_reference_m4(df, vol_min_pct=vol_min)

    sortie = cfg.MODELS_DIR / "M4_commissions" / "stats_par_service.json"
    ref.to_json(sortie, orient="index")
    logger.info(f"✅ Référence M4 : {len(ref)} services -> {sortie}")
    logger.info(f"Services : {ref.index.tolist()}")
    logger.info("Republier M4 : supprimer models/M4_commissions/registry.json "
                "et le dossier de version, puis python scripts/publier_modeles.py")


if __name__ == "__main__":
    main()
