"""IAM role dataclass."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Role:
    """Information about an IAM role.

    Attributes
    ----------
    name : str
        Role resource name (e.g., ``"roles/owner"``).
    title : str
        Human-readable title for the role.
    description : str
        Short description of what the role grants.
    """

    name: str
    title: str
    description: str


__all__ = ["Role"]
