"""Organization container implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

import google.auth
from google.auth.credentials import Credentials

from pdum.gcp._clients import cloud_billing, crm_v3

from .container import Container

if TYPE_CHECKING:
    from .billing_account import BillingAccount
    from .folder import Folder
    from .project import Project


@dataclass
class Organization(Container):
    """Information about a GCP organization."""

    ORGANIZATION_OWNER_ROLES: tuple[str, ...] = (
        "roles/billing.admin",
        "roles/billing.costsManager",
        "roles/billing.projectManager",
        "roles/iam.securityAdmin",
        "roles/orgpolicy.policyAdmin",
        "roles/resourcemanager.folderAdmin",
        "roles/resourcemanager.organizationAdmin",
        "roles/resourcemanager.projectCreator",
        "roles/resourcemanager.projectDeleter",
        "roles/resourcemanager.projectIamAdmin",
    )

    def parent(self, *, credentials: Optional[Credentials] = None) -> Optional[Container]:
        """Return the parent container (organizations are roots, so ``None``)."""
        return None

    def folders(self, *, credentials: Optional[Credentials] = None) -> list[Folder]:
        """List direct child folders of this organization."""
        from .folder import Folder

        creds = self._get_credentials(credentials=credentials)
        crm_service = crm_v3(creds)

        folders: list[Folder] = []
        request = crm_service.folders().list(parent=self.resource_name)

        while request is not None:
            response = request.execute()
            for folder in response.get("folders", []):
                folders.append(
                    Folder(
                        id=folder["name"].split("/")[1],
                        resource_name=folder["name"],
                        display_name=folder.get("displayName", ""),
                        parent_resource_name=self.resource_name,
                        _credentials=creds,
                    )
                )

            request = crm_service.folders().list_next(previous_request=request, previous_response=response)

        return folders

    def projects(self, *, credentials: Optional[Credentials] = None) -> list["Project"]:
        """List direct child projects of this organization."""
        from .project import _project_from_api_response

        creds = self._get_credentials(credentials=credentials)
        crm_service = crm_v3(creds)

        projects: list["Project"] = []
        request = crm_service.projects().list(parent=self.resource_name)

        while request is not None:
            response = request.execute()
            for project in response.get("projects", []):
                projects.append(_project_from_api_response(project, parent=self, credentials=creds))

            request = crm_service.projects().list_next(previous_request=request, previous_response=response)

        return projects

    def create_folder(self, display_name: str, *, credentials: Optional[Credentials] = None) -> "Folder":
        """Create a folder directly under this organization."""
        from .folder import Folder

        creds = self._get_credentials(credentials=credentials)
        crm_service = crm_v3(creds)

        folder_body = {
            "displayName": display_name,
            "parent": self.resource_name,
        }

        operation = crm_service.folders().create(body=folder_body).execute()

        import time

        while not operation.get("done", False):
            time.sleep(1)
            operation = crm_service.operations().get(name=operation["name"]).execute()

        folder_resource_name = operation["response"]["name"]
        folder_id = folder_resource_name.split("/")[1]

        return Folder(
            id=folder_id,
            resource_name=folder_resource_name,
            display_name=display_name,
            parent_resource_name=self.resource_name,
            _credentials=creds,
        )

    def add_user_roles(
        self,
        user_email: str,
        roles_to_add: list[str],
        *,
        credentials: Optional[Credentials] = None,
    ) -> dict:
        """Add a user to one or more IAM roles at the Organization level."""
        if "@" not in user_email or not user_email.strip():
            raise ValueError("user_email must be a valid email address")
        if not roles_to_add:
            raise ValueError("roles_to_add must be a non-empty list of role names")

        member = f"user:{user_email.strip()}"
        creds = self._get_credentials(credentials=credentials)
        crm = crm_v3(creds)
        resource = self.resource_name

        policy = (
            crm.organizations()
            .getIamPolicy(resource=resource, body={"options": {"requestedPolicyVersion": 3}})
            .execute()
        )

        if policy.get("version", 0) < 3:
            policy["version"] = 3

        bindings = policy.setdefault("bindings", [])
        changes_made = False

        for role in roles_to_add:
            binding = next((b for b in bindings if b.get("role") == role), None)
            if binding is None:
                bindings.append({"role": role, "members": [member]})
                changes_made = True
            else:
                members = binding.setdefault("members", [])
                if member not in members:
                    members.append(member)
                    changes_made = True

        if not changes_made:
            return policy

        updated = crm.organizations().setIamPolicy(resource=resource, body={"policy": policy}).execute()
        return updated

    def add_user_as_owner(self, user_email: str, *, credentials: Optional[Credentials] = None) -> dict:
        """Grant a user a standard set of high-privilege org roles."""
        return self.add_user_roles(
            user_email,
            roles_to_add=list(self.ORGANIZATION_OWNER_ROLES),
            credentials=credentials,
        )

    def billing_accounts(
        self,
        *,
        credentials: Optional[Credentials] = None,
        open_only: bool = True,
    ) -> list["BillingAccount"]:
        """List billing accounts scoped to this organization."""
        from .billing_account import BillingAccount

        creds = self._get_credentials(credentials=credentials)
        billing_service = cloud_billing(creds)

        accounts: list[BillingAccount] = []
        request = billing_service.billingAccounts().list(parent=self.resource_name)

        while request is not None:
            response = request.execute()

            for account in response.get("billingAccounts", []):
                billing_account_id = account["name"].split("/")[1]
                display_name = account.get("displayName", billing_account_id)
                is_open = account.get("open", False)
                status = "OPEN" if is_open else "CLOSED"

                if open_only and not is_open:
                    continue

                accounts.append(BillingAccount(id=billing_account_id, display_name=display_name, status=status))

            request = billing_service.billingAccounts().list_next(previous_request=request, previous_response=response)

        return accounts

    @classmethod
    def lookup(cls, org_id: str, *, credentials: Optional[Credentials] = None) -> "Organization":
        """Return an Organization by id using CRM v3."""
        if credentials is None:
            credentials, _ = google.auth.default()

        crm_service = crm_v3(credentials)
        resource_name = f"organizations/{org_id}"
        org_resource = crm_service.organizations().get(name=resource_name).execute()

        return cls(
            id=org_id,
            resource_name=resource_name,
            display_name=org_resource.get("displayName", ""),
            _credentials=credentials,
        )


__all__ = ["Organization"]
