"""Inférence M6 — réconciliation par blocking, liens et parties."""
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

    @staticmethod
    def _table_vide() -> pd.DataFrame:
        return pd.DataFrame(columns=[
            "TRANSFER_ID", "jumeau_propose", "confiance",
            "source_appariement", "decision", "RAISON",
        ])

    def _scorer_impl(self, df: pd.DataFrame) -> dict:
        comp = self.artefacts["complementaires"]
        seuil_auto = float(self.config.get("seuil_confiance_auto", 85))
        delai_max_h = float(self.config.get("delai_max_h", 24))

        d = df.drop_duplicates(subset=[cfg.COL_TRANSFER_ID], keep="first").copy()
        d[cfg.COL_MONTANT] = pd.to_numeric(d[cfg.COL_MONTANT], errors="coerce").fillna(0)
        d[cfg.COL_DATE] = pd.to_datetime(d[cfg.COL_DATE], errors="coerce")

        parts = d[cfg.COL_TRANSFER_ID].astype(str).str.split(".", expand=True)
        d["id_prefixe"] = parts[0].str[:2]
        d["id_date"] = parts[0].str[2:]
        d["id_session"] = parts[1] if parts.shape[1] > 1 else ""
        d["bloc"] = d["id_date"].astype(str) + "_" + d["id_session"].astype(str)

        ref = d[[cfg.COL_TRANSFER_ID, cfg.COL_MONTANT, cfg.COL_DATE, "bloc",
                 "id_prefixe", cfg.COL_SENDER_ID, cfg.COL_RECVR_ID]].rename(columns={
            cfg.COL_TRANSFER_ID: cfg.COL_RECON_FOR,
            cfg.COL_MONTANT: "j_montant", cfg.COL_DATE: "j_date",
            "bloc": "bloc_jumeau", "id_prefixe": "pref_jumeau",
            cfg.COL_SENDER_ID: "j_sender", cfg.COL_RECVR_ID: "j_receiver"})
        rec = d[d[cfg.COL_RECON_FOR].notna()].merge(ref, on=cfg.COL_RECON_FOR, how="left")
        rec["lien_valide"] = rec["j_montant"].notna()

        if rec.empty:
            vide = self._table_vide()
            return {
                "alertes": vide.copy(), "scores": vide.copy(), "manuels": vide.copy(),
                "stats": self._stats(vide, vide, vide, 0),
            }

        directs = rec[rec["lien_valide"]].copy()
        directs["ecart_montant"] = np.abs(directs[cfg.COL_MONTANT] - directs["j_montant"])
        directs["delai_h"] = (directs[cfg.COL_DATE] - directs["j_date"]) \
            .abs().dt.total_seconds() / 3600
        directs["meme_bloc"] = (directs["bloc"] == directs["bloc_jumeau"]).astype(int)
        directs["confiance"] = (
            40 + (directs["ecart_montant"] < 1) * 30
            + directs["meme_bloc"] * 15
            + (directs["delai_h"] < delai_max_h) * 15)
        directs["jumeau_propose"] = directs[cfg.COL_RECON_FOR]
        directs["source_appariement"] = "lien_direct"
        directs["RAISON"] = "lien déclaré contrôlé sur montant, bloc et délai"

        orphelins = rec[~rec["lien_valide"]].copy()
        sub = d[[cfg.COL_TRANSFER_ID, cfg.COL_MONTANT, cfg.COL_DATE, "bloc",
                 "id_prefixe", cfg.COL_SENDER_ID, cfg.COL_RECVR_ID]]
        idx_bloc = {b: g.reset_index(drop=True) for b, g in sub.groupby("bloc")}
        propositions = []
        sans_candidat = []
        for _, row in orphelins.iterrows():
            g = idx_bloc.get(row["bloc"])
            if g is None:
                sans_candidat.append(row)
                continue
            candidats = g[
                (np.abs(g[cfg.COL_MONTANT] - row[cfg.COL_MONTANT]) < 1)
                & (g[cfg.COL_TRANSFER_ID] != row[cfg.COL_TRANSFER_ID])].copy()
            if candidats.empty:
                sans_candidat.append(row)
                continue
            score = 1
            prefixe_attendu = comp.get(row["id_prefixe"])
            if prefixe_attendu and (candidats["id_prefixe"] == prefixe_attendu).any():
                candidats = candidats[candidats["id_prefixe"] == prefixe_attendu]
                score += 1
            if len(candidats) > 1:
                sender, receiver = row[cfg.COL_SENDER_ID], row[cfg.COL_RECVR_ID]
                meme_parties = (
                    ((candidats[cfg.COL_SENDER_ID] == sender)
                     & (candidats[cfg.COL_RECVR_ID] == receiver))
                    | ((candidats[cfg.COL_SENDER_ID] == receiver)
                       & (candidats[cfg.COL_RECVR_ID] == sender)))
                if meme_parties.any():
                    candidats = candidats[meme_parties]
                    score += 2
            best_idx = (candidats[cfg.COL_DATE] - row[cfg.COL_DATE]).abs().idxmin()
            propositions.append({
                "TRANSFER_ID": row[cfg.COL_TRANSFER_ID],
                "jumeau_propose": candidats.loc[best_idx, cfg.COL_TRANSFER_ID],
                "confiance": min(40 + score * 15, 100),
                "score_criteres": score,
                "source_appariement": "blocking",
                "RAISON": "candidat trouvé par bloc, montant, préfixe et parties",
            })

        prop_df = pd.DataFrame(propositions)
        manuels = pd.DataFrame(sans_candidat)
        if manuels.empty:
            manuels = self._table_vide()
        else:
            manuels = manuels.rename(columns={cfg.COL_TRANSFER_ID: "TRANSFER_ID"})
            manuels["jumeau_propose"] = pd.NA
            manuels["confiance"] = 0
            manuels["source_appariement"] = "aucun_candidat"
            manuels["decision"] = "MANUEL"
            manuels["RAISON"] = "aucun candidat compatible trouvé"

        cols = ["TRANSFER_ID", "jumeau_propose", "confiance",
                "source_appariement", "RAISON"]
        directs_out = directs.rename(columns={cfg.COL_TRANSFER_ID: "TRANSFER_ID"})[cols]
        prop_out = prop_df[cols] if not prop_df.empty else self._table_vide()[cols]
        candidats = pd.concat([directs_out, prop_out], ignore_index=True)
        automatiques = candidats[candidats["confiance"] >= seuil_auto].copy()
        suggestions = candidats[candidats["confiance"] < seuil_auto].copy()
        automatiques["decision"] = "AUTOMATIQUE"
        suggestions["decision"] = "A_VALIDER"

        total = len(rec)
        stats = self._stats(automatiques, suggestions, manuels, total)
        if stats["n_auto_fiable"] + stats["n_suggestion"] + stats["n_manuel"] != total:
            raise RuntimeError("Répartition M6 incohérente : les catégories ne couvrent pas le total")
        return {
            "alertes": suggestions,
            "scores": automatiques,
            "manuels": manuels,
            "stats": stats,
        }

    @staticmethod
    def _stats(automatiques: pd.DataFrame, suggestions: pd.DataFrame,
               manuels: pd.DataFrame, total: int) -> dict:
        n_auto, n_sugg, n_manuel = len(automatiques), len(suggestions), len(manuels)
        return {
            "n_alertes": int(n_sugg),
            "n_a_reconcilier": int(total),
            "n_auto_fiable": int(n_auto),
            "n_suggestion": int(n_sugg),
            "n_manuel": int(n_manuel),
            "taux_auto_pct": round(n_auto / max(total, 1) * 100, 1),
            "gain_heures": round(n_auto * 3 / 60, 0),
        }

    def exporter(self, resultats: dict, rep_sortie):
        fichiers = super().exporter(resultats, rep_sortie)
        manuels = resultats.get("manuels")
        if manuels is not None and len(manuels):
            f_manuels = rep_sortie / f"{self.NOM}_manuels.csv"
            manuels.to_csv(f_manuels, index=False, encoding="utf-8-sig")
            fichiers.append(f_manuels)
        return fichiers
