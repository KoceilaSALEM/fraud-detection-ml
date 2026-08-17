"""Thème clair et accessible du dashboard Sentinelle.

La palette conserve l'orange officiel comme signature de marque, mais réserve
les couleurs saturées aux actions, aux états et aux niveaux de risque. Les
surfaces de travail restent neutres et claires pour faciliter la lecture
prolongée des tableaux et des graphiques.
"""
from __future__ import annotations

from pathlib import Path

from dash import html

try:
    from src import config as _cfg
    _C = getattr(_cfg, "COULEURS", {})
except Exception:
    _C = {}

ORANGE = _C.get("orange", "#FF7900")
BRAND_TEXT = _C.get("orange_text", "#8A3500")
BG = _C.get("bg", "#F6F7F9")
CARD = _C.get("card", "#FFFFFF")
BORDER = _C.get("border", "#D9DEE7")
TEXT = _C.get("text", "#17212B")
DIM = _C.get("text_dim", "#5D6775")

CRITIQUE = _C.get("critique", "#B42318")
ELEVE = _C.get("eleve", "#8A4B08")
MODERE = _C.get("modere", "#175CD3")
NORMAL = _C.get("normal", "#067647")

FONT = "Inter, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"


CSS = f"""
:root {{
  --orange: {ORANGE}; --orange-text: {BRAND_TEXT};
  --bg: {BG}; --card: {CARD}; --border: {BORDER};
  --text: {TEXT}; --dim: {DIM};
  --critique: {CRITIQUE}; --eleve: {ELEVE};
  --modere: {MODERE}; --normal: {NORMAL};
  --shadow-sm: 0 1px 2px rgba(16, 24, 40, .05);
  --shadow-md: 0 8px 24px rgba(16, 24, 40, .07);
}}

* {{ box-sizing: border-box; }}
html, body {{
  background: {BG}; color: {TEXT}; font-family: {FONT}; margin: 0;
  font-size: 15px; line-height: 1.5;
}}
body {{ min-width: 320px; }}
h1, h2, h3, h4, h5, h6 {{
  color: {TEXT}; font-weight: 700; letter-spacing: -.015em;
}}
p, label, span {{ color: inherit; }}
a {{ color: {BRAND_TEXT}; }}
a:hover {{ color: #642700; }}

.app-shell {{ display: flex; min-height: 100vh; }}
.sidebar {{
  width: 280px; flex-shrink: 0; background: {CARD}; color: {TEXT};
  border-right: 1px solid {BORDER}; padding: 1.35rem 1rem;
  box-shadow: 2px 0 12px rgba(16, 24, 40, .025);
}}
.sidebar * {{ color: inherit; }}
.sidebar hr, .sep {{ border: 0; border-top: 1px solid {BORDER}; }}
.sidebar hr {{ margin: 1.1rem 0; }}
.content {{
  flex: 1; min-width: 0; max-width: 100%; overflow-x: hidden;
  padding: 2rem clamp(1.25rem, 3vw, 3rem) 3rem;
}}

.nav-link-custom {{
  display: flex; align-items: center; min-height: 42px;
  padding: .6rem .75rem; margin-bottom: .25rem;
  border-left: 3px solid transparent; border-radius: 7px;
  color: #344054 !important; text-decoration: none;
  font-size: .9rem; font-weight: 600;
  transition: background-color .15s ease, color .15s ease;
}}
.nav-link-custom:hover {{ background: #F2F4F7; color: {TEXT} !important; }}
.nav-link-custom.active {{
  background: #FFF1E6; border-left-color: {ORANGE};
  color: {BRAND_TEXT} !important;
}}

.small {{ color: {DIM}; font-weight: 600; }}
.vue-radio .form-check {{ margin-bottom: .2rem; }}
.vue-radio label {{ color: #344054 !important; font-size: .86rem; }}
input[type="radio"], input[type="checkbox"] {{ accent-color: {ORANGE}; }}
.Select-control, .Select-menu-outer {{
  background: {CARD} !important; border-color: {BORDER} !important;
  color: {TEXT} !important;
}}
.Select-control:hover {{ border-color: #98A2B3 !important; }}
.Select-value-label, .Select-placeholder, .Select-input > input {{ color: {TEXT} !important; }}
.Select-menu-outer {{ box-shadow: var(--shadow-md); }}
.upload-zone {{
  border: 1px dashed #98A2B3; border-radius: 10px; padding: 1.6rem;
  background: {CARD}; color: #344054; text-align: center; cursor: pointer;
  transition: border-color .15s ease, background-color .15s ease;
}}
.upload-zone:hover {{ border-color: {ORANGE}; background: #FFFAF5; }}
.btn-primary-custom {{
  background: {ORANGE}; border: 1px solid {ORANGE}; color: #000;
  border-radius: 8px; padding: .65rem 1.15rem; font-weight: 700;
  cursor: pointer; box-shadow: var(--shadow-sm);
}}
.btn-primary-custom:hover {{ background: #E86E00; border-color: #E86E00; }}
.btn-primary-custom:disabled {{ opacity: .48; cursor: not-allowed; }}
.btn-export {{
  margin-top: 8px; padding: .45rem .85rem; border-radius: 8px;
  background: {CARD}; border: 1px solid #C5CAD3; color: #344054;
  font-size: .82rem; font-weight: 600; cursor: pointer;
}}
.btn-export:hover {{ border-color: {ORANGE}; color: {BRAND_TEXT}; background: #FFF7F0; }}

.kpi-row {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 1rem; margin-bottom: 1rem;
}}
.kpi {{
  height: 100%; min-height: 126px; padding: 1.1rem 1.15rem;
  background: {CARD}; border: 1px solid {BORDER}; border-top: 3px solid {ORANGE};
  border-radius: 10px; box-shadow: var(--shadow-sm);
}}
.kpi .v {{
  color: {TEXT}; font-size: 2rem; font-weight: 750;
  line-height: 1.1; letter-spacing: -.035em;
}}
.kpi .l {{
  margin-top: .45rem; color: {DIM}; font-size: .72rem; font-weight: 700;
  letter-spacing: .08em; text-transform: uppercase;
}}
.kpi .d {{ margin-top: .2rem; color: {DIM}; font-size: .79rem; }}
.kpi.crit {{ border-top-color: {CRITIQUE}; }}
.kpi.ok {{ border-top-color: {NORMAL}; }}
.kpi.warn {{ border-top-color: {ELEVE}; }}
.metric-mini-row {{ display: flex; flex-wrap: wrap; gap: 2.2rem; margin: .5rem 0 1rem; }}
.metric-mini .v {{ color: {TEXT}; font-size: 1.55rem; font-weight: 750; }}
.metric-mini .l {{ margin-top: .1rem; color: {DIM}; font-size: .76rem; }}

.badge {{
  display: inline-block; padding: .24rem .62rem; border-radius: 999px;
  font-size: .7rem; font-weight: 700; letter-spacing: .045em;
  text-transform: uppercase;
}}
.b-ok {{ background: #ECFDF3; color: {NORMAL}; border: 1px solid #ABEFC6; }}
.b-warn {{ background: #FFFAEB; color: {ELEVE}; border: 1px solid #FEDF89; }}
.b-crit {{ background: #FEF3F2; color: {CRITIQUE}; border: 1px solid #FECDCA; }}
.b-info {{ background: #EFF8FF; color: {MODERE}; border: 1px solid #B2DDFF; }}
.b-brand {{ background: #FFF1E6; color: {BRAND_TEXT}; border: 1px solid #FFD1AD; }}

.vue-titre {{ margin: 0; color: {TEXT}; font-size: 1.65rem; font-weight: 750; }}
.vue-sous {{ margin-top: .2rem; color: {DIM}; font-size: .86rem; }}
.sep {{ margin: 1.1rem 0 1.3rem; }}
.vide {{
  padding: 1.5rem; border: 1px dashed #B8C0CC; border-radius: 10px;
  background: #FAFBFC; color: {DIM}; text-align: center;
}}

.ag-theme-alpine {{
  --ag-font-family: {FONT}; --ag-font-size: 13px;
  --ag-background-color: {CARD}; --ag-foreground-color: #344054;
  --ag-header-background-color: #F2F4F7; --ag-header-foreground-color: {TEXT};
  --ag-odd-row-background-color: #FAFBFC; --ag-row-hover-color: #FFF7F0;
  --ag-selected-row-background-color: #FFF1E6; --ag-border-color: {BORDER};
  --ag-secondary-border-color: #EAECF0; --ag-input-border-color: #C5CAD3;
  --ag-accent-color: {ORANGE}; border-radius: 10px; overflow: hidden;
}}

.dash-tabs .tab {{
  background: #F2F4F7 !important; color: {DIM} !important;
  border: 1px solid {BORDER} !important; padding: .7rem !important;
}}
.dash-tabs .tab--selected {{
  background: {CARD} !important; color: {BRAND_TEXT} !important;
  border-top: 2px solid {ORANGE} !important; font-weight: 700;
}}

.js-plotly-plot, iframe {{ border-radius: 10px; }}
iframe {{ background: {CARD}; border: 1px solid {BORDER} !important; }}

::-webkit-scrollbar {{ width: 10px; height: 10px; }}
::-webkit-scrollbar-track {{ background: {BG}; }}
::-webkit-scrollbar-thumb {{ background: #C5CAD3; border-radius: 999px; border: 2px solid {BG}; }}

@media (max-width: 800px) {{
  .app-shell {{ display: block; }}
  .sidebar {{ width: 100%; border-right: 0; border-bottom: 1px solid {BORDER}; }}
  .content {{ padding: 1.25rem 1rem 2rem; }}
  .kpi-row {{ grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }}
}}
"""

_ASSETS_DIR = Path(__file__).resolve().parent / "assets"
_ASSETS_DIR.mkdir(exist_ok=True)
(_ASSETS_DIR / "generated_theme.css").write_text(CSS, encoding="utf-8")


def kpi(valeur, label: str, detail: str = "", etat: str = ""):
    """Renvoie une carte KPI. ``etat`` : '', 'ok', 'warn' ou 'crit'."""
    enfants = [html.Div(str(valeur), className="v"), html.Div(label, className="l")]
    if detail:
        enfants.append(html.Div(detail, className="d"))
    classes = "kpi" + (f" {etat}" if etat else "")
    return html.Div(enfants, className=classes)


def kpi_row(*tuiles):
    return html.Div(list(tuiles), className="kpi-row")


def metric_mini(valeur, label: str):
    return html.Div([html.Div(str(valeur), className="v"),
                     html.Div(label, className="l")], className="metric-mini")


def metric_row(*metriques):
    return html.Div(list(metriques), className="metric-mini-row")


def badge(texte: str, style: str = "info"):
    return html.Span(texte, className=f"badge b-{style}")


def entete_vue(titre: str, sous_titre: str, badges=None):
    badges = badges or []
    if not isinstance(badges, list):
        badges = [badges]
    return html.Div([
        html.Div([
            html.Div([html.P(titre, className="vue-titre"),
                      html.P(sous_titre, className="vue-sous")]),
            html.Div(badges, style={"display": "flex", "gap": "6px",
                                     "alignItems": "center", "flexWrap": "wrap"}),
        ], style={"display": "flex", "justifyContent": "space-between",
                   "alignItems": "center", "flexWrap": "wrap", "gap": "8px"}),
        html.Hr(className="sep"),
    ])


def vide(message: str):
    return html.Div(message, className="vide")


def grid(df, height: str = "420px", page_size: int = 20):
    """Tableau interactif AG Grid adapté au thème clair."""
    import dash_ag_grid as dag

    if df is None or not len(df):
        return vide("Aucune donnée.")
    return dag.AgGrid(
        rowData=df.to_dict("records"),
        columnDefs=[{"field": c, "sortable": True, "filter": True} for c in df.columns],
        className="ag-theme-alpine",
        columnSize="responsiveSizeToFit",
        dashGridOptions={"pagination": True, "paginationPageSize": page_size},
        style={"height": height},
    )


def plotly_layout(fig, hauteur: int = 330):
    """Applique aux figures Plotly la palette claire du dashboard."""
    fig.update_layout(
        height=hauteur,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, color="#344054", size=12),
        margin=dict(l=10, r=10, t=36, b=10),
        xaxis=dict(gridcolor="#EAECF0", zerolinecolor=BORDER, linecolor=BORDER),
        yaxis=dict(gridcolor="#EAECF0", zerolinecolor=BORDER, linecolor=BORDER),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor=CARD, bordercolor=BORDER, font_family=FONT,
                        font_color=TEXT),
        colorway=[ORANGE, MODERE, NORMAL, ELEVE, CRITIQUE, "#7F56D9", "#0E9384"],
    )
    return fig
