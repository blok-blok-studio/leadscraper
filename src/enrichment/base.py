"""Base enrichment module."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseEnricher(ABC):
    """Abstract base class for enrichment modules."""

    MODULE_NAME = "base"

    @abstractmethod
    def enrich(self, lead) -> dict:
        """
        Enrich a lead with additional data.
        Returns a dict of field names (snake_case) → values to update on the lead.
        """
        pass

    def safe_enrich(self, lead) -> dict:
        """Enrich with error handling."""
        try:
            return self.enrich(lead)
        except Exception as e:
            name = getattr(lead, "businessName", getattr(lead, "business_name", "unknown"))
            logger.error(f"[{self.MODULE_NAME}] Error enriching {name}: {e}")
            return {}
