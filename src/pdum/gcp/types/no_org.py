"""Sentinel container for projects without an organization."""

from __future__ import annotations

from typing import Optional

from pdum.gcp._clients import cloud_billing, crm_v1

from .billing_account import BillingAccount
from .container import Container


class _NoOrgSentinel(Container):
    """Sentinel subclass of Container to represent projects with no organization parent."""

    _instance: Optional["_NoOrgSentinel"] = None

    def __new__(cls):
        if cls._instance is None:
            instance = object.__new__(cls)
            instance.id = ""
            instance.resource_name = "NO_ORG"
            instance.display_name = "No Organization"
            instance._credentials = None
            cls._instance = instance
        return cls._instance

    def __init__(self):
        # Prevent dataclass-generated __init__ from running.
        pass

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return "NO_ORG"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return "NO_ORG"

    def __bool__(self) -> bool:  # pragma: no cover - sentinel is falsy
        return False

    def parent(self, *, credentials=None):
        """Return ``None``; NO_ORG has no parent."""
        return None

    def folders(self, *, credentials=None):
        """Return an empty list; NO_ORG cannot have folders."""
        return []

    def create_folder(self, display_name: str, *, credentials=None):
        """Always raise TypeError because NO_ORG cannot have folders."""
        raise TypeError(
            "NO_ORG cannot have folders. Projects without an organization parent "
            "cannot contain folders. To create a folder, you must first create or "
            "use an existing organization or folder as the parent."
        )

    def cd(self, path: str, *, credentials=None):
        """Always raise TypeError because NO_ORG cannot navigate folders."""
        raise TypeError(
            "NO_ORG cannot have folders. Projects without an organization parent "
            "cannot contain folders. Use cd() on an organization or folder instead."
        )

    def projects(self, *, credentials=None):
        """List projects that have no organization or folder parent."""
        from .project import _project_from_api_response

        creds = self._get_credentials(credentials=credentials)
        crm_service = crm_v1(creds)

        projects = []
        request = crm_service.projects().list()

        while request is not None:
            response = request.execute()
            for project in response.get("projects", []):
                parent = project.get("parent", {})
                parent_type = parent.get("type")

                if not parent_type or parent_type not in ("organization", "folder"):
                    projects.append(_project_from_api_response(project, parent=self, credentials=creds))

            request = crm_service.projects().list_next(previous_request=request, previous_response=response)

        return projects

    def list_projects(self, *, credentials=None):
        """Deprecated alias of :meth:`projects` for backward compatibility."""
        return self.projects(credentials=credentials)

    def billing_accounts(self, *, credentials=None, open_only: bool = True):
        """List all billing accounts visible to the user regardless of parent."""
        creds = self._get_credentials(credentials=credentials)
        billing_service = cloud_billing(creds)

        billing_accounts = []
        request = billing_service.billingAccounts().list()

        while request is not None:
            response = request.execute()

            for account in response.get("billingAccounts", []):
                billing_account_id = account["name"].split("/")[1]
                display_name = account.get("displayName", billing_account_id)
                is_open = account.get("open", False)
                status = "OPEN" if is_open else "CLOSED"

                if not open_only or is_open:
                    billing_accounts.append(
                        BillingAccount(id=billing_account_id, display_name=display_name, status=status)
                    )

            request = billing_service.billingAccounts().list_next(previous_request=request, previous_response=response)

        return billing_accounts


NO_ORG = _NoOrgSentinel()

__all__ = ["NO_ORG"]
