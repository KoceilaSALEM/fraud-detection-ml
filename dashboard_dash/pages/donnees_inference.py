"""
Onglet 2 — Données & Inférence (pilotage opérateur).

Portage Dash de `page_donnees()` dans dashboard/app.py (Streamlit).

Différence vs Streamlit : le rafraîchissement pendant un run actif ne bloque
plus le process serveur avec `time.sleep(10); st.rerun()`. On utilise un
`dcc.Interval` (10 s) purement côté client, qui déclenche un callback léger —
le serveur reste disponible pour les autres analystes pendant ce temps.
"""
from __future__ import annotations

import base64
from datetime import datetime

import dash
import pandas as pd
from dash import Input, Output, State, callback, dcc, html

import data_access as da
import theme
from theme import badge, entete_vue, kpi, kpi_row, vide

dash.register_page(__name__, path="/donnees", name="Données & Inférence",
                    title="Orange Money — RA&FM — Données")


def layout():
    return html.Div([
        entete_vue("Données & Inférence",
                   "Déposer un fichier, lancer le scoring, suivre l'avancement",
                   badge("pilotage", "brand")),

        html.Div(id="progress-container"),

        html.H6("1 · Déposer un fichier (CSV ou Parquet)"),
        dcc.Upload(
            id="file-upload",
            className="upload-zone",
            children=html.Div([
                "Glissez un fichier ici ou ", html.A("parcourez"),
                html.P("Export DWH mensuel · jusqu'à ~200 Mo via le navigateur. "
                       "Au-delà, déposer le fichier directement dans data/raw/ "
                       "(SFTP) : il apparaîtra dans la liste ci-dessous.",
                       className="vue-sous"),
            ]),
            multiple=False,
        ),
        html.Div(id="upload-status"),

        html.H6("2 · Choisir le fichier à scorer", style={"marginTop": "1.2rem"}),
        dcc.Dropdown(id="fichier-select", placeholder="Fichier…"),

        html.Div([
            dcc.Checklist(
                id="modeles-select",
                options=[{"label": f" {v.lower()}", "value": k}
                         for k, v in da.MODELES.items()],
                value=[],
                labelStyle={"display": "block", "marginTop": "4px"},
            ),
            html.P("Vide = les 5 modèles. M1 et M5 déclenchent le feature "
                   "engineering complet (long sur très gros fichiers).",
                   className="vue-sous"),
        ], style={"marginTop": ".6rem"}),

        html.H6("3 · Lancer", style={"marginTop": "1.2rem"}),
        html.Button("🚀 Lancer l'inférence", id="btn-lancer",
                    className="btn-primary-custom"),
        html.Div(id="lancer-msg", style={"marginTop": ".6rem"}),

        html.H6("Fichiers déjà analysés", style={"marginTop": "1.5rem"}),
        html.Div(id="historique-container"),

        dcc.Interval(id="poll-inference", interval=10_000, n_intervals=0),
        dcc.Store(id="cache-buster"),
    ])


# ═══════════ upload : enregistrement du fichier dans data/raw/ ═══════════
@callback(
    Output("upload-status", "children"),
    Output("cache-buster", "data"),
    Input("file-upload", "contents"),
    State("file-upload", "filename"),
    prevent_initial_call=True,
)
def _traiter_upload(contents, filename):
    if not contents or not filename:
        raise dash.exceptions.PreventUpdate
    dest = da.ROOT / "data" / "raw" / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return html.Div(f"ℹ {filename} existe déjà — il sera utilisé tel quel.",
                         className="vide"), dash.no_update

    _header, b64 = contents.split(",", 1)
    dest.write_bytes(base64.b64decode(b64))
    da.invalider_cache()
    return html.Div(f"✅ {filename} enregistré dans data/raw/",
                     style={"color": theme.NORMAL}), datetime.now().isoformat()


# ═══════════ liste des fichiers disponibles à scorer ═══════════
@callback(
    Output("fichier-select", "options"),
    Output("fichier-select", "value"),
    Input("poll-inference", "n_intervals"),
    Input("cache-buster", "data"),
)
def _maj_fichiers(_n, _cache_buster):
    fichiers = []
    for dossier in (da.ROOT / "data" / "raw", da.ROOT / "data" / "processed"):
        if dossier.exists():
            fichiers += [f for f in dossier.iterdir() if f.suffix in (".csv", ".parquet")]
    if not fichiers:
        return [], None
    fichiers = sorted(fichiers, key=lambda f: f.stat().st_mtime, reverse=True)
    options = [{
        "label": f"{f.name}  ·  {f.stat().st_size / 1e9:.2f} Go  ·  "
                 f"{datetime.fromtimestamp(f.stat().st_mtime):%d/%m/%Y %H:%M}",
        "value": str(f),
    } for f in fichiers]
    return options, options[0]["value"]


# ═══════════ lancement de l'inférence ═══════════
@callback(
    Output("lancer-msg", "children"),
    Input("btn-lancer", "n_clicks"),
    State("fichier-select", "value"),
    State("modeles-select", "value"),
    prevent_initial_call=True,
)
def _lancer(n_clicks, fichier, modeles):
    if not n_clicks or not fichier:
        raise dash.exceptions.PreventUpdate
    if da.runs_en_cours():
        return vide("Un run est déjà en cours — attendez sa fin avant d'en lancer un autre.")
    from pathlib import Path
    da.lancer_inference(Path(fichier), modeles or None)
    da.invalider_cache()
    return html.Div(f"Inférence lancée sur {Path(fichier).name} — suivi ci-dessus.",
                     style={"color": theme.NORMAL})


@callback(Output("btn-lancer", "disabled"), Input("poll-inference", "n_intervals"))
def _desactiver_bouton(_n):
    return bool(da.runs_en_cours())


# ═══════════ suivi de la progression (poll 10 s) ═══════════
@callback(Output("progress-container", "children"), Input("poll-inference", "n_intervals"))
def _maj_progression(_n):
    actifs = da.runs_en_cours()
    if not actifs:
        return None
    a = actifs[0]
    pct = max(int(a.get("pct", 0)), 1)
    try:
        debut = datetime.strptime(a["run_id"], "%Y%m%d_%H%M%S")
        ecoule = (datetime.now() - debut).total_seconds()
        restant = ecoule / pct * (100 - pct)
    except Exception:
        ecoule, restant = 0, 0

    kpis = kpi_row(
        kpi(f"{pct} %", "avancement", f"étape : {a.get('etape', '?')}", "warn"),
        kpi(f"{ecoule/60:.0f} min", "temps écoulé"),
        kpi(f"~{restant/60:.0f} min", "temps restant estimé", "affiné en cours de run"),
        kpi(a["run_id"], "identifiant du run"),
    )
    barre = html.Div(html.Div(style={"width": f"{pct}%", "height": "8px",
                                      "background": theme.ORANGE, "borderRadius": "4px",
                                      "transition": "width .4s"}),
                      style={"width": "100%", "height": "8px", "background": theme.BORDER,
                             "borderRadius": "4px", "margin": ".6rem 0"})
    return html.Div([
        html.H6("⏱ Inférence en cours"), kpis, barre,
        html.P("Suivi automatique toutes les 10 s. Le run apparaîtra dans le "
               "sélecteur du Tableau de bord une fois terminé.", className="vue-sous"),
    ])


# ═══════════ historique des fichiers déjà scorés ═══════════
@callback(Output("historique-container", "children"), Input("poll-inference", "n_intervals"))
def _maj_historique(_n):
    runs_l = da.lister_runs()
    if not runs_l:
        return vide("Aucun run d'inférence disponible.")
    lignes = []
    for rid in runs_l[:15]:
        try:
            r = da.charger_rapport(rid)
            per = r.get("periode") or {}
            lignes.append({
                "Run": rid, "Fichier": r.get("source", "—"),
                "Période données": f"{per.get('debut', '?')} → {per.get('fin', '?')}",
                "Transactions": da.fmt(r.get("n_transactions", "—")),
                "Statut": "✅" if not r.get("modeles_ko") else "⚠️ partiel",
            })
        except Exception:
            pass
    return html.Div([
        theme.grid(pd.DataFrame(lignes), height="320px", page_size=10),
        html.P("Pour consulter une période : sélectionner son run dans la barre "
               "latérale, puis naviguer dans les vues.", className="vue-sous"),
    ])
