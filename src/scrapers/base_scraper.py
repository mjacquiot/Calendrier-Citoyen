"""
Modèle de publication brute et classe abstraite de Scraper.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class RawPublication:
    """Représente une publication collectée depuis une source publique locale."""
    id: str
    source_id: str
    source_name: str
    title: str
    content: str
    url: str
    published_at: Optional[str] = None
    image_url: Optional[str] = None
    external_links: List[str] = field(default_factory=list)
    raw_metadata: Dict[str, Any] = field(default_factory=dict)
    enrichment: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "source_name": self.source_name,
            "title": self.title,
            "content": self.content,
            "url": self.url,
            "published_at": self.published_at,
            "image_url": self.image_url,
            "external_links": self.external_links,
            "raw_metadata": self.raw_metadata,
            "enrichment": self.enrichment
        }


class BaseScraper(ABC):
    """Classe de base pour tous les collecteurs de données municipales."""

    def __init__(self, source_config: Dict[str, Any]):
        self.config = source_config
        self.source_id = source_config.get("id", "source_inconnue")
        self.source_name = source_config.get("nom", self.source_id)

    @abstractmethod
    def fetch(self) -> List[RawPublication]:
        """Exécute la collecte et renvoie une liste de publications brutes."""
        pass
