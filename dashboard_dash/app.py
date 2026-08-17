"""
Dashboard RA&FM Orange Money — poste de pilotage des 5 modèles ML.
Portage Dash de dashboard/app.py (Streamlit).

Public : analystes fraude & Revenue Assurance (dashboard opérationnel).
Question à laquelle la synthèse répond en 5 secondes :
    « Que dois-je traiter aujourd'hui, et le système est-il sain ? »

Lancement (dev) :
    python app.py
Lancement (prod, ex. Cloud Run) :
    gunicorn --bind :$PORT --workers 2 app:server
"""
from __future__ import annotations

from pathlib import Path

import dash
from dash import Dash, Input, Output, callback, dcc, html

import data_access as da
import theme  # noqa: F401  (déclenche la génération de assets/generated_theme.css)

ROOT = Path(__file__).resolve().parent.parent
LOGO_REL = "logo_orange.png"                          # doit vivre dans /assets

PAGES_ORDRE = [("/", "📊", "Tableau de bord"), ("/donnees", "⚙️", "Données & Inférence")]

app = Dash(
    __name__,
    use_pages=True,
    suppress_callback_exceptions=True,          # nécessaire : plusieurs composants
                                                 # (sélecteur de run, vue M2, boutons
                                                 # d'export...) sont insérés dynamiquement
                                                 # par des callbacks, donc absents du
                                                 # layout initial.
    title="Orange Money — RA&FM",
)
server = app.server                             # utilisé par gunicorn en prod
da.cache.init_app(server)                       # active le cache Flask-Caching (TTL 60 s)


def _nav_links(pathname: str):
    liens = []
    for href, icone, titre in PAGES_ORDRE:
        classes = "nav-link-custom" + (" active" if pathname == href else "")
        liens.append(dcc.Link(f"{icone}  {titre}", href=href, className=classes))
    return liens


def _entete_sidebar():
    logo_path = Path(__file__).resolve().parent / "assets" / LOGO_REL
    enfants = []
    if logo_path.exists():
        enfants.append(html.Img(src=app.get_asset_url(LOGO_REL), style={"width": "110px"}))
    enfants.append(html.Div([
        html.Strong("Orange Money", style={"display": "block", "fontSize": "1rem"}),
        html.Span("RA&FM — Pilotage ML", style={"fontSize": ".82rem", "color": theme.DIM}),
    ], style={"marginTop": ".4rem"}))
    return html.Div(enfants)


app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    dcc.Interval(id="global-poll", interval=15_000, n_intervals=0),
    html.Div(className="app-shell", children=[
        html.Div(className="sidebar", children=[
            html.Div(id="nav-links"),
            html.Hr(),
            _entete_sidebar(),
            html.Div(id="badge-run-en-cours", style={"marginTop": ".5rem"}),
            html.Hr(),
            html.Div(id="sidebar-page-extra"),
        ]),
        html.Div(className="content", children=[dash.page_container]),
    ]),
])


# ── navigation active (équivalent visuel de st.navigation) ──
@callback(Output("nav-links", "children"), Input("url", "pathname"))
def _maj_nav(pathname):
    return _nav_links(pathname)


# ── badge « run en cours » (visible sur toutes les pages) ──
@callback(Output("badge-run-en-cours", "children"), Input("global-poll", "n_intervals"))
def _maj_badge_run_en_cours(_n):
    actifs = da.runs_en_cours()
    if not actifs:
        return None
    return theme.badge(f"run en cours · {actifs[0].get('pct', 0)} %", "brand")


# ── partie du panneau latéral spécifique au Tableau de bord ──
# (sélecteur de run + sélecteur de vue + santé du système) : n'existe que
# lorsqu'on est sur "/" — reproduit le `with st.sidebar:` imbriqué dans
# `page_dashboard()` côté Streamlit, qui n'apparaissait que sur cette page.
@callback(Output("sidebar-page-extra", "children"), Input("url", "pathname"))
def _maj_sidebar_extra(pathname):
    if pathname != "/":
        return None
    runs = da.lister_runs()
    if not runs:
        return None
    options_run = [{"label": da.libelle_run(r), "value": r} for r in runs]
    return html.Div([
        html.Label("Run analysé", className="small"),
        dcc.Dropdown(id="run-selector", options=options_run, value=runs[0], clearable=False),
        html.Div(className="vue-radio", style={"marginTop": ".8rem"}, children=[
            html.Label("Vue", className="small"),
            dcc.RadioItems(
                id="vue-selector",
                options=[{"label": f" {v}", "value": v}
                         for v in ["Synthèse"] + list(da.MODELES.values())],
                value="Synthèse", labelStyle={"display": "block", "marginTop": "4px"},
            ),
        ]),
        html.Hr(),
        html.Div(id="sante-systeme"),
    ])


@callback(Output("sante-systeme", "children"), Input("run-selector", "value"))
def _maj_sante(run_id):
    if not run_id:
        return None
    rapport = da.charger_rapport(run_id)
    ok = rapport.get("modeles_ok", [])
    ko = rapport.get("modeles_ko", [])
    drift_v = (rapport.get("drift") or {}).get("verdict_global", "n/a")
    return html.Div([
        html.Strong("Santé du système", style={"fontSize": ".85rem"}), html.Br(),
        html.Span("Modèles : "),
        theme.badge(f"{len(ok)}/5 OK", "ok" if not ko else "crit"), html.Br(),
        html.Span("Drift : ", style={"marginTop": "4px", "display": "inline-block"}),
        theme.badge(drift_v, {"stable": "ok", "ATTENTION": "warn"}.get(drift_v, "crit")
                    if drift_v != "n/a" else "info"),
    ])


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8502)
