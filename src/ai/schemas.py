"""
Définition des schémas de données structurés et stricts pour l'analyse IA.
"""

from typing import Optional, List, Literal
from pydantic import BaseModel, Field


CategoryLiteral = Literal[
    "Vie Municipale & Délibérations",
    "Travaux & Voirie",
    "Manifestations & Vie Associative",
    "Enfance & Jeunesse",
    "Services & Déchets",
    "Culture & Patrimoine",
    "Alertes & Météo",
    "Non retenu",
]

ImportanceLiteral = Literal["high", "normal", "low"]
ContentTypeLiteral = Literal["event", "alert", "info", "news"]


class ClassifiedEvent(BaseModel):
    """Représentation structurée et validée d'un événement citoyen."""

    is_public_interest: bool = Field(
        description=(
            "True si l'information relève de l'intérêt public local, du mandat municipal/intercommunal "
            "ou d'une manifestation associative/culturelle ouverte au public. False s'il s'agit d'un fait divers "
            "individuel, de vie privée, d'un portrait/ouverture d'entreprise privée, d'un publi-reportage, "
            "d'un compte-rendu sportif passé sans événement à venir, ou d'une sortie de livre sans rencontre publique datée."
        )
    )
    rejection_reason: Optional[str] = Field(
        default=None,
        description="Raison du rejet si is_public_interest est False.",
    )
    title: str = Field(
        description="Titre sobre, clair et informatif pour les administrés, commençant par une majuscule et sans emoji initial (max 120 caractères)."
    )
    summary: str = Field(
        description="Résumé factuel, clair et soigné de l'information en 1 à 3 phrases complètes."
    )
    category: CategoryLiteral = Field(
        description="Catégorie officielle exacte parmi la liste autorisée."
    )
    badge: str = Field(
        default="Information",
        description="Badge court (ex: 'Arrêté / Travaux', 'Animation', 'Conseil Municipal', 'Culture', 'Alerte Publique', 'Service Public').",
    )
    location: str = Field(
        default="Dunières / Haut Pays du Velay",
        description="Lieu précis de l'événement ou des travaux (ex: 'Salle des Associations, Dunières', 'Salle Renaissance, Montfaucon-en-Velay').",
    )
    importance: ImportanceLiteral = Field(
        default="normal",
        description="'high' pour les alertes, arrêtés critiques et conseils municipaux ; 'normal' pour les animations ; 'low' pour les annonces secondaires.",
    )
    content_type: ContentTypeLiteral = Field(
        default="event",
        description="Nature éditoriale : 'event' (rendez-vous daté), 'alert' (urgence/météo/coupure), 'info' (arrêté/travaux/service public), 'news' (actualité locale).",
    )
    price: Optional[str] = Field(
        default=None,
        description=(
            "Tarif d'entrée/inscription explicite de l'événement principal uniquement (ex: 'Gratuit', '10 €', '6 € – 10 €'), "
            "ou null si non applicable/non mentionné. Ne jamais inclure le prix d'un livre, un bénéfice caritatif, "
            "un lot de concours ou un autre événement cité en fin d'article."
        ),
    )
    start_date: Optional[str] = Field(
        default=None,
        description="Date de début au format YYYY-MM-DD (ex: '2026-11-15') ou null si non mentionnée.",
    )
    end_date: Optional[str] = Field(
        default=None,
        description="Date de fin au format YYYY-MM-DD si période (ex: '2026-11-20') ou null si événement ponctuel.",
    )
    start_time: Optional[str] = Field(
        default=None,
        description="Heure de début principale au format 24h HH:MM (ex: '18:30') ou null si non précisée.",
    )
    end_time: Optional[str] = Field(
        default=None,
        description="Heure de fin principale au format 24h HH:MM (ex: '20:00') ou null si non précisée.",
    )
    additional_slots: List[str] = Field(
        default_factory=list,
        description="Créneaux horaires supplémentaires le même jour au format 'HH:MM-HH:MM' (ex: ['20:30-22:00']) si l'événement a plusieurs séances.",
    )
