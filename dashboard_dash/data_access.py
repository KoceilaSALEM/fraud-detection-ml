"""
Accès aux données de sortie du pipeline d'inférence (dossier outputs/runs).

Portage Dash des fonctions historiquement décorées @st.cache_data(ttl=60)
dans dashboard/app.py. Le cache est géré par Flask-Caching (SimpleCache,
même sémantique de TTL 60 s) au lieu du cache intégré de Streamlit.

Important : `cache.init_app(server)` doit être appelé une fois dans app.py
avant que le serveur ne traite des requêtes (voir app.py).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
from flask_caching import Cache

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "outputs" / "runs"
HISTORIQUE = ROOT / "outputs" / "historique_runs.jsonl"

cache = Cache(config={"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 60})

MODELES = {
    "M1_fraude": "Fraude transactionnelle",
    "M2_mules": "Réseaux de mules",
    "M4_commissions": "Anomalies commissions",
    "M5_echec": "Prédiction d'échec",
    "M6_reconciliation": "Réconciliation",
}


# ════════════════════════ accès aux données ════════════════════════
@cache.memoize(timeout=60)
def lister_runs() -> list[str]:
    if not RUNS_DIR.exists():
        return []
    return sorted((d.name for d in RUNS_DIR.iterdir()
                   if (d / "rapport_run.json").exists()), reverse=True)


@cache.memoize(timeout=60)
def charger_rapport(run_id: str) -> dict:
    return json.loads((RUNS_DIR / run_id / "rapport_run.json")
                       .read_text(encoding="utf-8"))


@cache.memoize(timeout=60)
def charger_alertes(run_id: str, modele: str):
    f = RUNS_DIR / run_id / f"{modele}_alertes.csv"
    return pd.read_csv(f) if f.exists() else None


@cache.memoize(timeout=60)
def charger_scores(run_id: str, modele: str):
    for ext, lecteur in ((".parquet", pd.read_parquet), (".csv", pd.read_csv)):
        f = RUNS_DIR / run_id / f"{modele}_scores{ext}"
        if f.exists():
            try:
                return lecteur(f)
            except Exception:
                return None
    return None


@cache.memoize(timeout=60)
def charger_historique_runs() -> list[dict]:
    if not HISTORIQUE.exists():
        return []
    return [json.loads(l) for l in HISTORIQUE.read_text(encoding="utf-8")
            .splitlines() if l.strip()]


def stats_modele(rapport: dict, cle: str) -> dict:
    return rapport.get("modeles", {}).get(cle, {})


def libelle_run(run_id: str) -> str:
    """Libellé lisible : 'run_id · période · fichier source'."""
    try:
        r = charger_rapport(run_id)
        per = r.get("periode") or {}
        morceaux = [run_id]
        if per.get("debut"):
            morceaux.append(f"{per['debut']} → {per['fin']}")
        if r.get("source"):
            morceaux.append(r["source"])
        return "  ·  ".join(morceaux)
    except Exception:
        return run_id


def runs_en_cours() -> list[dict]:
    """Runs avec progression < 100 et sans rapport final."""
    actifs = []
    if not RUNS_DIR.exists():
        return actifs
    for d in RUNS_DIR.iterdir():
        prog = d / "progression.json"
        if prog.exists() and not (d / "rapport_run.json").exists():
            try:
                pj = json.loads(prog.read_text(encoding="utf-8"))
                pj["run_id"] = d.name
                actifs.append(pj)
            except Exception:
                pass
    return sorted(actifs, key=lambda x: x["run_id"], reverse=True)


def lancer_inference(fichier: Path, modeles: list[str] | None = None) -> None:
    """Lance le run en arrière-plan (le dashboard reste réactif)."""
    cmd = [sys.executable, str(ROOT / "scripts" / "run_inference.py"),
           "--donnees", str(fichier)]
    if modeles:
        cmd += ["--modeles"] + modeles
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = 0x00000208          # DETACHED | NEW_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(cmd, cwd=str(ROOT),
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                      **kwargs)


def fmt(n) -> str:
    """Format milliers avec espaces (convention FR)."""
    try:
        return f"{int(n):,}".replace(",", " ")
    except (TypeError, ValueError):
        return str(n)


def invalider_cache() -> None:
    """Équivalent de st.cache_data.clear() — à appeler après upload / fin de run."""
    cache.clear()
