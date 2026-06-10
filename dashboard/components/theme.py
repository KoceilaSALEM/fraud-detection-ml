"""
theme.py — Thème CSS centralisé Orange Money
=============================================
Importé par toutes les pages du dashboard pour éviter la duplication.

Usage :
    from components.theme import inject_css, COULEURS
    inject_css()  # en haut de chaque page Streamlit
"""
# TODO: déplacer ici le bloc CSS (fonts, sidebar, cards, badges)
# qui était dupliqué dans chaque page de la v1.
# Exposer : inject_css(), COULEURS (importé depuis src.config)

COULEURS = {
    "orange": "#FF6B00", "bg": "#0A0D14", "card": "#111827",
    "border": "#1E2540", "critique": "#EF4444", "eleve": "#F59E0B",
    "modere": "#3B82F6", "normal": "#22C55E", "text_dim": "#6B7A99",
}

def inject_css():
    """Injecte le CSS global. À appeler en haut de chaque page."""
    import streamlit as st
    # TODO: coller le bloc <style>...</style> ici
    pass
