"""
Inférence M2 — Réseaux de mules.

Particularité : M2 est une analyse PAR LOT (le graphe du nouveau mois).
Les artefacts chargés sont le scaler (norme figée) et les paramètres ;
le PageRank et le DBSCAN se recalculent sur le nouveau graphe — c'est
inhérent à la détection de réseaux, qui est relative au lot analysé.

Pipeline identique au training (M2 v2) :
  arêtes -> features nœuds -> transit -> PageRank sparse -> DBSCAN
  (pré-filtré) -> score combiné -> budget -> explicabilité
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.cluster import DBSCAN

from src import config as cfg
from src.inference.base import BaseInference

FEAT_M2 = ["in_degree", "out_degree", "ratio_transit", "transit_score",
           "diversite", "log_montant_transit", "pagerank"]


def pagerank_sparse(edges: pd.DataFrame, src="source", tgt="target",
                    weight="montant", alpha=0.85, max_iter=100, tol=1e-9) -> dict:
    """PageRank power iteration sur matrice creuse. Robuste (vide, dangling)."""
    if len(edges) == 0:
        return {}
    noeuds = pd.Index(pd.concat([edges[src], edges[tgt]]).unique())
    n = len(noeuds)
    if n == 0:
        return {}
    idx = {node: i for i, node in enumerate(noeuds)}
    si = edges[src].map(idx).values
    ti = edges[tgt].map(idx).values
    w = edges[weight].values.astype(np.float64)
    A = csr_matrix((w, (si, ti)), shape=(n, n))
    out_sum = np.asarray(A.sum(axis=1)).flatten()
    dangling = (out_sum == 0)
    out_sum[out_sum == 0] = 1
    D_inv = csr_matrix((1.0 / out_sum, (range(n), range(n))), shape=(n, n))
    M = (D_inv @ A).T
    r = np.ones(n) / n
    for _ in range(max_iter):
        r_new = alpha * (M @ r) + alpha * (r[dangling].sum()) / n + (1 - alpha) / n
        if np.abs(r_new - r).sum() < tol:
            r = r_new
            break
        r = r_new
    return dict(zip(noeuds, r))


class InferenceM2(BaseInference):
    NOM = "M2_mules"
    DOSSIER_MODELE = "M2_mules"

    def charger_artefacts(self) -> None:
        d = self._dossier_artefacts()
        self.artefacts["params"] = self._charger_params(d)
        self.artefacts["scaler"] = self._charger_pkl(d, "scaler*.pkl")
        self.logger.info("M2 chargé : scaler + params")

    def _scorer_impl(self, df: pd.DataFrame) -> dict:
        params = self.artefacts["params"]
        budget = self.config.get("budget_mules", params.get("budget_mules", 500))
        eps = self.config.get("dbscan_eps", params.get("dbscan_eps", 1.5))
        min_samples = self.config.get("dbscan_min_samples",
                                      params.get("dbscan_min_samples", 5))
        max_points = self.config.get("max_points_dbscan", 50000)
        q_candidats = self.config.get("quantile_candidats", 0.90)
        poids = params.get("poids", {"transit": 0.35, "diversite": 0.25,
                                     "pagerank": 0.20, "cluster": 0.20})

        # 1. Arêtes (transactions réussies, expéditeur != destinataire)
        d = df[[cfg.COL_SENDER_ID, cfg.COL_RECVR_ID, cfg.COL_MONTANT, cfg.COL_STATUT]].copy()
        d[cfg.COL_MONTANT] = pd.to_numeric(d[cfg.COL_MONTANT], errors="coerce").fillna(0)
        d = d[(d[cfg.COL_STATUT] == "TS")
              & d[cfg.COL_SENDER_ID].notna() & d[cfg.COL_RECVR_ID].notna()]
        d = d[d[cfg.COL_SENDER_ID].astype(str) != d[cfg.COL_RECVR_ID].astype(str)]
        edges = d.groupby([cfg.COL_SENDER_ID, cfg.COL_RECVR_ID], observed=True).agg(
            nb_tx=(cfg.COL_MONTANT, "count"),
            montant=(cfg.COL_MONTANT, "sum")).reset_index()
        edges.columns = ["source", "target", "nb_tx", "montant"]

        # 2. Features par nœud
        out_s = edges.groupby("source").agg(
            out_degree=("target", "nunique"), out_montant=("montant", "sum")
        ).reset_index().rename(columns={"source": "node"})
        in_s = edges.groupby("target").agg(
            in_degree=("source", "nunique"), in_montant=("montant", "sum")
        ).reset_index().rename(columns={"target": "node"})
        nodes = pd.merge(in_s, out_s, on="node", how="outer").fillna(0)

        # 3. Transit
        nodes["est_transit"] = ((nodes["in_degree"] > 0) & (nodes["out_degree"] > 0)).astype(int)
        nodes["ratio_transit"] = nodes["out_montant"] / (nodes["in_montant"] + 1)
        nodes["transit_score"] = np.where(
            nodes["est_transit"] == 1,
            1 - np.abs(nodes["ratio_transit"] - 1).clip(0, 1), 0)
        nodes["diversite"] = nodes["in_degree"] + nodes["out_degree"]
        nodes["log_montant_transit"] = np.log1p(
            nodes[["in_montant", "out_montant"]].min(axis=1))
        suspects = nodes[nodes["est_transit"] == 1].copy()

        if len(suspects) == 0:
            return {"alertes": pd.DataFrame(), "scores": pd.DataFrame(),
                    "stats": {"n_alertes": 0, "n_transit": 0, "n_clusters": 0}}

        # 4. PageRank sparse sur le sous-graphe de transit
        ct = set(suspects["node"])
        edges_t = edges[edges["source"].isin(ct) & edges["target"].isin(ct)]
        pr = pagerank_sparse(edges_t)
        suspects["pagerank"] = suspects["node"].map(pr).fillna(0) if pr else 0.0

        # 5. DBSCAN pré-filtré (candidats au transit marqué uniquement)
        seuil = suspects["transit_score"].quantile(q_candidats)
        cand = suspects[(suspects["transit_score"] >= seuil)
                        & (suspects["diversite"] >= 3)].copy()
        if len(cand) > max_points:
            cand = cand.nlargest(max_points, "transit_score")
        suspects["cluster"] = -1
        n_clusters = 0
        if len(cand) >= min_samples:
            Xs = self.artefacts["scaler"].transform(cand[FEAT_M2].fillna(0).values)
            labels = DBSCAN(eps=eps, min_samples=min_samples, n_jobs=-1).fit_predict(Xs)
            suspects.loc[cand.index, "cluster"] = labels
            n_clusters = len(set(labels)) - (1 if -1 in labels else 0)

        # 6. Score combiné + budget
        suspects["r_transit"] = suspects["transit_score"].rank(pct=True) * 100
        suspects["r_diversite"] = suspects["diversite"].rank(pct=True) * 100
        suspects["r_pagerank"] = suspects["pagerank"].rank(pct=True) * 100
        suspects["r_cluster"] = (suspects["cluster"] >= 0).astype(int) * 100
        suspects["RISK_SCORE"] = (
            poids["transit"] * suspects["r_transit"]
            + poids["diversite"] * suspects["r_diversite"]
            + poids["pagerank"] * suspects["r_pagerank"]
            + poids["cluster"] * suspects["r_cluster"]).clip(0, 100)

        suspects = suspects.sort_values("RISK_SCORE", ascending=False)
        suspects["ALERTE"] = 0
        suspects.iloc[:budget, suspects.columns.get_loc("ALERTE")] = 1

        # 7. Explicabilité
        alertes = suspects[suspects["ALERTE"] == 1].copy()

        def raison(r):
            out = []
            if r["transit_score"] > 0.8:
                out.append("relais quasi-parfait (entrée≈sortie)")
            if r["in_degree"] >= 10:
                out.append(f"{int(r['in_degree'])} sources")
            if r["out_degree"] >= 10:
                out.append(f"{int(r['out_degree'])} destinations")
            if r["cluster"] >= 0:
                out.append("membre d'un réseau organisé")
            if r["r_pagerank"] > 95:
                out.append("position centrale dans le réseau")
            return " + ".join(out) if out else "profil de transit atypique"

        alertes["RAISON"] = alertes.apply(raison, axis=1)

        cols = ["node", "in_degree", "out_degree", "in_montant", "out_montant",
                "ratio_transit", "transit_score", "pagerank", "cluster", "RISK_SCORE"]
        return {
            "alertes": alertes[cols + ["RAISON"]],
            "scores": suspects[cols + ["ALERTE"]],
            "stats": {
                "n_alertes": int(len(alertes)),
                "n_transit": int(len(suspects)),
                "n_clusters": int(n_clusters),
                "n_aretes": int(len(edges)),
            },
        }
