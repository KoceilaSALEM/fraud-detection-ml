"""
Logging structuré du système ML Orange Money RA&FM.

Chaque run d'inférence produit un fichier de log horodaté + sortie console.
Format pensé pour l'auditabilité : qui, quoi, quand, combien.
"""
import logging
import sys
from datetime import datetime
from pathlib import Path


def get_logger(nom: str, repertoire: str = "logs", niveau: str = "INFO") -> logging.Logger:
    """
    Crée un logger à double sortie : console + fichier horodaté.

    Args:
        nom: nom du composant (ex 'inference.m1', 'pipeline', 'api')
        repertoire: dossier des logs (créé si absent)
        niveau: DEBUG | INFO | WARNING | ERROR

    Returns:
        Logger configuré, idempotent (pas de doublons de handlers).
    """
    logger = logging.getLogger(nom)
    if logger.handlers:          # déjà configuré -> réutiliser
        return logger

    logger.setLevel(getattr(logging, niveau.upper(), logging.INFO))
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # Fichier journalier (un fichier par jour, tous composants confondus)
    log_dir = Path(repertoire)
    log_dir.mkdir(parents=True, exist_ok=True)
    fichier = log_dir / f"{datetime.now():%Y-%m-%d}.log"
    fh = logging.FileHandler(fichier, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger
