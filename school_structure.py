"""Référentiel des niveaux et classes de l'École Shemec (RDC).

Les libellés sont centralisés ici pour être réutilisés par les formulaires,
les validations et les tests. Les champs universitaires historiques restent
compatibles avec les anciens dossiers.
"""
NIVEAUX_SCOLAIRES = {
    "Maternelle": (
        "1re année maternelle",
        "2e année maternelle",
        "3e année maternelle",
    ),
    "Primaire": tuple(f"{n}e année primaire" for n in range(1, 7)),
    "Secondaire": tuple(f"{n}e secondaire" for n in range(1, 7)),
}

OPTIONS_SECONDAIRE = (
    "Générale",
    "Scientifique",
    "Pédagogie générale",
    "Commerciale et gestion",
    "Technique",
    "Littéraire",
)


def classe_valide(niveau: str, classe: str) -> bool:
    """Retourne vrai si la classe appartient au niveau scolaire indiqué."""
    return classe in NIVEAUX_SCOLAIRES.get(niveau, ())


def option_valide(niveau: str, option: str) -> bool:
    """Les options ne s'appliquent qu'au secondaire."""
    if niveau != "Secondaire":
        return option in ("", "Aucune")
    return option in OPTIONS_SECONDAIRE
