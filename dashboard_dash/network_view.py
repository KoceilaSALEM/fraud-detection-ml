"""
Vue réseau M2 (réseaux de mules) — portage Dash de dashboard/network_view.py.

Différence structurelle majeure avec Streamlit
------------------------------------------------
En Streamlit, `render_network_intelligence()` était appelée à chaque script-run
et faisait tout en une passe : définir les widgets, lire leur valeur, recalculer,
afficher — Streamlit relance le script du haut vers le bas à chaque interaction.

Dash fonctionne par callbacks explicites (Input → Output), déclarés une seule
fois au démarrage de l'app. Ce module expose donc :

  - `m2_layout(id_prefix)`      : la coquille statique (KPIs, sélecteurs, onglets
                                   vides) à insérer dans la page.
  - `register_m2_callbacks(app)`: les callbacks qui remplissent cette coquille.

Le chargement des données (`load_m2`), la résolution défensive des colonnes,
la construction du sous-graphe (`_subgraph_frames`) et la génération HTML pyvis
(`build_pyvis_html`) sont des fonctions pures, inchangées vs la version
Streamlit — seules les fonctions de rendu (qui appelaient st.*) ont été
converties en composants Dash.

Rendu de l'arbre Graphviz : Streamlit (`st.graphviz_chart`) délègue le rendu du
DOT au navigateur (aucune dépendance système). On reproduit ce comportement en
Dash avec un `html.Iframe` chargeant `d3-graphviz` depuis un CDN — donc toujours
aucune dépendance serveur (pas besoin d'installer le paquet système `graphviz`),
mais le navigateur de l'analyste doit pouvoir atteindre le CDN (voir README).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
from dash import Input, Output, State, callback, dcc, html
import dash_ag_grid as dag

from data_access import cache
import theme

# ─────────────────────────────────────────────────────────────────────────
#  Palette du graphe, optimisée pour le fond clair
# ─────────────────────────────────────────────────────────────────────────
ORANGE = theme.ORANGE
GRAPH_BG = "#FFFFFF"
GRAPH_TEXT = "#17212B"
GRAPH_EDGE = "#98A2B3"

COLOR_CRITIQUE = "#F97066"
COLOR_ELEVE = "#FDB022"
COLOR_MODERE = "#53B1FD"
COLOR_FAIBLE = "#98A2B3"
COLOR_EXTERNE = "#D0D5DD"

_SRC_CANDIDATES = ["source", "src", "sender", "SENDER", "SENDER_ID", "from",
                   "emetteur", "EMETTEUR", "payer", "node_from", "u", "start"]
_DST_CANDIDATES = ["target", "dst", "receiver", "RECEIVER", "RECEIVER_ID", "to",
                   "destinataire", "DESTINATAIRE", "payee", "node_to", "v", "end"]
_AMT_CANDIDATES = ["montant", "amount", "MONTANT", "AMOUNT", "montant_total",
                   "sum_montant", "poids", "weight_montant", "value"]
_CNT_CANDIDATES = ["count", "nb", "n", "nb_tx", "transactions", "freq",
                   "weight", "poids", "n_tx"]


def _resolve_col(cols, candidates):
    lower = {c.lower(): c for c in cols}
    for cand in candidates:
        if cand in cols:
            return cand
        if cand.lower() in lower:
            return lower[cand.lower()]
    return None


def _first_existing(directory: Path, candidates):
    for name in candidates:
        p = directory / name
        if p.exists():
            return p
    return None


# ─────────────────────────────────────────────────────────────────────────
#  Chargement des exports M2 (mis en cache — Flask-Caching, TTL 60 s)
# ─────────────────────────────────────────────────────────────────────────
@cache.memoize(timeout=60)
def load_m2(outputs_dir: str):
    """Charge scored + edges. Renvoie (scored, edges, meta). Inchangé vs Streamlit."""
    outputs_dir = Path(outputs_dir)

    scored_path = _first_existing(
        outputs_dir, ["scored_v2.parquet", "scored.parquet", "scored_mules.parquet"])
    edges_path = _first_existing(
        outputs_dir, ["edges_graph.parquet", "edges.parquet", "edges_transit.parquet"])

    if scored_path is None:
        return None, None, {"error":
            f"Aucun fichier de comptes scorés trouvé dans {outputs_dir} "
            "(cherché : scored_v2.parquet, scored.parquet)."}
    if edges_path is None:
        return None, None, {"error":
            f"Aucun fichier d'arêtes trouvé dans {outputs_dir} "
            "(cherché : edges_graph.parquet, edges.parquet)."}

    scored = pd.read_parquet(scored_path)
    edges = pd.read_parquet(edges_path)

    if "node" not in scored.columns:
        return None, None, {"error": "Colonne 'node' absente de scored.parquet"}

    src = _resolve_col(edges.columns, _SRC_CANDIDATES)
    dst = _resolve_col(edges.columns, _DST_CANDIDATES)
    amt = _resolve_col(edges.columns, _AMT_CANDIDATES)
    cnt = _resolve_col(edges.columns, _CNT_CANDIDATES)

    meta = {
        "src": src, "dst": dst, "amt": amt, "cnt": cnt,
        "edge_cols": list(edges.columns), "scored_cols": list(scored.columns),
        "scored_file": scored_path.name, "edges_file": edges_path.name, "error": None,
    }
    if src is None or dst is None:
        meta["error"] = (
            "Impossible d'identifier les colonnes source/destination dans "
            f"edges.parquet. Colonnes présentes : {list(edges.columns)}")

    scored = scored.copy()
    scored["node"] = scored["node"].astype(str)
    if src and dst:
        edges = edges.copy()
        edges[src] = edges[src].astype(str)
        edges[dst] = edges[dst].astype(str)

    return scored, edges, meta


# ─────────────────────────────────────────────────────────────────────────
#  Helpers de formatage / style (purs — inchangés vs Streamlit)
# ─────────────────────────────────────────────────────────────────────────
def _node_color(risk_level, risk_score):
    lvl = str(risk_level).upper() if risk_level is not None else ""
    if "CRITIQUE" in lvl:
        return COLOR_CRITIQUE
    if "ÉLEV" in lvl or "ELEV" in lvl or "HIGH" in lvl:
        return COLOR_ELEVE
    if "MODÉR" in lvl or "MODER" in lvl or "MEDIUM" in lvl:
        return COLOR_MODERE
    if "FAIBLE" in lvl or "LOW" in lvl:
        return COLOR_FAIBLE
    try:
        s = float(risk_score)
        if s >= 85: return COLOR_CRITIQUE
        if s >= 70: return COLOR_ELEVE
        if s >= 50: return COLOR_MODERE
        return COLOR_FAIBLE
    except (TypeError, ValueError):
        return COLOR_FAIBLE


def _fmt_mga(x):
    try:
        return f"{float(x):,.0f} Ar".replace(",", " ")
    except (TypeError, ValueError):
        return "—"


def _node_tooltip(row):
    def g(col, default="—"):
        v = row.get(col, default)
        return default if pd.isna(v) else v

    lines = [f"<b>ID {g('node')}</b>"]
    if "RISK_SCORE" in row:
        lines.append(f"Risque : <b>{g('RISK_SCORE')}</b> ({g('RISK_LEVEL')})")
    if "in_degree" in row or "out_degree" in row:
        lines.append(f"Entrant : {g('in_degree')} — Sortant : {g('out_degree')}")
    if "in_montant" in row or "out_montant" in row:
        lines.append(f"Reçu : {_fmt_mga(g('in_montant'))}")
        lines.append(f"Envoyé : {_fmt_mga(g('out_montant'))}")
    if "ratio_transit" in row:
        try:
            lines.append(f"Ratio transit : {float(g('ratio_transit')):.2f}")
        except (TypeError, ValueError):
            pass
    if "pagerank" in row:
        try:
            lines.append(f"PageRank : {float(g('pagerank')):.4f}")
        except (TypeError, ValueError):
            pass
    return "<br>".join(str(x) for x in lines)


# ─────────────────────────────────────────────────────────────────────────
#  Construction du sous-graphe pour un cluster donné (pur — inchangé)
# ─────────────────────────────────────────────────────────────────────────
def _subgraph_frames(scored, edges, meta, cluster_id, include_external, max_nodes):
    src, dst = meta["src"], meta["dst"]
    amt, cnt = meta["amt"], meta["cnt"]

    core_ids = set(scored.loc[scored["cluster"] == cluster_id, "node"])

    if include_external:
        mask = edges[src].isin(core_ids) | edges[dst].isin(core_ids)
    else:
        mask = edges[src].isin(core_ids) & edges[dst].isin(core_ids)
    e = edges.loc[mask].copy()

    involved = set(e[src]) | set(e[dst]) | core_ids

    truncated = False
    if len(involved) > max_nodes:
        truncated = True
        core_scored = scored[scored["node"].isin(core_ids)].copy()
        if "RISK_SCORE" in core_scored.columns:
            core_scored = core_scored.sort_values("RISK_SCORE", ascending=False)
        keep = list(core_scored["node"].head(max_nodes))
        keep_set = set(keep)
        if include_external and len(keep_set) < max_nodes:
            deg = pd.concat([e[src], e[dst]]).value_counts()
            for nid in deg.index:
                if nid not in keep_set:
                    keep_set.add(nid)
                    if len(keep_set) >= max_nodes:
                        break
        involved = keep_set
        e = e[e[src].isin(involved) & e[dst].isin(involved)].copy()

    nodes_df = scored[scored["node"].isin(involved)].copy()
    known = set(nodes_df["node"])
    externals = [n for n in involved if n not in known]
    if externals:
        ext_df = pd.DataFrame({"node": externals})
        ext_df["_external"] = True
        nodes_df["_external"] = False
        nodes_df = pd.concat([nodes_df, ext_df], ignore_index=True)
    else:
        nodes_df["_external"] = False

    e = e.rename(columns={src: "_src", dst: "_dst"})
    e["_amt"] = e[amt] if amt else 0
    e["_cnt"] = e[cnt] if cnt else 1

    return nodes_df.reset_index(drop=True), e.reset_index(drop=True), truncated


# ─────────────────────────────────────────────────────────────────────────
#  Vue 1 — Graphe interactif (pyvis) — pur, inchangé vs Streamlit
# ─────────────────────────────────────────────────────────────────────────
def build_pyvis_html(nodes_df, edges_df, height_px=650):
    from pyvis.network import Network

    net = Network(height=f"{height_px}px", width="100%", directed=True,
                  bgcolor=GRAPH_BG, font_color=GRAPH_TEXT, notebook=False,
                  cdn_resources="in_line")

    deg = pd.concat([edges_df["_src"], edges_df["_dst"]]).value_counts().to_dict()

    for _, r in nodes_df.iterrows():
        nid = str(r["node"])
        d = deg.get(nid, 1)
        size = 12 + min(d, 40) * 1.4
        if r.get("_external", False):
            color = COLOR_EXTERNE
            title = f"<b>ID {nid}</b><br>Contrepartie externe au réseau"
        else:
            color = _node_color(r.get("RISK_LEVEL"), r.get("RISK_SCORE"))
            title = _node_tooltip(r)
        net.add_node(nid, label=nid, title=title, color=color, size=size,
                     borderWidth=2, borderWidthSelected=4,
                     font={"color": GRAPH_TEXT, "size": 13, "face": "Segoe UI"})

    amax = edges_df["_amt"].astype(float).max() if len(edges_df) else 0
    for _, e in edges_df.iterrows():
        try:
            a = float(e["_amt"])
        except (TypeError, ValueError):
            a = 0.0
        width = 1.0
        if amax and a > 0:
            width = 1.0 + 5.0 * (math.log1p(a) / math.log1p(amax))
        label_amt = _fmt_mga(a) if a > 0 else ""
        net.add_edge(str(e["_src"]), str(e["_dst"]), value=width,
                     title=label_amt, color=GRAPH_EDGE)

    options = {
        "nodes": {"shape": "dot", "borderWidth": 2},
        "edges": {"arrows": {"to": {"enabled": True, "scaleFactor": 0.7}},
                  "color": {"color": GRAPH_EDGE, "highlight": ORANGE, "hover": ORANGE},
                  "smooth": {"type": "dynamic"}},
        "physics": {"barnesHut": {"gravitationalConstant": -12000, "springLength": 130,
                                   "springConstant": 0.04, "damping": 0.09},
                    "stabilization": {"iterations": 180, "fit": True},
                    "minVelocity": 0.5},
        "interaction": {"hover": True, "tooltipDelay": 100, "navigationButtons": True,
                        "keyboard": True, "multiselect": True},
    }
    net.set_options(json.dumps(options))

    try:
        return net.generate_html(notebook=False)
    except TypeError:
        return net.generate_html()


# ─────────────────────────────────────────────────────────────────────────
#  Vue 2 — Arbre hiérarchique (DOT, rendu client via d3-graphviz)
# ─────────────────────────────────────────────────────────────────────────
def build_graphviz_dot(nodes_df, edges_df, show_amounts=True):
    """Construit une chaîne DOT — logique inchangée vs Streamlit."""
    info = {str(r["node"]): r for _, r in nodes_df.iterrows()}

    lines = [
        "digraph reseau {",
        "  rankdir=LR;",
        '  bgcolor="transparent";',
        '  node [style="filled", fontname="Segoe UI", fontcolor="#17212B", '
        'color="#475467", penwidth=1.5];',
        '  edge [color="#98A2B3", fontname="Segoe UI", fontcolor="#5D6775", '
        'fontsize=9, penwidth=1.2];',
    ]
    for nid, r in info.items():
        if r.get("_external", False):
            fill, lbl = COLOR_EXTERNE, nid
        else:
            fill = _node_color(r.get("RISK_LEVEL"), r.get("RISK_SCORE"))
            score = r.get("RISK_SCORE", "")
            lbl = f"{nid}\\n({score})" if str(score) not in ("", "nan") else nid
        lines.append(f'  "{nid}" [fillcolor="{fill}", label="{lbl}"];')

    for _, e in edges_df.iterrows():
        s, d = str(e["_src"]), str(e["_dst"])
        if show_amounts and float(e.get("_amt", 0) or 0) > 0:
            lines.append(f'  "{s}" -> "{d}" [label="{_fmt_mga(e["_amt"])}"];')
        else:
            lines.append(f'  "{s}" -> "{d}";')
    lines.append("}")
    return "\n".join(lines)


def build_graphviz_iframe_srcdoc(dot_string: str) -> str:
    """
    Page HTML autonome qui rend un DOT côté navigateur via d3-graphviz —
    équivalent de st.graphviz_chart (aucune dépendance système, pas besoin
    d'installer le paquet `graphviz` sur la VM). Requiert un accès du
    navigateur de l'analyste aux CDN listés (voir README).
    """
    dot_js = json.dumps(dot_string)  # échappement sûr pour insertion dans <script>
    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<style>
  html,body {{ margin:0; background:#FFFFFF; color:#17212B; }}
  #graph {{ width:100%; height:100%; }}
  #graph svg {{ width:100%; height:100%; }}
</style>
</head>
<body>
<div id="graph">Chargement de l'arbre…</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@hpcc-js/wasm@2.15.3/dist/index.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/d3-graphviz@5.0.2/build/d3-graphviz.min.js"></script>
<script>
  const dot = {dot_js};
  d3.select("#graph").graphviz().renderDot(dot);
</script>
</body></html>"""


# ─────────────────────────────────────────────────────────────────────────
#  Légende
# ─────────────────────────────────────────────────────────────────────────
def _legend():
    def item(color, label):
        return html.Span([
            html.Span("●", style={"color": color, "marginRight": "4px"}), label,
        ], style={"marginRight": "18px"})

    return html.Div([
        item(COLOR_CRITIQUE, "Critique"), item(COLOR_ELEVE, "Élevé"),
        item(COLOR_MODERE, "Modéré"), item(COLOR_FAIBLE, "Faible"),
        item(COLOR_EXTERNE, "Contrepartie externe"),
        html.Span("→ sens du transfert  ·  épaisseur ∝ montant"),
    ], style={"display": "flex", "flexWrap": "wrap", "fontSize": "0.82rem",
              "color": theme.DIM, "margin": "4px 0 10px 0"})


# ─────────────────────────────────────────────────────────────────────────
#  Coquille de layout — à insérer dans la page (remplace render_network_intelligence)
# ─────────────────────────────────────────────────────────────────────────
def m2_layout(id_prefix: str = "m2net", outputs_dir: str | None = None):
    """
    outputs_dir : chemin déjà connu au moment de la construction de la vue
    (ex. str(ROOT / "outputs" / "M2_mules")). On le fixe directement comme
    valeur initiale du Store plutôt que de le pousser depuis un callback
    externe : un Output ciblant un composant qui n'existe pas encore dans le
    DOM (cas des autres vues, où ce Store n'est pas monté) fait planter le
    moteur client Dash, même avec `dash.no_update` — voir la note dans
    pages/tableau_de_bord.py::vue_m2.
    """
    p = id_prefix
    return html.Div([
        html.H5("Réseaux de mules — exploration du graphe"),
        dcc.Store(id=f"{p}-outputs-dir", data=outputs_dir),
        html.Div(id=f"{p}-error"),
        html.Div(id=f"{p}-kpis"),

        html.Div([
            html.Div([
                html.Label("Réseau à explorer", className="small"),
                dcc.Dropdown(id=f"{p}-cluster", clearable=False),
            ], style={"flex": "3", "minWidth": "320px"}),
            html.Div([
                dcc.Checklist(
                    id=f"{p}-ext",
                    options=[{"label": " Inclure les contreparties externes (1 saut)",
                              "value": "ext"}],
                    value=[],
                ),
            ], style={"flex": "3", "minWidth": "280px", "alignSelf": "flex-end",
                      "paddingBottom": "8px"}),
            html.Div([
                html.Label("Nœuds max affichés", className="small"),
                dcc.Slider(id=f"{p}-maxnodes", min=20, max=400, step=20, value=120,
                           marks=None, tooltip={"placement": "bottom"}),
            ], style={"flex": "2", "minWidth": "220px"}),
        ], style={"display": "flex", "gap": "1.5rem", "flexWrap": "wrap",
                  "margin": "0.8rem 0"}),

        html.Div(id=f"{p}-legend"),
        html.Div(id=f"{p}-info"),

        dcc.Tabs(id=f"{p}-tabs", value="graph", className="dash-tabs", children=[
            dcc.Tab(label="Graphe interactif", value="graph"),
            dcc.Tab(label="Vue arbre", value="tree"),
            dcc.Tab(label="Comptes du réseau", value="data"),
        ]),
        html.Div(id=f"{p}-tab-content", style={"marginTop": "0.8rem"}),
    ])


# ─────────────────────────────────────────────────────────────────────────
#  Callbacks — enregistrés une seule fois à l'import du module (voir la ligne
#  `nv.register_m2_callbacks()` en bas de pages/tableau_de_bord.py). On utilise
#  le décorateur global `dash.callback` (et non `app.callback`) : cela permet
#  d'enregistrer les callbacks depuis un module de page sans dépendre de
#  l'ordre de création de l'objet `app` (pattern standard des apps Dash
#  multipages, cf. https://dash.plotly.com/sharing-data-between-callbacks).
# ─────────────────────────────────────────────────────────────────────────
_REGISTERED_PREFIXES: set[str] = set()


def register_m2_callbacks(id_prefix: str = "m2net"):
    if id_prefix in _REGISTERED_PREFIXES:
        return                                        # évite le double-enregistrement
    _REGISTERED_PREFIXES.add(id_prefix)
    p = id_prefix

    @callback(
        Output(f"{p}-cluster", "options"),
        Output(f"{p}-cluster", "value"),
        Output(f"{p}-kpis", "children"),
        Output(f"{p}-error", "children"),
        Output(f"{p}-legend", "children"),
        Input(f"{p}-outputs-dir", "data"),
    )
    def _maj_selecteur(outputs_dir):
        if not outputs_dir:
            return [], None, None, None, None

        scored, edges, meta = load_m2(outputs_dir)
        if meta.get("error"):
            return [], None, None, theme.vide(meta["error"]), None

        n_clusters = int(scored.loc[scored["cluster"] >= 0, "cluster"].nunique())
        n_transit = len(scored)
        n_alertes = int((scored.get("RISK_SCORE", pd.Series(dtype=float)) >= 70).sum())
        kpis = theme.metric_row(
            theme.metric_mini(n_clusters, "Réseaux organisés"),
            theme.metric_mini(f"{n_transit:,}".replace(",", " "), "Comptes de transit"),
            theme.metric_mini(f"{n_alertes:,}".replace(",", " "), "Alertes (score ≥ 70)"),
        )

        clusters = (scored[scored["cluster"] >= 0].groupby("cluster")
                    .agg(taille=("node", "size"),
                         risque_moyen=("RISK_SCORE", "mean")
                         if "RISK_SCORE" in scored.columns else ("node", "size"))
                    .sort_values("risque_moyen", ascending=False))

        if clusters.empty:
            return [], None, kpis, theme.vide(
                "Aucun réseau organisé (cluster ≥ 0) dans scored.parquet."), _legend()

        options = []
        for cid, row in clusters.iterrows():
            rm = row["risque_moyen"]
            rm_s = f"{rm:.0f}" if pd.notna(rm) else "—"
            options.append({"label": f"Réseau #{cid} — {int(row['taille'])} comptes "
                                      f"— risque moyen {rm_s}", "value": cid})
        return options, options[0]["value"], kpis, None, _legend()

    @callback(
        Output(f"{p}-tab-content", "children"),
        Output(f"{p}-info", "children"),
        Input(f"{p}-cluster", "value"),
        Input(f"{p}-ext", "value"),
        Input(f"{p}-maxnodes", "value"),
        Input(f"{p}-tabs", "value"),
        State(f"{p}-outputs-dir", "data"),
        prevent_initial_call=True,
    )
    def _maj_contenu(cluster_id, ext_val, max_nodes, tab, outputs_dir):
        if not outputs_dir or cluster_id is None:
            return None, None

        scored, edges, meta = load_m2(outputs_dir)
        if meta.get("error"):
            return None, None

        include_external = "ext" in (ext_val or [])
        nodes_df, edges_df, truncated = _subgraph_frames(
            scored, edges, meta, cluster_id, include_external, max_nodes or 120)

        info = None
        if truncated:
            info = theme.vide(
                f"Réseau volumineux : affichage limité aux {max_nodes} comptes les "
                "plus risqués. Augmentez le curseur ou décochez les externes pour "
                "réduire la densité.")
        if edges_df.empty:
            return theme.vide("Aucune arête à afficher pour ce réseau avec ces "
                               "filtres."), info

        if tab == "graph":
            html_str = build_pyvis_html(nodes_df, edges_df, height_px=660)
            content = html.Div([
                html.Iframe(srcDoc=html_str, style={"width": "100%", "height": "680px",
                                                      "border": "none"}),
                html.P(f"{len(nodes_df)} nœuds · {len(edges_df)} liens · glissez pour "
                       "déplacer, molette pour zoomer, survolez un nœud pour le "
                       "détail, cliquez pour isoler ses connexions.",
                       className="vue-sous"),
            ])
            return content, info

        if tab == "tree":
            show_amounts = len(edges_df) <= 40
            dot = build_graphviz_dot(nodes_df, edges_df, show_amounts=show_amounts)
            note = None
            if len(edges_df) > 120:
                note = theme.vide(
                    "Beaucoup d'arêtes : la vue arbre reste lisible mais dense. "
                    "Elle est surtout pertinente pour les petits réseaux (source → "
                    "relais → destination).")
            content = html.Div([
                note,
                html.Iframe(srcDoc=build_graphviz_iframe_srcdoc(dot),
                            style={"width": "100%", "height": "600px", "border": "none"}),
            ])
            return content, info

        # tab == "data"
        display = nodes_df[nodes_df.get("_external", False) == False].copy()
        cols_pref = [c for c in ["node", "RISK_SCORE", "RISK_LEVEL", "in_degree",
                                  "out_degree", "in_montant", "out_montant",
                                  "ratio_transit", "pagerank", "diversite"]
                     if c in display.columns]
        if "RISK_SCORE" in display.columns:
            display = display.sort_values("RISK_SCORE", ascending=False)
        cols = cols_pref if cols_pref else list(display.columns)
        grid = dag.AgGrid(
            id=f"{p}-grid",
            rowData=display[cols].to_dict("records"),
            columnDefs=[{"field": c, "sortable": True, "filter": True} for c in cols],
            className="ag-theme-alpine",
            columnSize="responsiveSizeToFit",
            dashGridOptions={"pagination": True, "paginationPageSize": 20},
            style={"height": "500px"},
        )
        return html.Div([
            html.P("Recherche disponible directement dans l'en-tête de la colonne "
                   "« node » (filtre AG Grid).", className="vue-sous"),
            grid,
        ]), info
