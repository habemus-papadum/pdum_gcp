"""Project resource implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Iterable, Optional

import coolname
import google.auth
from google.auth.credentials import Credentials

from pdum.gcp._clients import cloud_billing, crm_v3, service_usage

from .billing_account import NO_BILLING_ACCOUNT, BillingAccount
from .constants import _REQUIRED_APIS
from .resource import Resource

if TYPE_CHECKING:
    from .container import Container
    from .role import Role


@dataclass
class Project(Resource):
    """Information about a GCP project."""

    id: str
    name: str
    project_number: str
    lifecycle_state: str
    parent: "Container"
    _credentials: Optional[Credentials] = field(default=None, repr=False, compare=False)

    def full_resource_name(self) -> str:
        return f"projects/{self.id}"

    def enabled_apis(self, *, credentials: Optional[Credentials] = None) -> list[str]:
        """List enabled APIs for this project."""
        creds = self._get_credentials(credentials=credentials)
        service_usage_client = service_usage(creds)

        enabled_apis: list[str] = []
        parent_name = f"projects/{self.id}"
        request = service_usage_client.services().list(parent=parent_name, filter="state:ENABLED")

        while request is not None:
            response = request.execute()

            for service in response.get("services", []):
                api_name = service.get("config", {}).get("name", "")
                if api_name:
                    enabled_apis.append(api_name)

            request = service_usage_client.services().list_next(previous_request=request, previous_response=response)

        return enabled_apis

    def enable_apis(
        self,
        api_list: list[str],
        *,
        credentials: Optional[Credentials] = None,
        timeout: float = 300.0,
        verbose: bool = True,
        polling_interval: float = 5.0,
    ) -> dict:
        """Enable multiple APIs for this project using batch enable."""
        import time

        creds = self._get_credentials(credentials=credentials)
        service_usage_client = service_usage(creds)

        parent_name = f"projects/{self.id}"
        request_body = {"serviceIds": api_list}

        operation = service_usage_client.services().batchEnable(parent=parent_name, body=request_body).execute()

        operation_name = operation.get("name")
        if verbose:
            print(f"Enabling {len(api_list)} APIs for project {self.id}... ", end="", flush=True)

        start_time = time.time()

        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                if verbose:
                    print()
                raise TimeoutError(f"Operation timed out after {timeout} seconds. Operation name: {operation_name}")

            operation = service_usage_client.operations().get(name=operation_name).execute()

            if operation.get("done", False):
                if verbose:
                    print()

                if "error" in operation:
                    error = operation["error"]
                    error_message = error.get("message", "Unknown error")
                    error_code = error.get("code", "Unknown")
                    raise RuntimeError(f"Operation failed with error code {error_code}: {error_message}")

                return operation

            if verbose:
                print(".", end="", flush=True)

            time.sleep(polling_interval)

    def billing_account(self, *, credentials: Optional[Credentials] = None) -> BillingAccount:
        """Return the project's billing account or ``NO_BILLING_ACCOUNT``."""
        creds = self._get_credentials(credentials=credentials)
        billing_service = cloud_billing(creds)

        resource_name = f"projects/{self.id}"
        billing_info = billing_service.projects().getBillingInfo(name=resource_name).execute()

        billing_enabled = billing_info.get("billingEnabled", False)
        billing_account_name = billing_info.get("billingAccountName", "")

        if not billing_enabled or not billing_account_name:
            return NO_BILLING_ACCOUNT

        billing_account_id = billing_account_name.split("/")[1]
        billing_account_info = billing_service.billingAccounts().get(name=billing_account_name).execute()

        display_name = billing_account_info.get("displayName", billing_account_id)
        is_open = billing_account_info.get("open", False)
        status = "OPEN" if is_open else "CLOSED"

        return BillingAccount(id=billing_account_id, display_name=display_name, status=status)

    def bootstrap_quota_project(
        self,
        *,
        credentials: Optional[Credentials] = None,
        required_apis: Optional[Iterable[str]] = None,
        timeout: float = 300.0,
        verbose: bool = True,
        polling_interval: float = 5.0,
    ) -> dict:
        """Enable the required APIs for using this project as a quota project."""
        creds = self._get_credentials(credentials=credentials)

        current = set(self.enabled_apis(credentials=creds))
        required = set(_REQUIRED_APIS if required_apis is None else required_apis)
        to_enable = sorted(required - current)

        if not to_enable:
            return {"done": True, "result": "no-op", "enabled": sorted(current)}

        return self.enable_apis(
            to_enable,
            credentials=creds,
            timeout=timeout,
            verbose=verbose,
            polling_interval=polling_interval,
        )

    def update_billing_account(
        self,
        billing_account: BillingAccount | str | None,
        *,
        credentials: Optional[Credentials] = None,
    ) -> dict:
        """Update this project's billing account."""
        creds = self._get_credentials(credentials=credentials)
        billing = cloud_billing(creds)

        if billing_account is None:
            ba_name = ""
        elif isinstance(billing_account, BillingAccount):
            ba_name = f"billingAccounts/{billing_account.id}"
        elif isinstance(billing_account, str):
            ba_name = f"billingAccounts/{billing_account}"
        else:
            ba_name = ""

        body = {"billingAccountName": ba_name}
        return billing.projects().updateBillingInfo(name=f"projects/{self.id}", body=body).execute()

    @classmethod
    def update_billing_account_for_id(
        cls,
        project_id: str,
        billing_account: BillingAccount | str | None,
        *,
        credentials: Optional[Credentials] = None,
    ) -> dict:
        """Class-level variant to update billing using a project id."""
        temp = cls(
            id=project_id,
            name="",
            project_number="",
            lifecycle_state="",
            parent=cls._dummy_parent(),
            _credentials=credentials,
        )
        return temp.update_billing_account(billing_account, credentials=credentials)

    @classmethod
    def lookup(cls, project_id: str, *, credentials: Optional[Credentials] = None) -> "Project":
        """Return a Project by id using CRM v3 and resolve its parent."""
        from .folder import Folder
        from .no_org import NO_ORG
        from .organization import Organization

        if credentials is None:
            credentials, _ = google.auth.default()

        crm_service = crm_v3(credentials)

        request = crm_service.projects().search(query=f"id:{project_id}")
        response = request.execute()

        projects = response.get("projects", [])
        if not projects:
            raise FileNotFoundError(f"Project with ID '{project_id}' not found.")
        if len(projects) > 1:
            raise ValueError(f"Found multiple projects with ID '{project_id}'.")

        project_resource = projects[0]
        parent_resource_name = project_resource.get("parent")

        if parent_resource_name and parent_resource_name.startswith("organizations/"):
            org_id = parent_resource_name.split("/")[1]
            parent: Container = Organization.lookup(org_id, credentials=credentials)
        elif parent_resource_name and parent_resource_name.startswith("folders/"):
            folder_resource = crm_service.folders().get(name=parent_resource_name).execute()
            parent = Folder(
                id=folder_resource["name"].split("/")[1],
                resource_name=folder_resource["name"],
                display_name=folder_resource.get("displayName", ""),
                parent_resource_name=folder_resource.get("parent", ""),
                _credentials=credentials,
            )
        else:
            parent = NO_ORG

        return cls(
            id=project_resource["projectId"],
            name=project_resource.get("displayName", ""),
            project_number=str(project_resource.get("projectNumber", "")),
            lifecycle_state=project_resource.get("state", ""),
            parent=parent,
            _credentials=credentials,
        )

    @classmethod
    def suggest_name(cls, *, prefix: Optional[str] = None, random_digits: int = 5) -> str:
        """Suggest a valid GCP project id using an optional prefix."""
        import random

        if not 0 <= random_digits <= 10:
            raise ValueError("random_digits must be between 0 and 10")

        if prefix is None:
            prefix = coolname.generate_slug(2)
        else:
            if not prefix or not prefix[0].islower() or not prefix[0].isalpha():
                raise ValueError("prefix must start with a lowercase letter")

        if random_digits > 0:
            digits = "".join(str(random.randint(0, 9)) for _ in range(random_digits))
            name = f"{prefix}-{digits}"
        else:
            name = prefix

        if len(name) < 6 or len(name) > 30:
            raise ValueError(
                f"Generated name '{name}' is {len(name)} characters, but GCP project IDs must be 6-30 characters long"
            )

        return name

    def list_roles(
        self,
        *,
        credentials: Optional[Credentials] = None,
        user_email: str | None = None,
    ) -> list["Role"]:
        """List IAM roles for a user on this project."""
        creds = self._get_credentials(credentials=credentials)
        from pdum.gcp._helpers import _list_roles

        return _list_roles(credentials=creds, resource_name=f"projects/{self.id}", user_email=user_email)

    def add_user_as_owner(self, user_email: str, *, credentials: Optional[Credentials] = None) -> dict:
        """Add a user to the project's Owners (roles/owner) binding."""
        if "@" not in user_email or not user_email.strip():
            raise ValueError("user_email must be a valid email address")

        member = f"user:{user_email.strip()}"
        role = "roles/owner"

        creds = self._get_credentials(credentials=credentials)
        crm = crm_v3(creds)
        resource = f"projects/{self.id}"

        policy = (
            crm.projects().getIamPolicy(resource=resource, body={"options": {"requestedPolicyVersion": 3}}).execute()
        )

        if policy.get("version", 0) < 3:
            policy["version"] = 3

        bindings = policy.setdefault("bindings", [])
        owner_binding = next((b for b in bindings if b.get("role") == role), None)

        if owner_binding is None:
            owner_binding = {"role": role, "members": [member]}
            bindings.append(owner_binding)
        else:
            members = owner_binding.setdefault("members", [])
            if member in members:
                return policy
            members.append(member)

        updated = crm.projects().setIamPolicy(resource=resource, body={"policy": policy}).execute()
        return updated

    @staticmethod
    def _dummy_parent() -> "Container":
        """Return a lightweight placeholder container for helper construction."""
        from .no_org import NO_ORG

        return NO_ORG


def _project_from_api_response(
    project_dict: dict,
    parent: "Container",
    credentials: Optional[Credentials] = None,
) -> Project:
    """Create a Project from API response data."""
    return Project(
        id=project_dict["projectId"],
        name=project_dict.get("name", ""),
        project_number=project_dict.get("projectNumber", ""),
        lifecycle_state=project_dict.get("lifecycleState", ""),
        parent=parent,
        _credentials=credentials,
    )


__all__ = ["Project", "_project_from_api_response"]
