"""
API REST du système ML Orange Money RA&FM.

Rôle : exposer les RÉSULTATS des runs batch (alertes, scores, drift,
historique) à l'outil de fraude de l'entreprise, et permettre de
déclencher un run. L'API ne recalcule rien : elle sert ce que le
pipeline batch a produit — séparation propre batch/consultation.

Lancement :
    uvicorn api.main:app --host 0.0.0.0 --port 8000
Docs interactives : http://<host>:8000/docs
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config as cfg                                  # noqa: E402
from src.logging_conf import get_logger                        # noqa: E402
from src.monitoring.metrics import charger_historique          # noqa: E402
from src.registry import ModelRegistry                         # noqa: E402

logger = get_logger("api")

app = FastAPI(
    title="Orange Money RA&FM — API ML",
    description="Alertes et scores des 5 modèles (fraude, mules, "
                "commissions, échec, réconciliation)",
    version=cfg.CFG.get("projet", {}).get("version", "1.0.0"),
)

HISTORIQUE = ROOT / "outputs" / "historique_runs.jsonl"
RUNS_DIR = ROOT / cfg.CFG.get("inference", {}).get("repertoire_sortie", "outputs/runs")
MODELES_VALIDES = ["M1_fraude", "M2_mules", "M4_commissions",
                   "M5_echec", "M6_reconciliation"]


# ──────────────────────────── santé & méta ───────────────────────────
@app.get("/health", tags=["système"])
def health():
    """Statut du système : modèles publiés, dernier run."""
    registre = ModelRegistry(ROOT / "models")
    modeles = {}
    for m in MODELES_VALIDES:
        infos = registre.infos(m)
        modeles[m] = {"latest": infos.get("latest"),
                      "n_versions": len(infos.get("versions", []))}
    runs = charger_historique(HISTORIQUE)
    dernier = runs[-1] if runs else None
    return {
        "statut": "ok",
        "modeles": modeles,
        "dernier_run": {
            "run_id": dernier["run_id"],
            "fin": dernier.get("fin"),
            "modeles_ok": dernier.get("modeles_ok", []),
            "modeles_ko": dernier.get("modeles_ko", []),
        } if dernier else None,
    }


@app.get("/modeles", tags=["système"])
def modeles():
    """Registre complet : versions et métriques de chaque modèle."""
    registre = ModelRegistry(ROOT / "models")
    return {m: registre.infos(m) for m in MODELES_VALIDES}


# ──────────────────────────── runs ────────────────────────────────────
@app.get("/runs", tags=["runs"])
def liste_runs(n: int = Query(20, le=200)):
    """Historique des N derniers runs (du plus récent au plus ancien)."""
    runs = charger_historique(HISTORIQUE)
    return list(reversed(runs[-n:]))


@app.get("/runs/{run_id}", tags=["runs"])
def detail_run(run_id: str):
    """Rapport complet d'un run (validation, drift, stats par modèle)."""
    f = RUNS_DIR / run_id / "rapport_run.json"
    if not f.exists():
        raise HTTPException(404, f"Run {run_id} introuvable")
    return json.loads(f.read_text(encoding="utf-8"))


@app.get("/runs/{run_id}/alertes/{modele}", tags=["alertes"])
def alertes_run(run_id: str, modele: str,
                limit: int = Query(100, le=5000), offset: int = 0):
    """Alertes d'un modèle pour un run donné (paginé)."""
    if modele not in MODELES_VALIDES:
        raise HTTPException(400, f"Modèle inconnu. Valides : {MODELES_VALIDES}")
    f = RUNS_DIR / run_id / f"{modele}_alertes.csv"
    if not f.exists():
        raise HTTPException(404, f"Pas d'alertes {modele} pour le run {run_id}")
    df = pd.read_csv(f)
    total = len(df)
    page = df.iloc[offset:offset + limit]
    return {
        "run_id": run_id, "modele": modele, "total": total,
        "offset": offset, "limit": limit,
        "alertes": json.loads(page.to_json(orient="records")),
    }


@app.get("/runs/{run_id}/drift", tags=["monitoring"])
def drift_run(run_id: str):
    """Rapport de dérive des données pour un run."""
    f = RUNS_DIR / run_id / "rapport_run.json"
    if not f.exists():
        raise HTTPException(404, f"Run {run_id} introuvable")
    rapport = json.loads(f.read_text(encoding="utf-8"))
    drift = rapport.get("drift")
    if drift is None:
        raise HTTPException(404, "Pas de rapport de drift pour ce run "
                                 "(références absentes au moment du run)")
    return drift


# ──────────────────────────── déclenchement ───────────────────────────
@app.post("/inference", tags=["runs"], status_code=202)
def lancer_inference(chemin_donnees: str, background: BackgroundTasks,
                     modeles: list[str] | None = None):
    """
    Déclenche un run d'inférence en arrière-plan sur un fichier
    (csv ou parquet accessible depuis le serveur). Réponse immédiate ;
    suivre l'avancement via /runs.
    """
    chemin = Path(chemin_donnees)
    if not chemin.exists():
        raise HTTPException(400, f"Fichier introuvable : {chemin}")

    def _tache():
        from src.inference.pipeline import PipelineInference
        df = (pd.read_parquet(chemin) if chemin.suffix == ".parquet"
              else pd.read_csv(chemin, sep=cfg.CSV_SEP, encoding=cfg.CSV_ENCODING,
                               low_memory=False))
        PipelineInference(ROOT).executer(df, modeles=modeles)

    background.add_task(_tache)
    logger.info(f"Run d'inférence déclenché via API : {chemin}")
    return {"statut": "accepté", "donnees": str(chemin),
            "suivi": "/runs (le run apparaîtra une fois terminé)"}
