"""Shared resource base classes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import google.auth
from google.auth.credentials import Credentials


class Resource(ABC):
    """Abstract base for CRM-addressable resources."""

    _credentials: Optional[Credentials]

    @abstractmethod
    def full_resource_name(self) -> str:
        """Return the fully qualified resource name (``projects/{id}``, ``folders/{id}``, ``organizations/{id}``)."""

    def _get_credentials(self, *, credentials: Optional[Credentials] = None) -> Credentials:
        """Get credentials for API calls (explicit > stored > ADC)."""
        if credentials is not None:
            return credentials
        if getattr(self, "_credentials", None) is not None:
            return self._credentials  # type: ignore[attr-defined]
        creds, _ = google.auth.default()
        return creds


__all__ = ["Resource"]
