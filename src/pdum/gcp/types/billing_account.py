"""Billing account helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class BillingAccount:
    """Information about a GCP billing account.

    Attributes
    ----------
    id : str
        Billing account ID (for example ``"012345-567890-ABCDEF"``).
    display_name : str
        Human-friendly billing account name.
    status : str
        Status indicator such as ``"OPEN"`` or ``"CLOSED"`` (defaults to ``"OPEN"``).
    """

    id: str
    display_name: str
    status: str = "OPEN"

    def __bool__(self) -> bool:
        """Return True for regular billing accounts.

        Notes
        -----
        Truthiness does not reflect the ``status`` field; even a ``CLOSED`` account
        is truthy. Use ``status`` to inspect openness if needed.
        """

        return True


class _NoBillingAccountSentinel(BillingAccount):
    """Sentinel subclass of BillingAccount to represent projects with no billing account."""

    _instance: Optional[_NoBillingAccountSentinel] = None

    def __new__(cls):
        if cls._instance is None:
            instance = object.__new__(cls)
            instance.id = ""
            instance.display_name = "No Billing Account"
            instance.status = ""
            cls._instance = instance
        return cls._instance

    def __init__(self):
        # Prevent dataclass-generated __init__ from running.
        pass

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return "NO_BILLING_ACCOUNT"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return "NO_BILLING_ACCOUNT"

    def __bool__(self) -> bool:  # pragma: no cover - sentinel is always falsy
        return False


NO_BILLING_ACCOUNT = _NoBillingAccountSentinel()

__all__ = ["BillingAccount", "NO_BILLING_ACCOUNT"]
