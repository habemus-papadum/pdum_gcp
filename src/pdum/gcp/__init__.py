"""Utilities and tools for Google Cloud"""

from importlib.metadata import version

from pdum.gcp.admin import (
    doctor,
    get_email,
    get_iam_policy,
    list_organizations,
    list_roles,
    lookup_api,
    quota_project,
    walk_projects,
)
from pdum.gcp.types import (
    NO_BILLING_ACCOUNT,
    NO_ORG,
    APIResolutionError,
    BillingAccount,
    Container,
    Folder,
    MultiRegion,
    Organization,
    Project,
    Region,
)

__version__ = version("habemus-papadum-gcp")


__all__ = [
    "__version__",
    "get_email",
    "get_iam_policy",
    "doctor",
    "list_roles",
    "list_organizations",
    "lookup_api",
    "quota_project",
    "walk_projects",
    "APIResolutionError",
    "BillingAccount",
    "Container",
    "Organization",
    "Folder",
    "Project",
    "Region",
    "MultiRegion",
    "NO_ORG",
    "NO_BILLING_ACCOUNT",
]
