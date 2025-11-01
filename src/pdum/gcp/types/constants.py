"""Shared constants for pdum.gcp types."""

from __future__ import annotations

_REQUIRED_APIS: tuple[str, ...] = (
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "serviceusage.googleapis.com",
    "cloudbilling.googleapis.com",
    "firestore.googleapis.com",
)

__all__ = ["_REQUIRED_APIS"]
