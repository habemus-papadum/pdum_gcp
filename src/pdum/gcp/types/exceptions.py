"""Custom exceptions for pdum.gcp types."""

from __future__ import annotations


class APIResolutionError(Exception):
    """Raised when an API display name cannot be uniquely resolved to a service ID."""

    __slots__ = ()


__all__ = ["APIResolutionError"]
