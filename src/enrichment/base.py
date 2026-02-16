"""Base enrichment module."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from src.database.models import Lead

logger = logging.getLogger(__name__)


class BaseEnricher(ABC):
    """Abstract base class for enrichment modules."""

    MODULE_NAME = "base"

    @abstractmethod
    def enrich(self, lead: Lead) -> dict:
        """
        Enrich a lead with additional data.
        Returns a dict of field names → values to update on the lead.
        """
        pass

    def safe_enrich(self, lead: Lead) -> dict:
        """Enrich with error handling."""
        try:
            return self.enrich(lead)
        except Exception as e:
            logger.error(f"[{self.MODULE_NAME}] Error enriching {lead.business_name}: {e}")
            return {}
