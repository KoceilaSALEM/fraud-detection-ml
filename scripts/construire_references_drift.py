#!/usr/bin/env python3
"""
Construit les références de drift depuis les données d'ENTRAÎNEMENT.
À lancer UNE FOIS après l'entraînement (puis après chaque réentraînement).

Usage : python scripts/construire_references_drift.py [--donnees data/processed/OM_clean.parquet]
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd

from src import config as cfg
from src.monitoring.drift import construire_reference
from src.logging_conf import get_logger

logger = get_logger("cli.drift_refs")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--donnees", default=str(cfg.PARQUET_PATH))
    args = p.parse_args()

    variables = cfg.CFG.get("drift", {}).get(
        "features_surveillees", [cfg.COL_MONTANT])
    logger.info(f"Lecture {args.donnees} (colonnes : {variables})")
    df = pd.read_parquet(args.donnees, columns=variables)

    references = {}
    for var in variables:
        references[var] = construire_reference(df[var])
        logger.info(f"Référence {var} : {references[var]['n_reference']:,} obs")
    references["_volume"] = int(len(df))

    sortie = ROOT / "models" / "drift_references.json"
    sortie.write_text(json.dumps(references, indent=2), encoding="utf-8")
    logger.info(f"✅ Références écrites : {sortie}")


if __name__ == "__main__":
    main()
