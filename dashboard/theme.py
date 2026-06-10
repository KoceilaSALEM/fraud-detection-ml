"""
Thème du dashboard — charte Orange.

Identité : noir profond + orange #FF7900 + blanc, typographie Helvetica bold.
Signature visuelle : la tuile KPI carrée au liseré orange, écho du carré du logo.
La couleur saturée est réservée au critique et à la marque ; le contexte
reste en tons neutres (principe : la couleur signale la priorité).
"""
from __future__ import annotations

import streamlit as st

try:
    from src import config as _cfg
    _C = getattr(_cfg, "COULEURS", {})
except Exception:                                    # dashboard autonome
    _C = {}

ORANGE = _C.get("orange", "#FF7900")
BG = _C.get("bg", "#0A0D14")
CARD = _C.get("card", "#111827")
BORDER = _C.get("border", "#1E2540")
CRITIQUE = _C.get("critique", "#EF4444")
ELEVE = _C.get("eleve", "#F59E0B")
MODERE = _C.get("modere", "#3B82F6")
NORMAL = _C.get("normal", "#22C55E")
DIM = _C.get("text_dim", "#6B7A99")

FONT = "'Helvetica Neue', Helvetica, Arial, sans-serif"

CSS = f"""
<style>
  /* ── socle ───────────────────────────────────────────── */
  html, body, [class*="css"] {{ font-family: {FONT}; }}
  .stApp {{ background: {BG}; }}
  section[data-testid="stSidebar"] {{
      background: #000000; border-right: 1px solid {BORDER};
  }}
  section[data-testid="stSidebar"] * {{ color: #FFFFFF; }}
  h1, h2, h3 {{ font-weight: 800; letter-spacing: -0.02em; }}

  /* ── tuile KPI (signature : carré au liseré orange) ───── */
  .kpi {{
      background: {CARD}; border: 1px solid {BORDER};
      border-bottom: 3px solid {ORANGE}; border-radius: 6px;
      padding: 1.05rem 1.15rem .9rem; height: 100%;
  }}
  .kpi .v {{ font-size: 2.1rem; font-weight: 800; color: #FFF;
             line-height: 1.05; letter-spacing: -0.03em; }}
  .kpi .l {{ font-size: .70rem; font-weight: 600; color: {DIM};
             text-transform: uppercase; letter-spacing: .12em; margin-top: .35rem; }}
  .kpi .d {{ font-size: .78rem; color: {DIM}; margin-top: .15rem; }}
  .kpi.crit {{ border-bottom-color: {CRITIQUE}; }}
  .kpi.ok   {{ border-bottom-color: {NORMAL}; }}
  .kpi.warn {{ border-bottom-color: {ELEVE}; }}

  /* ── badges d'état ─────────────────────────────────────── */
  .badge {{ display: inline-block; padding: .22rem .65rem; border-radius: 99px;
            font-size: .72rem; font-weight: 700; letter-spacing: .06em;
            text-transform: uppercase; }}
  .b-ok    {{ background: {NORMAL}22; color: {NORMAL}; border: 1px solid {NORMAL}55; }}
  .b-warn  {{ background: {ELEVE}22; color: {ELEVE}; border: 1px solid {ELEVE}55; }}
  .b-crit  {{ background: {CRITIQUE}22; color: {CRITIQUE}; border: 1px solid {CRITIQUE}55; }}
  .b-info  {{ background: {MODERE}22; color: {MODERE}; border: 1px solid {MODERE}55; }}
  .b-brand {{ background: {ORANGE}22; color: {ORANGE}; border: 1px solid {ORANGE}55; }}

  /* ── en-tête de vue ────────────────────────────────────── */
  .vue-titre {{ font-size: 1.55rem; font-weight: 800; color: #FFF; margin: 0; }}
  .vue-sous  {{ font-size: .85rem; color: {DIM}; margin-top: .15rem; }}
  .sep {{ border: none; border-top: 1px solid {BORDER}; margin: 1rem 0 1.2rem; }}

  /* ── tableaux ──────────────────────────────────────────── */
  [data-testid="stDataFrame"] {{ border: 1px solid {BORDER}; border-radius: 6px; }}

  /* discrétion Streamlit */
  #MainMenu, footer {{ visibility: hidden; }}
</style>
"""


def appliquer_theme() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def kpi(col, valeur, label, detail: str = "", etat: str = "") -> None:
    """Tuile KPI signature. etat : '' | 'ok' | 'warn' | 'crit'."""
    col.markdown(
        f'<div class="kpi {etat}"><div class="v">{valeur}</div>'
        f'<div class="l">{label}</div>'
        + (f'<div class="d">{detail}</div>' if detail else "")
        + "</div>",
        unsafe_allow_html=True,
    )


def badge(texte: str, style: str = "info") -> str:
    return f'<span class="badge b-{style}">{texte}</span>'


def entete_vue(titre: str, sous_titre: str, badges_html: str = "") -> None:
    st.markdown(
        f'<div style="display:flex;justify-content:space-between;align-items:center">'
        f'<div><p class="vue-titre">{titre}</p>'
        f'<p class="vue-sous">{sous_titre}</p></div>'
        f'<div>{badges_html}</div></div><hr class="sep">',
        unsafe_allow_html=True,
    )


def plotly_layout(fig, hauteur: int = 330):
    """Habillage Plotly cohérent avec la charte."""
    fig.update_layout(
        height=hauteur, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, color="#C8D2E8", size=12),
        margin=dict(l=10, r=10, t=36, b=10),
        xaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER),
        yaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor=CARD, font_family=FONT),
    )
    return fig
