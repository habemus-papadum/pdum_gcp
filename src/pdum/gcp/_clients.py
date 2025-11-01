"""Internal helpers to construct Google API service clients.

These helpers centralize `googleapiclient.discovery.build` usage to keep
options consistent across the codebase. They are intentionally private; the
public API surface remains in `admin.py` and `types.py`.
"""

from __future__ import annotations

from google.auth.credentials import Credentials
from googleapiclient import discovery


def crm_v1(credentials: Credentials):
    """Cloud Resource Manager v1 service client."""
    return discovery.build("cloudresourcemanager", "v1", credentials=credentials, cache_discovery=False)


def crm_v3(credentials: Credentials):
    """Cloud Resource Manager v3 service client."""
    return discovery.build("cloudresourcemanager", "v3", credentials=credentials, cache_discovery=False)


def iam_v1(credentials: Credentials):
    """IAM v1 service client."""
    return discovery.build("iam", "v1", credentials=credentials, cache_discovery=False)


def service_usage(credentials: Credentials):
    """Service Usage v1 service client."""
    return discovery.build("serviceusage", "v1", credentials=credentials, cache_discovery=False)


def cloud_billing(credentials: Credentials):
    """Cloud Billing v1 service client."""
    return discovery.build("cloudbilling", "v1", credentials=credentials, cache_discovery=False)
