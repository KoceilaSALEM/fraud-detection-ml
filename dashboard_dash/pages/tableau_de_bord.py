"""
Onglet 1 — Tableau de bord (consultation des résultats, public analystes).

Portage Dash de la fonction `page_dashboard()` + toutes les `vue_*()` de
dashboard/app.py (Streamlit).

Différence structurelle importante vs Streamlit
--------------------------------------------------
La version Streamlit utilisait des variables *globales de module*
(run_id, rapport, ok, ko, drift_v) réécrites à chaque script-run pour les
partager entre `page_dashboard()` et les fonctions `vue_*()`. Ce pattern
fonctionne en Streamlit (un seul utilisateur, un seul thread, script relancé
en entier à chaque interaction) mais est risqué en Dash : le process serveur
est partagé par tous les analystes connectés simultanément. On passe donc
maintenant un contexte explicite `ctx = {"rapport", "run_id", "ok", "ko",
"drift_v"}` en paramètre de chaque fonction de vue — aucune variable globale
mutable.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import dash
from dash import Input, Output, State, ALL, dcc, html, callback

import data_access as da
import network_view as nv
import theme
from theme import (ORANGE, CRITIQUE, ELEVE, MODERE, NORMAL, badge, entete_vue,
                    kpi, kpi_row, plotly_layout, vide)

dash.register_page(__name__, path="/", name="Tableau de bord", title="Orange Money — RA&FM")


# ════════════════════════ layout (coquille) ════════════════════════
def layout():
    return html.Div([
        dcc.Store(id="vue-content-trigger"),
        html.Div(id="vue-content"),
        dcc.Download(id="global-download"),
    ])


# ════════════════════════ VUE SYNTHÈSE ════════════════════════
def vue_synthese(ctx):
    rapport, run_id, ok, ko, drift_v = (ctx["rapport"], ctx["run_id"], ctx["ok"],
                                         ctx["ko"], ctx["drift_v"])
    n_entree = next((s.get("n_entree") for s in rapport.get("modeles", {}).values()
                      if s.get("n_entree")), None)
    sous = f"Run {run_id}" + (f" · {da.fmt(n_entree)} transactions" if n_entree else "") \
           + f" · {rapport.get('duree_totale_s', '?')} s"
    badges = [
        badge(f"{len(ok)}/5 modèles", "ok" if not ko else "crit"),
        badge(f"drift {drift_v}",
              {"stable": "ok", "ATTENTION": "warn"}.get(drift_v, "crit")
              if drift_v != "n/a" else "info"),
    ]

    m1 = da.stats_modele(rapport, "m1_fraude")
    m2 = da.stats_modele(rapport, "m2_mules")
    m4 = da.stats_modele(rapport, "m4_commissions")
    m6 = da.stats_modele(rapport, "m6_reconciliation")
    total_alertes = sum(s.get("n_alertes", 0) for s in rapport.get("modeles", {}).values())

    kpis = kpi_row(
        kpi(da.fmt(total_alertes), "alertes à traiter", "tous modèles confondus",
            "crit" if total_alertes > 0 else "ok"),
        kpi(m1.get("n_alertes", "—"), "fraude (M1)",
            f"budget {m1.get('budget_jour', '—')}/j" if m1 else "non exécuté"),
        kpi(m2.get("n_alertes", "—"), "mules (M2)",
            f"{m2.get('n_clusters', '—')} réseaux" if m2 else "non exécuté"),
        kpi(m4.get("n_alertes", "—"), "commissions (M4)", "" if m4 else "non exécuté"),
        kpi(f"{m6.get('taux_auto_pct', '—')} %", "réconciliation auto (M6)",
            f"{da.fmt(m6.get('gain_heures', 0))} h gagnées" if m6 else "non exécuté", "ok"),
    )

    graph_par_modele = None
    donnees = [(da.MODELES.get(next((K for K in da.MODELES if K.lower() == k), k), k),
                v.get("n_alertes", 0))
               for k, v in rapport.get("modeles", {}).items()]
    if donnees:
        df = pd.DataFrame(donnees, columns=["Modèle", "Alertes"])
        fig = px.bar(df, x="Alertes", y="Modèle", orientation="h", text="Alertes")
        fig.update_traces(marker_color=ORANGE, textposition="auto")
        graph_par_modele = dcc.Graph(figure=plotly_layout(fig, 290), config={"displayModeBar": False})

    ok_l, ko_l = [m.lower() for m in ok], [m.lower() for m in ko]
    lignes = []
    for cle, nom in da.MODELES.items():
        k = cle.lower()
        statut = "✅ OK" if k in ok_l else "❌ Échec" if k in ko_l else "— non exécuté"
        lignes.append({"Modèle": nom, "Statut": statut})
    tableau_etats = theme.grid(pd.DataFrame(lignes), height="220px", page_size=6)

    erreurs = []
    if rapport.get("erreurs"):
        for m, e in rapport["erreurs"].items():
            erreurs.append(html.Div(f"⚠ {m} : {e[:140]}", className="vide",
                                     style={"borderColor": CRITIQUE, "color": CRITIQUE,
                                            "textAlign": "left", "marginTop": "6px"}))

    hist_graph = None
    hist = da.charger_historique_runs()
    if len(hist) > 1:
        h = pd.DataFrame([{
            "run": r["run_id"],
            "alertes": sum(s.get("n_alertes", 0) for s in r.get("modeles", {}).values()),
        } for r in hist[-30:]])
        fig = go.Figure(go.Scatter(x=h["run"], y=h["alertes"], mode="lines+markers",
                                    line=dict(color=ORANGE, width=2), marker=dict(size=7)))
        hist_graph = dcc.Graph(figure=plotly_layout(fig, 250), config={"displayModeBar": False})

    return html.Div([
        entete_vue("Synthèse du run", sous, badges),
        kpis,
        html.Div([
            html.Div([html.H6("Alertes par modèle"), graph_par_modele],
                     style={"flex": "3", "minWidth": "320px"}),
            html.Div([html.H6("État des modèles"), tableau_etats, *erreurs],
                     style={"flex": "2", "minWidth": "260px"}),
        ], style={"display": "flex", "gap": "1.5rem", "flexWrap": "wrap", "marginTop": "1rem"}),
        html.Div([html.H6("Historique des runs"), hist_graph],
                 style={"marginTop": "1rem"}) if hist_graph else None,
    ])


def _bouton_export(modele: str, label: str = "⬇ Exporter (CSV)"):
    return html.Button(label, id={"type": "dl-btn", "modele": modele},
                       className="btn-export")


# ════════════════════════ VUE M1 — FRAUDE ════════════════════════
def vue_m1(ctx):
    rapport, run_id = ctx["rapport"], ctx["run_id"]
    s = da.stats_modele(rapport, "m1_fraude")
    entete = entete_vue("Fraude transactionnelle — M1",
                         "Isolation Forest par groupe de pairs · budget d'alertes journalier",
                         badge("peer-group", "brand"))
    if not s:
        return html.Div([entete, vide("M1 n'a pas été exécuté dans ce run.")])

    kpis = kpi_row(
        kpi(da.fmt(s.get("n_alertes", 0)), "alertes",
            f"{s.get('pct_alertes', 0)} % des transactions", "crit"),
        kpi(s.get("budget_jour", "—"), "budget / jour", "capacité analystes"),
        kpi(s.get("score_moyen_alertes", "—"), "score moyen", "des alertes émises"),
        kpi(f"{s.get('duree_s', '—')} s", "durée scoring"),
    )

    graphes = []
    segments = s.get("segments", {})
    if segments:
        df = pd.DataFrame(list(segments.items()), columns=["Segment", "Transactions"])
        fig = px.bar(df, x="Segment", y="Transactions", text="Transactions")
        fig.update_traces(marker_color=MODERE)
        graphes.append(html.Div([html.H6("Transactions par segment (groupes de pairs)"),
                                  dcc.Graph(figure=plotly_layout(fig, 300),
                                            config={"displayModeBar": False})],
                                 style={"flex": "1", "minWidth": "320px"}))

    alertes = da.charger_alertes(run_id, "M1_fraude")
    corps = []
    if alertes is not None and len(alertes):
        if "SEGMENT" in alertes.columns:
            rep = alertes["SEGMENT"].value_counts().reset_index()
            rep.columns = ["Segment", "Alertes"]
            fig = px.bar(rep, x="Segment", y="Alertes", text="Alertes")
            fig.update_traces(marker_color=ORANGE)
            graphes.append(html.Div([html.H6("Alertes par segment"),
                                      dcc.Graph(figure=plotly_layout(fig, 300),
                                                config={"displayModeBar": False})],
                                     style={"flex": "1", "minWidth": "320px"}))

        corps = [
            html.H6("File d'alertes priorisée"),
            html.P("Triée par score de risque — chaque alerte porte sa raison.",
                   className="vue-sous"),
            theme.grid(alertes.head(300)),
            _bouton_export("M1_fraude"),
        ]
    else:
        corps = [vide("Aucune alerte M1 dans ce run.")]

    return html.Div([
        entete, kpis,
        html.Div(graphes, style={"display": "flex", "gap": "1.5rem", "flexWrap": "wrap",
                                  "margin": "1rem 0"}) if graphes else None,
        *corps,
    ])


# ════════════════════════ VUE M2 — MULES ════════════════════════
def vue_m2(ctx):
    rapport = ctx["rapport"]
    s = da.stats_modele(rapport, "m2_mules")
    entete = entete_vue("Réseaux de mules — M2",
                         "Transit + PageRank + clustering · graphe des flux",
                         badge("graphe", "brand"))
    if not s:
        return html.Div([entete, vide("M2 n'a pas été exécuté dans ce run.")])

    kpis = kpi_row(
        kpi(s.get("n_alertes", 0), "comptes à investiguer", "budget mules", "crit"),
        kpi(s.get("n_clusters", 0), "réseaux organisés", "clusters DBSCAN", "warn"),
        kpi(da.fmt(s.get("n_transit", 0)), "comptes de transit"),
        kpi(da.fmt(s.get("n_aretes", 0)), "arêtes du graphe"),
    )

    # NB : le graphe M2 lit toujours outputs/M2_mules (chemin fixe, pas par run) —
    # limitation connue et documentée du pipeline M2 (voir mémoire de fin d'études).
    m2_dir = str(da.ROOT / "outputs" / "M2_mules")
    return html.Div([entete, kpis, html.Hr(className="sep"),
                      nv.m2_layout("m2net", outputs_dir=m2_dir)])


# ════════════════════════ VUE M4 — COMMISSIONS ════════════════════
def vue_m4(ctx):
    rapport, run_id = ctx["rapport"], ctx["run_id"]
    s = da.stats_modele(rapport, "m4_commissions")
    entete = entete_vue("Anomalies commissions — M4",
                         "Z-score vs norme historique figée · agrégation jour × service",
                         badge("revenue assurance", "brand"))
    if not s:
        return html.Div([entete, vide("M4 n'a pas été exécuté dans ce run.")])

    inconnus = s.get("services_inconnus", [])
    kpis = kpi_row(
        kpi(s.get("n_alertes", 0), "anomalies détectées", "", "warn"),
        kpi(s.get("n_jours_services", 0), "couples jour × service analysés"),
        kpi(len(inconnus), "services hors référence",
            ", ".join(map(str, inconnus[:3])) + ("…" if len(inconnus) > 3 else ""),
            "warn" if inconnus else "ok"),
    )

    corps = []
    alertes = da.charger_alertes(run_id, "M4_commissions")
    if alertes is not None and len(alertes):
        fig = px.scatter(alertes, x="jour", y="z_score", color="service", size="volume",
                          hover_data=["metrique", "valeur", "reference"])
        fig.add_hline(y=3, line_dash="dot", line_color=ELEVE)
        fig.add_hline(y=-3, line_dash="dot", line_color=ELEVE)
        corps = [
            html.H6("Déviations par jour et service"),
            dcc.Graph(figure=plotly_layout(fig, 330), config={"displayModeBar": False}),
            html.H6("Détail des anomalies"),
            theme.grid(alertes),
            _bouton_export("M4_commissions"),
        ]
    else:
        corps = [vide("Aucune anomalie de commission — facturation conforme à la norme.")]

    return html.Div([entete, kpis, *corps])


# ════════════════════════ VUE M5 — ÉCHEC ════════════════════════
def vue_m5(ctx):
    rapport, run_id = ctx["rapport"], ctx["run_id"]
    s = da.stats_modele(rapport, "m5_echec")
    entete = entete_vue("Prédiction d'échec — M5",
                         "LightGBM supervisé · ROC-AUC 0.96 (validation temporelle)",
                         badge("supervisé", "brand"))
    if not s:
        return html.Div([entete, vide("M5 n'a pas été exécuté dans ce run "
                                       "(nécessite le feature engineering — lancer "
                                       "sur la VM).")])

    kpis = kpi_row(
        kpi(da.fmt(s.get("n_alertes", 0)), "transactions à risque",
            f"proba ≥ {s.get('seuil', 0.8)}", "warn"),
        kpi(f"{s.get('pct_alertes', 0)} %", "part du volume"),
        kpi(s.get("proba_moyenne", "—"), "probabilité moyenne", "tout le lot"),
        kpi(f"{s.get('duree_s', '—')} s", "durée scoring"),
    )

    corps = []
    scores = da.charger_scores(run_id, "M5_echec")
    if scores is not None and "proba_echec" in scores.columns:
        ech = scores["proba_echec"].sample(min(len(scores), 100_000), random_state=1)
        fig = px.histogram(ech, nbins=50)
        fig.update_traces(marker_color=MODERE)
        fig.add_vline(x=s.get("seuil", 0.8), line_color=CRITIQUE, line_dash="dash",
                       annotation_text="seuil d'alerte")
        fig.update_layout(showlegend=False, yaxis_type="log")
        corps.append(html.H6("Distribution des probabilités d'échec"))
        corps.append(dcc.Graph(figure=plotly_layout(fig, 320), config={"displayModeBar": False}))

    alertes = da.charger_alertes(run_id, "M5_echec")
    if alertes is not None and len(alertes):
        corps += [html.H6("Transactions à plus fort risque d'échec"), theme.grid(alertes.head(300)),
                  _bouton_export("M5_echec")]

    return html.Div([entete, kpis, *corps])


# ════════════════════════ VUE M6 — RÉCONCILIATION ═══════════════
def vue_m6(ctx):
    rapport, run_id = ctx["rapport"], ctx["run_id"]
    s = da.stats_modele(rapport, "m6_reconciliation")
    entete = entete_vue("Réconciliation — M6",
                         "Record linkage (blocking + parties) · précision 86,6 % validée",
                         badge("record linkage", "brand"))
    if not s:
        return html.Div([entete, vide("M6 n'a pas été exécuté dans ce run.")])

    kpis = kpi_row(
        kpi(f"{s.get('taux_auto_pct', 0)} %", "réconciliation automatique",
            f"{da.fmt(s.get('n_auto_fiable', 0))} appariements fiables", "ok"),
        kpi(da.fmt(s.get("n_suggestion", 0)), "suggestions à valider", "file analyste", "warn"),
        kpi(da.fmt(s.get("n_manuel", 0)), "cas manuels", "sans candidat"),
        kpi(f"{da.fmt(s.get('gain_heures', 0))} h", "gain analyste estimé",
            "3 min / cas évité", "ok"),
    )

    rep = pd.DataFrame({
        "Catégorie": ["Automatique fiable", "Suggestion analyste", "Manuel"],
        "Volume": [s.get("n_auto_fiable", 0), s.get("n_suggestion", 0), s.get("n_manuel", 0)]})
    fig = px.pie(rep, names="Catégorie", values="Volume", hole=0.62, color="Catégorie",
                 color_discrete_map={"Automatique fiable": NORMAL,
                                      "Suggestion analyste": ELEVE, "Manuel": CRITIQUE})
    fig.update_traces(textinfo="percent")
    graphe = html.Div([html.H6("Répartition du traitement"),
                        dcc.Graph(figure=plotly_layout(fig, 320), config={"displayModeBar": False})],
                       style={"flex": "2", "minWidth": "280px"})

    alertes = da.charger_alertes(run_id, "M6_reconciliation")
    if alertes is not None and len(alertes):
        droite = html.Div([html.H6("Suggestions d'appariement (à valider)"),
                            theme.grid(alertes.head(300)), _bouton_export("M6_reconciliation")],
                           style={"flex": "3", "minWidth": "320px"})
    else:
        droite = html.Div([html.H6("Suggestions d'appariement (à valider)"),
                            vide("Aucune suggestion — tout est apparié automatiquement "
                                 "ou manuel.")], style={"flex": "3", "minWidth": "320px"})

    return html.Div([entete, kpis,
                      html.Div([graphe, droite], style={"display": "flex", "gap": "1.5rem",
                                                          "flexWrap": "wrap", "marginTop": "1rem"})])


VUES_CONSULTATION = {
    "Synthèse": vue_synthese,
    da.MODELES["M1_fraude"]: vue_m1, da.MODELES["M2_mules"]: vue_m2,
    da.MODELES["M4_commissions"]: vue_m4, da.MODELES["M5_echec"]: vue_m5,
    da.MODELES["M6_reconciliation"]: vue_m6,
}


# ════════════════════════ callbacks de la page ════════════════════════
@callback(
    Output("vue-content", "children"),
    Input("run-selector", "value"),
    Input("vue-selector", "value"),
    prevent_initial_call=False,
)
def _maj_vue(run_id, vue):
    if not run_id:
        return html.Div([
            html.P("👋 Bienvenue. Pour commencer : ouvrir l'onglet "
                   "« ⚙️ Données & Inférence » (barre latérale), déposer un "
                   "fichier et lancer le scoring. Les résultats apparaîtront ici."),
        ])

    rapport = da.charger_rapport(run_id)
    ok = rapport.get("modeles_ok", [])
    ko = rapport.get("modeles_ko", [])
    drift_v = (rapport.get("drift") or {}).get("verdict_global", "n/a")
    ctx = {"rapport": rapport, "run_id": run_id, "ok": ok, "ko": ko, "drift_v": drift_v}

    fn = VUES_CONSULTATION.get(vue or "Synthèse", vue_synthese)
    return fn(ctx)


@callback(
    Output("global-download", "data"),
    Input({"type": "dl-btn", "modele": ALL}, "n_clicks"),
    State("run-selector", "value"),
    prevent_initial_call=True,
)
def _exporter_csv(_n_clicks, run_id):
    if not isinstance(_n_clicks, list):
        _n_clicks = [_n_clicks]
    triggered = dash.ctx.triggered_id
    if not triggered or not any(_n_clicks):
        raise dash.exceptions.PreventUpdate
    modele = triggered["modele"]
    df = da.charger_alertes(run_id, modele)
    if df is None or not len(df):
        raise dash.exceptions.PreventUpdate
    return dcc.send_bytes(df.to_csv(index=False).encode("utf-8-sig"),
                           f"{modele}_alertes_{run_id}.csv")


nv.register_m2_callbacks("m2net")
