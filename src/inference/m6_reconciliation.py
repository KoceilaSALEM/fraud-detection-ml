"""
Inférence M6 — Réconciliation automatique (blocking + parties).

Moteur de règles validé à 86.6% de précision (vérité terrain cachée) :
  1. parsing TRANSFER_ID -> (préfixe, date, session) = clé de blocage
  2. lien direct RECONCILIATION_FOR validé (montant/bloc/délai) -> AUTO
  3. orphelins -> candidat par (bloc + montant + préfixe + PARTIES)
  4. séparation production : auto fiable / suggestion analyste / manuel

Les préfixes complémentaires (CO<->TC...) viennent des params figés.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src import config as cfg
from src.inference.base import BaseInference


class InferenceM6(BaseInference):
    NOM = "M6_reconciliation"
    DOSSIER_MODELE = "M6_reconciliation"

    def charger_artefacts(self) -> None:
        d = self._dossier_artefacts()
        self.artefacts["params"] = self._charger_params(d)
        self.artefacts["complementaires"] = self.artefacts["params"].get(
            "complementaires", {})
        self.logger.info(
            f"M6 chargé : préfixes complémentaires {self.artefacts['complementaires']}")

    def _scorer_impl(self, df: pd.DataFrame) -> dict:
        comp = self.artefacts["complementaires"]
        seuil_auto = self.config.get("seuil_confiance_auto", 85)
        delai_max_h = self.config.get("delai_max_h", 24)

        d = df.drop_duplicates(subset=[cfg.COL_TRANSFER_ID], keep="first").copy()
        d[cfg.COL_MONTANT] = pd.to_numeric(d[cfg.COL_MONTANT], errors="coerce").fillna(0)
        if not pd.api.types.is_datetime64_any_dtype(d[cfg.COL_DATE]):
            d[cfg.COL_DATE] = pd.to_datetime(d[cfg.COL_DATE], errors="coerce")

        # 1. Parsing TRANSFER_ID
        parts = d[cfg.COL_TRANSFER_ID].astype(str).str.split(".", expand=True)
        d["id_prefixe"] = parts[0].str[:2]
        d["id_date"] = parts[0].str[2:]
        d["id_session"] = parts[1] if parts.shape[1] > 1 else ""
        d["bloc"] = d["id_date"].astype(str) + "_" + d["id_session"].astype(str)

        # 2. Enrichir avec le jumeau (merge vectorisé, pas de dict 25M)
        ref = d[[cfg.COL_TRANSFER_ID, cfg.COL_MONTANT, cfg.COL_DATE, "bloc",
                 "id_prefixe", cfg.COL_SENDER_ID, cfg.COL_RECVR_ID]].rename(columns={
            cfg.COL_TRANSFER_ID: cfg.COL_RECON_FOR,
            cfg.COL_MONTANT: "j_montant", cfg.COL_DATE: "j_date",
            "bloc": "bloc_jumeau", "id_prefixe": "pref_jumeau",
            cfg.COL_SENDER_ID: "j_sender", cfg.COL_RECVR_ID: "j_receiver"})
        rec = d[d[cfg.COL_RECON_FOR].notna()].merge(ref, on=cfg.COL_RECON_FOR, how="left")
        rec["lien_valide"] = rec["j_montant"].notna()

        if len(rec) == 0:
            return {"alertes": pd.DataFrame(), "scores": pd.DataFrame(),
                    "stats": {"n_alertes": 0, "n_a_reconcilier": 0}}

        # 3. Liens directs : score de confiance
        directs = rec[rec["lien_valide"]].copy()
        directs["ecart_montant"] = np.abs(directs[cfg.COL_MONTANT] - directs["j_montant"])
        directs["delai_h"] = (directs[cfg.COL_DATE] - directs["j_date"]) \
            .abs().dt.total_seconds() / 3600
        directs["meme_bloc"] = (directs["bloc"] == directs["bloc_jumeau"]).astype(int)
        directs["confiance"] = (40 + (directs["ecart_montant"] < 1) * 30
                                + directs["meme_bloc"] * 15
                                + (directs["delai_h"] < delai_max_h) * 15)

        # 4. Orphelins : appariement par blocking + parties
        orphelins = rec[~rec["lien_valide"]].copy()
        sub = d[[cfg.COL_TRANSFER_ID, cfg.COL_MONTANT, cfg.COL_DATE, "bloc",
                 "id_prefixe", cfg.COL_SENDER_ID, cfg.COL_RECVR_ID]]
        idx_bloc = {b: g.reset_index(drop=True) for b, g in sub.groupby("bloc")}
        suggestions = []
        for _, row in orphelins.iterrows():
            g = idx_bloc.get(row["bloc"])
            if g is None:
                continue
            c = g[(np.abs(g[cfg.COL_MONTANT] - row[cfg.COL_MONTANT]) < 1)
                  & (g[cfg.COL_TRANSFER_ID] != row[cfg.COL_TRANSFER_ID])]
            if len(c) == 0:
                continue
            score = 1
            pa = comp.get(row["id_prefixe"])
            if pa and (c["id_prefixe"] == pa).any():
                c = c[c["id_prefixe"] == pa]
                score += 1
            if len(c) > 1:
                s, r = row[cfg.COL_SENDER_ID], row[cfg.COL_RECVR_ID]
                mask = (((c[cfg.COL_SENDER_ID] == s) & (c[cfg.COL_RECVR_ID] == r))
                        | ((c[cfg.COL_SENDER_ID] == r) & (c[cfg.COL_RECVR_ID] == s)))
                if mask.any():
                    c = c[mask]
                    score += 2
            best = c.loc[(c[cfg.COL_DATE] - row[cfg.COL_DATE]).abs().idxmin(),
                         cfg.COL_TRANSFER_ID]
            suggestions.append({
                "TRANSFER_ID": row[cfg.COL_TRANSFER_ID], "jumeau_propose": best,
                "score_criteres": score, "confiance": min(40 + score * 15, 100)})
        sugg_df = pd.DataFrame(suggestions)

        # 5. Séparation production
        n_total = len(rec)
        n_auto = int((directs["confiance"] >= seuil_auto).sum()
                     + ((sugg_df["score_criteres"] >= 3).sum() if len(sugg_df) else 0))
        n_sugg = int((directs["confiance"] < seuil_auto).sum()
                     + ((sugg_df["score_criteres"] < 3).sum() if len(sugg_df) else 0))
        n_manuel = n_total - n_auto - n_sugg

        cols_auto = [c for c in [cfg.COL_TRANSFER_ID, cfg.COL_RECON_FOR, cfg.COL_MONTANT,
                                 "confiance", "meme_bloc", "delai_h"] if c in directs.columns]
        return {
            "alertes": sugg_df,                       # suggestions à valider par analyste
            "scores": directs[cols_auto],             # appariements auto
            "stats": {
                "n_alertes": int(len(sugg_df)),
                "n_a_reconcilier": n_total,
                "n_auto_fiable": n_auto,
                "n_suggestion": n_sugg,
                "n_manuel": n_manuel,
                "taux_auto_pct": round(n_auto / max(n_total, 1) * 100, 1),
                "gain_heures": round(n_auto * 3 / 60, 0),
            },
        }
