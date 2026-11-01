"""
Définition des schémas de données structurés pour l'analyse IA.
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class ClassifiedEvent(BaseModel):
    """Représentation structurée et validée d'un événement citoyen."""
    is_public_interest: bool = Field(
        description="True si l'information relève de l'intérêt public local, du mandat municipal/intercommunal ou de la vie associative ouverte. False s'il s'agit d'un fait divers individuel, de vie privée ou d'une publicité commerciale privée."
    )
    rejection_reason: Optional[str] = Field(
        default=None,
        description="Raison du rejet si is_public_interest est False (ex: 'fait divers individuel sans portée municipale', 'données privées')."
    )
    title: str = Field(
        description="Titre sobre, clair et informatif pour les administrés (max 80 caractères)."
    )
    summary: str = Field(
        description="Résumé clair et bienveillant de l'information en 1 à 3 phrases."
    )
    category: str = Field(
        description="Catégorie parmi : 'Vie Municipale & Délibérations', 'Travaux & Voirie', 'Manifestations & Vie Associative', 'Enfance & Jeunesse', 'Services & Déchets', 'Culture & Patrimoine', 'Alertes & Météo'."
    )
    badge: str = Field(
        default="Information",
        description="Badge court (ex: 'Arrêté Municipal', 'Animation', 'Conseil', 'Travaux', 'Alerte', 'Pratique')."
    )
    location: str = Field(
        default="Dunières",
        description="Lieu précis de l'événement ou des travaux (ex: 'Salle Annexe, Dunières', 'Médiathèque', 'Rue du 19-Mars-1962')."
    )
    importance: str = Field(
        default="normal",
        description="'high' pour les arrêtés critiques, alertes et conseils municipaux ; 'normal' pour les animations ; 'low' pour les annonces récurrentes."
    )
    start_date: Optional[str] = Field(
        default=None,
        description="Date de début au format YYYY-MM-DD (ex: '2026-11-15') ou null si non mentionnée."
    )
    end_date: Optional[str] = Field(
        default=None,
        description="Date de fin au format YYYY-MM-DD si période (ex: '2026-11-20') ou null si événement ponctuel."
    )
