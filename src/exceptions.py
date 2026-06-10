"""
Exceptions métier du système ML Orange Money RA&FM.

Des erreurs NOMMÉES plutôt que des stack traces obscures :
en production, l'opérateur doit comprendre immédiatement ce qui bloque.
"""


class OMError(Exception):
    """Base de toutes les erreurs du système. Attrape-tout propre."""


class DonneesInvalidesError(OMError):
    """Le fichier d'entrée ne respecte pas le contrat (colonnes, format, volume)."""


class ModeleAbsentError(OMError):
    """L'artefact du modèle (pkl/json) est introuvable dans le registre."""


class VersionIncompatibleError(OMError):
    """Les features du fichier ne correspondent pas à celles du modèle entraîné."""


class DriftCritiqueError(OMError):
    """Dérive de données au-delà du seuil critique : scoring déconseillé."""


class InferenceError(OMError):
    """Échec pendant le scoring d'un modèle (avec contexte du modèle en cause)."""

    def __init__(self, modele: str, message: str):
        self.modele = modele
        super().__init__(f"[{modele}] {message}")
