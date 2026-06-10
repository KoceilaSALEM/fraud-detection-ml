#!/usr/bin/env python3
"""
Run d'inférence batch — LE point d'entrée production.

Usage :
    python scripts/run_inference.py --donnees data/processed/nouveau_mois.parquet
    python scripts/run_inference.py --donnees export.csv --modeles m1_fraude m5_echec
    python scripts/run_inference.py --donnees export.csv --version 2025-09-30_v1
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd

from src import config as cfg
from src.inference.pipeline import PipelineInference
from src.logging_conf import get_logger

logger = get_logger("cli.run_inference")


def charger_donnees(chemin: Path) -> pd.DataFrame:
    if chemin.suffix == ".parquet":
        return pd.read_parquet(chemin)
    if chemin.suffix == ".csv":
        return pd.read_csv(chemin, sep=cfg.CSV_SEP, encoding=cfg.CSV_ENCODING,
                           low_memory=False)
    raise ValueError(f"Format non géré : {chemin.suffix} (csv ou parquet)")


def main():
    p = argparse.ArgumentParser(description="Run d'inférence Orange Money RA&FM")
    p.add_argument("--donnees", required=True, help="Fichier parquet ou csv")
    p.add_argument("--modeles", nargs="*", default=None,
                   help="Sous-ensemble (défaut : tous les actifs)")
    p.add_argument("--version", default="latest", help="Version des modèles")
    args = p.parse_args()

    chemin = Path(args.donnees)
    if not chemin.exists():
        logger.error(f"Fichier introuvable : {chemin}")
        sys.exit(1)

    logger.info(f"Chargement : {chemin}")
    df = charger_donnees(chemin)

    pipeline = PipelineInference(ROOT)
    rapport = pipeline.executer(df, modeles=args.modeles, version=args.version)

    print("\n" + "=" * 60)
    print(f"RUN {rapport['run_id']} — {rapport['duree_totale_s']}s")
    print(f"Modèles OK : {rapport.get('modeles_ok', [])}")
    if rapport.get("modeles_ko"):
        print(f"Modèles KO : {rapport['modeles_ko']}")
    print(f"Exports    : {rapport.get('repertoire_exports')}")
    print("=" * 60)
    sys.exit(0 if not rapport.get("modeles_ko") else 2)


if __name__ == "__main__":
    main()
