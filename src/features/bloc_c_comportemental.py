"""
bloc_c_comportemental.py — Features comportementales glissantes
================================================================
Le cœur du modèle. Calcul CAUSAL (uniquement le passé de chaque compte)
pour éviter toute fuite de données.

Fenêtres :
  - 7j glissant   : vélocité court terme (rafales mule/fraude)
  - profil complet : déviation au comportement habituel (prise de contrôle)
  - ancienneté    : feature de confiance (évite faux positifs comptes neufs)

IMPORTANT : le DataFrame DOIT être trié par [SENDER_USER_ID, CREATED_ON]
avant d'appeler build().
"""

import numpy as np
import pandas as pd
import time
from .. import config as cfg


def build(df, verbose=True):
    """
    Ajoute les features comportementales.
    Prérequis : df TRIÉ par [COL_SENDER_ID, COL_DATE].

    Méthode robuste : la vélocité 7j est calculée par searchsorted vectorisé
    (une valeur par ligne garantie, insensible aux clés manquantes ou aux
    timestamps dupliqués).
    """
    debut = time.time()
    grp_col = cfg.COL_SENDER_ID

    # ── Nettoyage : retirer les lignes sans date ──
    n_avant = len(df)
    df = df[df[cfg.COL_DATE].notna()].copy()
    if verbose and n_avant != len(df):
        print(f"  {n_avant - len(df)} ligne(s) sans date retirée(s)")

    # ── Sécuriser la clé de groupe : remplacer les SENDER_USER_ID manquants ──
    # (sinon groupby/rolling écarte ces lignes -> désalignement)
    # Si la colonne est de type 'category' (downcasting), on la repasse en str
    # car on ne peut pas fillna avec une nouvelle catégorie inexistante.
    if isinstance(df[grp_col].dtype, pd.CategoricalDtype):
        df[grp_col] = df[grp_col].astype(str)
    df[grp_col] = df[grp_col].fillna("__UNKNOWN__").replace(
        {"nan": "__UNKNOWN__", "None": "__UNKNOWN__", "": "__UNKNOWN__"})

    # Re-trier pour garantir l'ordre (compte, date) après nettoyage
    df = df.sort_values([grp_col, cfg.COL_DATE]).reset_index(drop=True)

    # ── Vélocité 7j + montant 7j (searchsorted vectorisé, sans perte) ──
    montant = df[cfg.COL_MONTANT].to_numpy()
    # timestamps en nanosecondes -> secondes
    t_ns = df[cfg.COL_DATE].to_numpy(dtype="datetime64[ns]").astype("int64")
    sept_jours = 7 * 24 * 3600 * 1_000_000_000  # 7 jours en ns

    velocite = np.ones(len(df), dtype=np.float64)
    montant7 = montant.copy()

    # Bornes de chaque groupe (df est trié par grp_col)
    codes = pd.factorize(df[grp_col], sort=False)[0]
    # cumul du montant pour calcul rapide des sommes par fenêtre
    cumsum = np.concatenate([[0.0], np.cumsum(montant)])

    # Pour chaque groupe, fenêtre glissante via searchsorted sur les temps
    debut_grp = 0
    n = len(df)
    i = 0
    while i < n:
        g = codes[i]
        j = i
        while j < n and codes[j] == g:
            j += 1
        # groupe = lignes [i, j)
        t_grp = t_ns[i:j]
        # pour chaque position k, trouver le 1er index dont t >= t_k - 7j
        bornes = t_grp - sept_jours
        starts = np.searchsorted(t_grp, bornes, side="left")
        # nb de transactions dans la fenêtre = position - start + 1
        positions = np.arange(len(t_grp))
        velocite[i:j] = (positions - starts + 1).astype(np.float64)
        # somme des montants dans la fenêtre via cumsum global
        # cumsum index décalé de i
        cs_grp = np.concatenate([[0.0], np.cumsum(montant[i:j])])
        montant7[i:j] = cs_grp[positions + 1] - cs_grp[starts]
        i = j

    df["f_velocite_7j"]    = np.clip(velocite, None, 5000)
    df["f_log_velocite_7j"]= np.log1p(velocite)  # capture les ordres de grandeur
    df["f_montant_7j"]     = montant7
    df["f_log_montant_7j"] = np.log1p(df["f_montant_7j"].clip(lower=0))
    if verbose:
        print(f"  vélocité 7j OK | {time.time()-debut:.0f}s")

    # ── Profil historique complet (causal via expanding + shift) ──
    grp = df.groupby(grp_col)[cfg.COL_MONTANT]
    moy_hist = grp.transform(lambda x: x.expanding().mean().shift(1).fillna(x.iloc[0]))
    std_hist = grp.transform(lambda x: x.expanding().std().shift(1).fillna(0))

    df["f_ratio_vs_profil"] = np.where(
        moy_hist > 0, (df[cfg.COL_MONTANT] / (moy_hist + 1)).clip(0, 50), 1)
    df["f_zscore_montant"] = np.where(
        std_hist > 0,
        ((df[cfg.COL_MONTANT] - moy_hist) / (std_hist + 1)).clip(-10, 10), 0)
    if verbose:
        print(f"  profil compte OK | {time.time()-debut:.0f}s")

    # ── Diversité destinataires (cumul causal) ──
    # On utilise la version "fast" car expanding().apply(nunique) ne gère
    # pas les colonnes string (RECEIVER_USER_ID) et est lent sur 30M lignes.
    df["f_nb_dest_cumul"] = nb_dest_cumul_fast(df)

    # ── Taux d'échec historique (causal) ──
    is_fail = (df[cfg.COL_STATUT] == "TF").astype(int)
    df["f_taux_echec_hist"] = (
        is_fail.groupby(df[grp_col])
        .transform(lambda x: x.expanding().mean().shift(1).fillna(0))
    )

    # ── Ancienneté (jours depuis 1ère transaction) ──
    premiere = df.groupby(grp_col)[cfg.COL_DATE].transform("min")
    df["f_anciennete_jours"] = ((df[cfg.COL_DATE] - premiere)
                                .dt.total_seconds() / 86400).clip(0, 32)

    # ── Rang de la transaction ──
    df["f_rang_tx"] = df.groupby(grp_col).cumcount().clip(upper=1000)

    # ── Neutraliser les features de groupe pour les comptes inconnus ──
    # Les lignes sans SENDER_USER_ID ont été regroupées sous "__UNKNOWN__".
    # Leurs features comportementales (vélocité, rang, profil) sont des
    # artefacts (faux "compte" hyperactif) -> on les remet à neutre.
    mask_unknown = (df[grp_col] == "__UNKNOWN__")
    n_unknown = mask_unknown.sum()
    if n_unknown > 0:
        cols_neutres = {
            "f_velocite_7j": 1, "f_log_velocite_7j": 0,
            "f_montant_7j": df[cfg.COL_MONTANT], "f_log_montant_7j": None,
            "f_ratio_vs_profil": 1, "f_zscore_montant": 0,
            "f_nb_dest_cumul": 1, "f_taux_echec_hist": 0,
            "f_rang_tx": 0,
        }
        for col, val in cols_neutres.items():
            if col not in df.columns:
                continue
            if col == "f_montant_7j":
                df.loc[mask_unknown, col] = df.loc[mask_unknown, cfg.COL_MONTANT]
            elif col == "f_log_montant_7j":
                df.loc[mask_unknown, col] = np.log1p(
                    df.loc[mask_unknown, cfg.COL_MONTANT].clip(lower=0))
            else:
                df.loc[mask_unknown, col] = val
        if verbose:
            print(f"  {n_unknown} ligne(s) __UNKNOWN__ neutralisée(s)")

    if verbose:
        print(f"✅ Bloc C complet | {time.time()-debut:.0f}s")
    return df


def feature_names():
    return ["f_velocite_7j", "f_log_velocite_7j", "f_montant_7j", "f_log_montant_7j",
            "f_ratio_vs_profil", "f_zscore_montant", "f_nb_dest_cumul",
            "f_taux_echec_hist", "f_anciennete_jours", "f_rang_tx"]


# ── Variante optimisée de f_nb_dest_cumul (si la version expanding est lente) ──
def nb_dest_cumul_fast(df):
    """
    Version rapide du comptage de destinataires distincts cumulés.
    À utiliser si expanding().apply(nunique) est trop lent sur 30M lignes.
    """
    seen = {}
    out = np.empty(len(df), dtype=np.int32)
    senders = df[cfg.COL_SENDER_ID].values
    recvrs  = df[cfg.COL_RECVR_ID].values
    for i in range(len(df)):
        s = senders[i]
        if s not in seen:
            seen[s] = set()
        seen[s].add(recvrs[i])
        out[i] = len(seen[s])
    return np.clip(out, None, 200)
