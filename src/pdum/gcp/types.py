"""Type definitions for GCP resources.

This module contains dataclasses and type definitions for GCP resources
like organizations, folders, and projects.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Generator, Optional

import google.auth
from google.auth.credentials import Credentials

from pdum.gcp._clients import cloud_billing, crm_v1, crm_v3, service_usage

if TYPE_CHECKING:
    pass


class APIResolutionError(Exception):
    """Raised when an API display name cannot be uniquely resolved to a service ID."""

    pass


@dataclass
class Role:
    """Information about an IAM role.

    Attributes:
        name: The role name (e.g., "roles/owner")
        title: The human-readable role title
        description: A description of the role
    """

    name: str
    title: str
    description: str


@dataclass
class BillingAccount:
    """Information about a GCP billing account.

    Attributes:
        id: The billing account ID (e.g., "012345-567890-ABCDEF")
        display_name: The human-readable display name for the billing account
        status: Status string, e.g., "OPEN" or "CLOSED" (default: "OPEN")
    """

    id: str
    display_name: str
    status: str = "OPEN"

    def __bool__(self) -> bool:
        """Return True for regular billing accounts.

        Note
        ----
        Truthiness does not reflect the `status` field; even a CLOSED account
        is truthy. Use `status` to inspect openness if needed.
        """
        return True


class Resource(ABC):
    """Abstract base for CRM-addressable resources.

    Provides uniform access to the fully-qualified resource name and shared
    credential materialization logic.
    """

    _credentials: Optional[Credentials]

    @abstractmethod
    def full_resource_name(self) -> str:
        """Return the fully qualified resource name (projects/{id}, folders/{id}, organizations/{id})."""

    def _get_credentials(self, *, credentials: Optional[Credentials] = None) -> Credentials:
        """Get credentials for API calls (explicit > stored > ADC)."""
        if credentials is not None:
            return credentials
        if getattr(self, "_credentials", None) is not None:
            return self._credentials  # type: ignore[attr-defined]
        creds, _ = google.auth.default()
        return creds


@dataclass
class Container(Resource):
    """Base class for GCP resource containers (Organizations, Folders, and NO_ORG).

    This base class provides common functionality for all container types that can
    hold projects and folders.

    Attributes:
        id: The container ID (numeric string for orgs/folders, empty for NO_ORG)
        resource_name: The full resource name (e.g., "organizations/123" or "folders/456")
        display_name: The human-readable display name
        _credentials: Optional Google Cloud credentials to use for API calls
    """

    id: str
    resource_name: str
    display_name: str
    _credentials: Optional[Credentials] = field(default=None, repr=False, compare=False)

    def full_resource_name(self) -> str:
        return self.resource_name

    def parent(self, *, credentials=None) -> Optional[Container]:
        """Get the parent container.

        Args:
            credentials: Google Cloud credentials to use. If None, uses stored credentials or ADC.

        Returns:
            The parent Container (Organization or Folder), or None if no parent

        Raises:
            NotImplementedError: Subclasses must implement this method
        """
        raise NotImplementedError("Subclasses must implement parent()")

    def folders(self, *, credentials=None) -> list[Folder]:
        """List folders that are direct children of this container.

        Args:
            credentials: Google Cloud credentials to use. If None, uses Application Default Credentials.

        Returns:
            List of Folder objects that are direct children

        Raises:
            NotImplementedError: Subclasses must implement this method
        """
        raise NotImplementedError("Subclasses must implement folders()")

    def projects(self, *, credentials=None) -> list[Project]:
        """List projects that are direct children of this container.

        Args:
            credentials: Google Cloud credentials to use. If None, uses Application Default Credentials.

        Returns:
            List of Project objects that are direct children

        Raises:
            NotImplementedError: Subclasses must implement this method
        """
        raise NotImplementedError("Subclasses must implement projects()")

    def create_folder(self, display_name: str, *, credentials=None) -> Folder:
        """Create a new folder as a child of this container.

        Args:
            display_name: The human-readable name for the folder
            credentials: Google Cloud credentials to use. If None, uses stored credentials or ADC.

        Returns:
            A Folder object representing the newly created folder

        Raises:
            NotImplementedError: Subclasses must implement this method
        """
        raise NotImplementedError("Subclasses must implement create_folder()")

    def list_roles(self, *, credentials=None) -> list[Role]:
        """List the IAM roles for the current user on this container.

        Args:
            credentials: Google Cloud credentials to use. If None, uses stored credentials or ADC.

        Returns:
            A list of Role objects.
        """
        creds = self._get_credentials(credentials=credentials)
        from pdum.gcp._helpers import _list_roles
        return _list_roles(credentials=creds, resource_name=self.resource_name)

    def create_project(
        self,
        project_id: str,
        display_name: str,
        *,
        billing_account: "BillingAccount" = None,  # default set below for typing clarity
        credentials=None,
        timeout: float = 600.0,
        polling_interval: float = 5.0,
    ) -> "Project":
        """Create a new project under this container and optionally attach billing.

        Parameters
        ----------
        project_id : str
            The new project's ID (must satisfy GCP constraints).
        display_name : str
            Human-friendly display name for the project.
        billing_account : BillingAccount, optional
            Billing account to attach after creation. If omitted or falsy (e.g.,
            ``NO_BILLING_ACCOUNT``), billing is not attached.
        credentials : Credentials, optional
            Explicit credentials to use. If ``None``, uses stored credentials or ADC.
        timeout : float, default 600.0
            Max seconds to wait for the long-running create operation.
        polling_interval : float, default 5.0
            Seconds between operation polls.

        Returns
        -------
        Project
            The created project materialized as a Project instance.

        Raises
        ------
        googleapiclient.errors.HttpError
            If any API call fails.
        TimeoutError
            If creation does not complete within ``timeout`` seconds.
        RuntimeError
            If the create operation completes with an error.

        Notes
        -----
        This method mutates GCP estate (creates resources, may attach billing).
        Do not run in CI. Prefer invoking manually with appropriate credentials.
        """
        # Avoid circular import for sentinel
        from pdum.gcp.types import NO_BILLING_ACCOUNT as _NO_BILLING_ACCOUNT

        # Default billing account sentinel
        if billing_account is None:
            billing_account = _NO_BILLING_ACCOUNT

        creds = self._get_credentials(credentials=credentials)
        crm = crm_v3(creds)

        body = {
            "projectId": project_id,
            "displayName": display_name,
        }

        # Parent: use container resource name unless creating without an org/folder
        is_no_org = (self is NO_ORG) or (getattr(self, "resource_name", "") == "NO_ORG")
        parent_name = None if is_no_org else self.resource_name
        if parent_name:
            body["parent"] = parent_name

        # Initiate creation (LRO)
        operation = crm.projects().create(body=body).execute()

        # Poll until done or timeout
        import time

        op_name = operation.get("name")
        start = time.time()
        while not operation.get("done", False):
            if time.time() - start > timeout:
                raise TimeoutError(f"Project create operation timed out after {timeout}s (operation: {op_name})")
            time.sleep(polling_interval)
            operation = crm.operations().get(name=op_name).execute()

        if "error" in operation:
            err = operation["error"]
            raise RuntimeError(f"Project creation failed: {err.get('code')}: {err.get('message')}")

        # Attach billing if a real account provided
        if billing_account:
            billing = cloud_billing(creds)
            billing_body = {
                "billingAccountName": f"billingAccounts/{billing_account.id}",
                "billingEnabled": True,
            }
            billing.projects().updateBillingInfo(name=f"projects/{project_id}", body=billing_body).execute()

        # Return a fully materialized Project
        return Project.lookup(project_id, credentials=creds)
    def walk_projects(
        self, *, credentials=None, active_only: bool = True
    ) -> Generator[Project, None, None]:
        """Recursively yield all projects within this container and its subfolders.

        This method performs a depth-first search through the container hierarchy,
        yielding all projects found. It first yields immediate projects of this
        container, then recursively yields projects from all child folders.

        Args:
            credentials: Google Cloud credentials to use. If None, uses stored credentials or ADC.
            active_only: If True (default), only yield projects in ACTIVE state.
                If False, yield all projects regardless of lifecycle state
                (including DELETE_REQUESTED and DELETE_IN_PROGRESS).

        Yields:
            Project objects found in this container and all nested folders

        Example:
            >>> from pdum.gcp import list_organizations
            >>> orgs = list_organizations()
            >>> for org in orgs:
            ...     print(f"Organization: {org.display_name}")
            ...     for project in org.walk_projects():
            ...         print(f"  - {project.id}")
            Organization: My Organization
              - project-1
              - project-2
              - nested-folder-project-3
        """
        creds = self._get_credentials(credentials=credentials)

        # Yield all immediate projects of this container
        for project in self.projects(credentials=creds):
            # Filter by lifecycle state if active_only is True
            if active_only and project.lifecycle_state != "ACTIVE":
                continue
            yield project

        # Recursively yield projects from all child folders
        for folder in self.folders(credentials=creds):
            yield from folder.walk_projects(credentials=creds, active_only=active_only)

    def tree(self, *, credentials=None, _prefix: str = "", _is_last: bool = True) -> None:
        """Print a visual tree of this container and its children.

        The output includes organizations (🌺), folders (🎸), and projects (🎵),
        using box-drawing characters for structure.

        Parameters
        ----------
        credentials : Credentials, optional
            Explicit credentials to use. If ``None``, uses stored credentials or ADC.
        _prefix : str, optional
            Internal indentation prefix. Do not pass manually.
        _is_last : bool, optional
            Internal flag for branch drawing. Do not pass manually.

        Examples
        --------
        >>> from pdum.gcp import list_organizations
        >>> for org in list_organizations():  # doctest: +SKIP
        ...     org.tree()  # doctest: +ELLIPSIS
        🌺 My Organization (organizations/123456789)
        ├── 🎸 Development (folders/111)
        │   ├── 🎵 dev-project-1 (ACTIVE)
        │   └── 🎵 dev-project-2 (ACTIVE)
        └── ...
        """
        creds = self._get_credentials(credentials=credentials)

        # Determine the emoji based on the container type (whimsical and colorful!)
        if self is NO_ORG:
            emoji = "🐞"  # Ladybug - free-floating projects
        elif isinstance(self, Organization):
            emoji = "🌺"  # Hibiscus - beautiful organization flower
        else:  # Folder
            emoji = "🎸"  # Guitar - folders rock!

        # Print the current container
        print(f"{_prefix}{emoji} {self.display_name} ({self.resource_name})")

        # Delegate printing of children to the shared helper
        self._tree_children(credentials=creds, _prefix=_prefix)

    def _tree_children(self, *, credentials=None, _prefix: str = "") -> None:
        """Internal helper to print children without printing the parent again.

        Args:
            credentials: Google Cloud credentials to use
            _prefix: The prefix for indentation
        """
        creds = self._get_credentials(credentials=credentials)

        # Get all folders and projects
        folders = self.folders(credentials=creds)
        projects = self.projects(credentials=creds)

        # Combine them for processing
        all_children = folders + projects
        total_children = len(all_children)

        # Process each child
        for idx, child in enumerate(all_children):
            is_last_child = idx == total_children - 1

            if isinstance(child, Project):
                # Print project - each project is a musical note!
                branch = "└── " if is_last_child else "├── "
                print(f"{_prefix}{branch}🎵 {child.id} ({child.lifecycle_state})")
            else:
                # Print folder recursively
                branch = "└── " if is_last_child else "├── "
                extension = "    " if is_last_child else "│   "
                new_prefix = _prefix + extension

                print(f"{_prefix}{branch}🎸 {child.display_name} ({child.resource_name})")
                # Recursively print the folder's children
                child._tree_children(credentials=creds, _prefix=new_prefix)

    def cd(self, path: str, *, credentials=None) -> Folder:
        """Navigate to a child folder using a slash-separated path.

        Parameters
        ----------
        path : str
            Path like ``"dev/team-a/project-folder"``. Leading/trailing slashes are ignored.
        credentials : Credentials, optional
            Explicit credentials to use. If ``None``, uses stored credentials or ADC.

        Returns
        -------
        Folder
            The matching folder.

        Raises
        ------
        ValueError
            If the path is empty or a component is not found.
        TypeError
            If invoked on ``NO_ORG`` (which cannot have folders).

        Examples
        --------
        >>> from pdum.gcp import list_organizations
        >>> org = list_organizations()[0]  # doctest: +SKIP
        >>> org.cd("dev/team-a")  # doctest: +SKIP
        Folder(...)
        """
        creds = self._get_credentials(credentials=credentials)

        # Strip leading and trailing slashes and split the path
        path = path.strip("/")

        # Handle empty path
        if not path:
            raise ValueError("Path cannot be empty")

        # Split the path into components
        components = path.split("/")

        # Start with the current container
        current_container: Container = self

        # Navigate through each path component
        for component in components:
            # List all folders in the current container
            folders = current_container.folders(credentials=creds)

            # Find the folder matching this component
            matching_folder = None
            for folder in folders:
                if folder.display_name == component:
                    matching_folder = folder
                    break

            # If no matching folder found, raise an error
            if matching_folder is None:
                raise ValueError(
                    f"Folder '{component}' not found in {current_container.display_name}. "
                    f"Available folders: {', '.join(f.display_name for f in folders) or '(none)'}"
                )

            # Move to the matching folder
            current_container = matching_folder

        # Return the final folder
        return current_container


@dataclass
class Organization(Container):
    """Information about a GCP organization.

    Attributes:
        id: The organization ID (numeric string)
        resource_name: The resource name (e.g., "organizations/123456789")
        display_name: The human-readable display name
    """

    def parent(self, *, credentials=None) -> Optional[Container]:
        """Get the parent container.

        Organizations are root-level resources and have no parent.

        Args:
            credentials: Google Cloud credentials to use. If None, uses stored credentials or ADC.

        Returns:
            None (organizations have no parent)
        """
        return None

    def folders(self, *, credentials=None) -> list[Folder]:
        """List direct child folders of this organization.

        Parameters
        ----------
        credentials : Credentials, optional
            Explicit credentials to use. If ``None``, uses stored credentials or ADC.

        Returns
        -------
        list[Folder]
            Direct child folders of this organization.
        """
        creds = self._get_credentials(credentials=credentials)

        crm_service = crm_v3(creds)

        folders = []
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

            request = crm_service.folders().list_next(
                previous_request=request, previous_response=response
            )

        return folders

    def projects(self, *, credentials=None) -> list[Project]:
        """List direct child projects of this organization.

        Parameters
        ----------
        credentials : Credentials, optional
            Explicit credentials to use. If ``None``, uses stored credentials or ADC.

        Returns
        -------
        list[Project]
            Direct child projects of this organization.
        """
        creds = self._get_credentials(credentials=credentials)

        crm_service = crm_v3(creds)

        projects = []
        # Filter projects by parent organization
        request = crm_service.projects().list(parent=self.resource_name)

        while request is not None:
            response = request.execute()
            for project in response.get("projects", []):
                projects.append(
                    _project_from_api_response(project, parent=self, credentials=creds)
                )

            request = crm_service.projects().list_next(
                previous_request=request, previous_response=response
            )

        return projects

    def create_folder(self, display_name: str, *, credentials=None) -> "Folder":
        """Create a folder directly under this organization.

        Parameters
        ----------
        display_name : str
            The display name for the new folder.
        credentials : Credentials, optional
            Explicit credentials to use. If ``None``, uses stored credentials or ADC.

        Returns
        -------
        Folder
            The created folder resource.

        Raises
        ------
        googleapiclient.errors.HttpError
            If the API call fails.
        """
        creds = self._get_credentials(credentials=credentials)

        crm_service = crm_v3(creds)

        # Create folder request body
        folder_body = {
            "displayName": display_name,
            "parent": self.resource_name,
        }

        # Call the folders.create() method
        operation = crm_service.folders().create(
            body=folder_body
        ).execute()

        # Wait for the operation to complete (folders.create returns a long-running operation)
        # The operation name is in the format "operations/..."
        while not operation.get("done", False):
            import time

            time.sleep(1)
            operation = crm_service.operations().get(name=operation["name"]).execute()

        # Extract the folder from the operation response
        folder_resource_name = operation["response"]["name"]
        folder_id = folder_resource_name.split("/")[1]

        # Return a Folder object
        return Folder(
            id=folder_id,
            resource_name=folder_resource_name,
            display_name=display_name,
            parent_resource_name=self.resource_name,
            _credentials=creds,
        )

    def add_user_roles(self, user_email: str, roles_to_add: list[str], *, credentials=None) -> dict:
        """Add a user to one or more IAM roles at the Organization level.

        This updates the Organization's IAM policy by ensuring ``user:{email}``
        is present in each specified role binding. If a binding does not exist,
        it is created; if the member already exists for a role, that role is
        left unchanged.

        Parameters
        ----------
        user_email : str
            The user's email address (e.g., ``"admin@example.com"``). The
            ``user:`` prefix is added automatically.
        roles_to_add : list[str]
            A list of role names (for example: ``"roles/billing.admin"``,
            ``"roles/iam.securityAdmin"``, ``"roles/resourcemanager.organizationAdmin"``).
        credentials : Credentials, optional
            Explicit credentials to use. If ``None``, uses stored credentials or ADC.

        Returns
        -------
        dict
            The updated (or current, if no change) IAM policy as a dictionary.

        Raises
        ------
        ValueError
            If the email appears invalid or ``roles_to_add`` is empty.
        googleapiclient.errors.HttpError
            If the get/set policy API calls fail.

        Notes
        -----
        This method mutates Organization-level IAM policy. Ensure you have
        ``resourcemanager.organizations.setIamPolicy`` on the target org.
        Not executed in CI.
        """
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

        updated = (
            crm.organizations().setIamPolicy(resource=resource, body={"policy": policy}).execute()
        )
        return updated

    def billing_accounts(self, *, credentials=None, open_only: bool = True) -> list[BillingAccount]:
        """List billing accounts scoped to this organization.

        Parameters
        ----------
        credentials : Credentials, optional
            Explicit credentials to use. If ``None``, uses stored credentials or ADC.
        open_only : bool, optional
            If ``True`` (default), return only billing accounts whose status is
            open. If ``False``, include closed accounts as well.

        Returns
        -------
        list[BillingAccount]
            Billing accounts linked to this organization.

        Raises
        ------
        googleapiclient.errors.HttpError
            If the API call fails.

        Examples
        --------
        >>> org = list_organizations()[0]  # doctest: +SKIP
        >>> [b.display_name for b in org.billing_accounts()]  # doctest: +SKIP
        ['My Billing Account', ...]
        """
        creds = self._get_credentials(credentials=credentials)

        # Build the Cloud Billing V1 service client
        billing_service = cloud_billing(creds)

        billing_accounts = []

        # List billing accounts with parent filter
        request = billing_service.billingAccounts().list(parent=self.resource_name)

        # Handle pagination
        while request is not None:
            response = request.execute()

            for account in response.get("billingAccounts", []):
                # Extract billing account ID from resource name
                # Format is "billingAccounts/012345-567890-ABCDEF"
                billing_account_id = account["name"].split("/")[1]
                display_name = account.get("displayName", billing_account_id)
                is_open = account.get("open", False)
                status = "OPEN" if is_open else "CLOSED"

                # Respect open_only filter
                if open_only and not is_open:
                    continue

                billing_accounts.append(
                    BillingAccount(id=billing_account_id, display_name=display_name, status=status)
                )

            # Get next page
            request = billing_service.billingAccounts().list_next(
                previous_request=request, previous_response=response
            )

        return billing_accounts

    @classmethod
    def lookup(cls, org_id: str, *, credentials: Optional[Credentials] = None) -> "Organization":
        """Return an Organization by id using CRM v3.

        Parameters
        ----------
        org_id : str
            Numeric organization id (e.g., ``"123456789"``).
        credentials : Credentials, optional
            Explicit credentials to use. If ``None``, uses ADC.

        Returns
        -------
        Organization
            Populated organization resource.

        Raises
        ------
        googleapiclient.errors.HttpError
            If the organization is not found or the API call fails.
        """
        # Get credentials if not provided
        if credentials is None:
            credentials, _ = google.auth.default()

        # Build the Resource Manager V3 service client
        crm_service = crm_v3(credentials)

        # Get the organization details
        resource_name = f"organizations/{org_id}"
        org_resource = crm_service.organizations().get(name=resource_name).execute()

        # Create and return the Organization object
        return cls(
            id=org_id,
            resource_name=resource_name,
            display_name=org_resource.get("displayName", ""),
            _credentials=credentials,
        )


@dataclass
class Folder(Container):
    """Information about a GCP folder.

    Attributes:
        id: The folder ID (numeric string)
        resource_name: The resource name (e.g., "folders/123456789")
        display_name: The human-readable display name
        parent_resource_name: The parent resource name (e.g., "organizations/123" or "folders/456")
        _credentials: Optional Google Cloud credentials to use for API calls
    """

    parent_resource_name: str = ""

    def parent(self, *, credentials=None) -> Optional[Container]:
        """Get the parent container.

        Args:
            credentials: Google Cloud credentials to use. If None, uses stored credentials or ADC.

        Returns:
            The parent Container (Organization or Folder), or None if parent cannot be determined
        """
        if not self.parent_resource_name:
            return None

        creds = self._get_credentials(credentials=credentials)
        crm_service = crm_v3(creds)

        # Parse the parent resource name
        if self.parent_resource_name.startswith("organizations/"):
            org_id = self.parent_resource_name.split("/")[1]
            return Organization.lookup(org_id, credentials=creds)
        elif self.parent_resource_name.startswith("folders/"):
            folder_resource = crm_service.folders().get(name=self.parent_resource_name).execute()
            return Folder(
                id=folder_resource["name"].split("/")[1],
                resource_name=folder_resource["name"],
                display_name=folder_resource.get("displayName", ""),
                parent_resource_name=folder_resource.get("parent", ""),
                _credentials=creds,
            )

        return None

    def folders(self, *, credentials=None) -> list[Folder]:
        """List direct child folders of this folder.

        Parameters
        ----------
        credentials : Credentials, optional
            Explicit credentials to use. If ``None``, uses stored credentials or ADC.

        Returns
        -------
        list[Folder]
            Direct child folders of this folder.
        """
        creds = self._get_credentials(credentials=credentials)

        crm_service = crm_v3(creds)

        folders = []
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

            request = crm_service.folders().list_next(
                previous_request=request, previous_response=response
            )

        return folders

    def projects(self, *, credentials=None) -> list[Project]:
        """List direct child projects of this folder.

        Parameters
        ----------
        credentials : Credentials, optional
            Explicit credentials to use. If ``None``, uses stored credentials or ADC.

        Returns
        -------
        list[Project]
            Direct child projects of this folder.
        """
        creds = self._get_credentials(credentials=credentials)

        crm_service = crm_v3(creds)

        projects = []
        # Filter projects by parent folder
        request = crm_service.projects().list(parent=self.resource_name)

        while request is not None:
            response = request.execute()
            for project in response.get("projects", []):
                projects.append(
                    _project_from_api_response(project, parent=self, credentials=creds)
                )

            request = crm_service.projects().list_next(
                previous_request=request, previous_response=response
            )

        return projects

    def create_folder(self, display_name: str, *, credentials=None) -> Folder:
        """Create a folder directly under this folder.

        Parameters
        ----------
        display_name : str
            The display name for the new folder.
        credentials : Credentials, optional
            Explicit credentials to use. If ``None``, uses stored credentials or ADC.

        Returns
        -------
        Folder
            The created folder resource.

        Raises
        ------
        googleapiclient.errors.HttpError
            If the API call fails.
        """
        creds = self._get_credentials(credentials=credentials)

        crm_service = crm_v3(creds)

        # Create folder request body
        folder_body = {
            "displayName": display_name,
            "parent": self.resource_name,
        }

        # Call the folders.create() method
        operation = crm_service.folders().create(
            body=folder_body
        ).execute()

        # Wait for the operation to complete (folders.create returns a long-running operation)
        # The operation name is in the format "operations/..."
        while not operation.get("done", False):
            import time

            time.sleep(1)
            operation = crm_service.operations().get(name=operation["name"]).execute()

        # Extract the folder from the operation response
        folder_resource_name = operation["response"]["name"]
        folder_id = folder_resource_name.split("/")[1]

        # Return a Folder object
        return Folder(
            id=folder_id,
            resource_name=folder_resource_name,
            display_name=display_name,
            parent_resource_name=self.resource_name,
            _credentials=creds,
        )


@dataclass
class Project(Resource):
    """Information about a GCP project.

    Attributes:
        id: The project ID (e.g., "my-project-123")
        name: The human-readable project name
        project_number: The project number (numeric string)
        lifecycle_state: The lifecycle state (e.g., "ACTIVE", "DELETE_REQUESTED")
        parent: The parent Container (Organization, Folder, or NO_ORG)
        _credentials: Optional Google Cloud credentials to use for API calls
    """

    id: str
    name: str
    project_number: str
    lifecycle_state: str
    parent: Container
    _credentials: Optional[Credentials] = field(default=None, repr=False, compare=False)

    def full_resource_name(self) -> str:
        return f"projects/{self.id}"

    def enabled_apis(self, *, credentials=None) -> list[str]:
        """List enabled APIs for this project.

        Parameters
        ----------
        credentials : Credentials, optional
            Explicit credentials to use. If ``None``, uses stored credentials or ADC.

        Returns
        -------
        list[str]
            Service names, e.g., ``['compute.googleapis.com', 'storage.googleapis.com']``.

        Raises
        ------
        googleapiclient.errors.HttpError
            If the API call fails.

        Examples
        --------
        >>> from pdum.gcp.admin import quota_project
        >>> quota_project().enabled_apis()  # doctest: +SKIP
        ['compute.googleapis.com', ...]
        """
        creds = self._get_credentials(credentials=credentials)

        # Build the Service Usage V1 service client
        service_usage_client = service_usage(creds)

        enabled_apis = []

        # List services with filter for enabled state
        parent_name = f"projects/{self.id}"
        request = service_usage_client.services().list(parent=parent_name, filter="state:ENABLED")

        # Handle pagination
        while request is not None:
            response = request.execute()

            for service in response.get("services", []):
                # Extract the API service name from config
                # The 'config.name' field contains the service name (e.g., compute.googleapis.com)
                api_name = service.get("config", {}).get("name", "")
                if api_name:
                    enabled_apis.append(api_name)

            # Get next page
            request = service_usage_client.services().list_next(
                previous_request=request, previous_response=response
            )

        return enabled_apis

    def enable_apis(
        self,
        api_list: list[str],
        *,
        credentials=None,
        timeout: float = 300.0,
        verbose: bool = True,
        polling_interval: float = 5.0,
    ) -> dict:
        """Enable multiple APIs for this project using batch enable.

        Polls the long-running operation until completion or timeout.

        Parameters
        ----------
        api_list : list[str]
            Service ids to enable.
        credentials : Credentials, optional
            Explicit credentials to use. If ``None``, uses stored credentials or ADC.
        timeout : float, default 300.0
            Maximum number of seconds to wait for completion.
        verbose : bool, default True
            If ``True``, prints progress dots while polling.
        polling_interval : float, default 5.0
            Seconds between polls.

        Returns
        -------
        dict
            The completed operation resource.

        Raises
        ------
        googleapiclient.errors.HttpError
            If the API call fails.
        TimeoutError
            If the operation times out.
        RuntimeError
            If the operation completes with an error status.
        """
        import time

        creds = self._get_credentials(credentials=credentials)

        # Build the Service Usage V1 service client
        service_usage_client = service_usage(creds)

        # Prepare the batch enable request
        parent_name = f"projects/{self.id}"
        request_body = {"serviceIds": api_list}

        # Call batchEnable to initiate the operation
        operation = (
            service_usage_client.services()
            .batchEnable(parent=parent_name, body=request_body)
            .execute()
        )

        operation_name = operation.get("name")
        if verbose:
            print(
                f"Enabling {len(api_list)} APIs for project {self.id}... ",
                end="",
                flush=True,
            )

        # Poll the operation until it's done or timeout
        start_time = time.time()

        while True:
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > timeout:
                if verbose:
                    print()  # New line after dots
                raise TimeoutError(
                    f"Operation timed out after {timeout} seconds. "
                    f"Operation name: {operation_name}"
                )

            # Get operation status
            operation = service_usage_client.operations().get(name=operation_name).execute()

            # Check if operation is done
            if operation.get("done", False):
                if verbose:
                    print()  # New line after dots

                # Check for errors
                if "error" in operation:
                    error = operation["error"]
                    error_message = error.get("message", "Unknown error")
                    error_code = error.get("code", "Unknown")
                    raise RuntimeError(
                        f"Operation failed with error code {error_code}: {error_message}"
                    )

                # Operation completed successfully
                return operation

            # Print dot if verbose
            if verbose:
                print(".", end="", flush=True)

            # Wait before next poll
            time.sleep(polling_interval)

    def billing_account(self, *, credentials=None) -> BillingAccount:
        """Return the project's billing account or ``NO_BILLING_ACCOUNT``.

        Parameters
        ----------
        credentials : Credentials, optional
            Explicit credentials to use. If ``None``, uses stored credentials or ADC.

        Returns
        -------
        BillingAccount
            The associated billing account, or the ``NO_BILLING_ACCOUNT`` sentinel
            if billing is disabled or no account is linked.

        Raises
        ------
        googleapiclient.errors.HttpError
            If the API call fails.

        Examples
        --------
        >>> project = Project(  # doctest: +SKIP
        ...     id='x', name='x', project_number='1', lifecycle_state='ACTIVE', parent=NO_ORG
        ... )
        >>> project.billing_account()  # doctest: +SKIP
        NO_BILLING_ACCOUNT
        """
        creds = self._get_credentials(credentials=credentials)

        # Build the Cloud Billing V1 service client
        billing_service = cloud_billing(creds)

        # Get the project's billing info
        resource_name = f"projects/{self.id}"
        billing_info = billing_service.projects().getBillingInfo(name=resource_name).execute()

        # Check if billing is enabled and account exists
        billing_enabled = billing_info.get("billingEnabled", False)
        billing_account_name = billing_info.get("billingAccountName", "")

        if not billing_enabled or not billing_account_name:
            return NO_BILLING_ACCOUNT

        # Extract the billing account ID from the resource name
        # Format is "billingAccounts/012345-567890-ABCDEF"
        billing_account_id = billing_account_name.split("/")[1]

        # Get the billing account details to retrieve the display name
        billing_account_info = (
            billing_service.billingAccounts().get(name=billing_account_name).execute()
        )

        display_name = billing_account_info.get("displayName", billing_account_id)
        is_open = billing_account_info.get("open", False)
        status = "OPEN" if is_open else "CLOSED"

        return BillingAccount(id=billing_account_id, display_name=display_name, status=status)

    @classmethod
    def lookup(cls, project_id: str, *, credentials: Optional[Credentials] = None) -> "Project":
        """Return a Project by id using CRM v3 and resolve its parent.

        Parameters
        ----------
        project_id : str
            Project id (e.g., ``"my-project-123"``).
        credentials : Credentials, optional
            Explicit credentials to use. If ``None``, uses ADC.

        Returns
        -------
        Project
            Populated project with parent Container (Organization, Folder, or NO_ORG).

        Raises
        ------
        googleapiclient.errors.HttpError
            If the project is not found or the API call fails.
        FileNotFoundError
            If the project is not found.
        ValueError
            If multiple projects are found for the given ID.
        """
        # Get credentials if not provided
        if credentials is None:
            credentials, _ = google.auth.default()

        # Build the Resource Manager V3 service client
        crm_service = crm_v3(credentials)

        # Search for the project by its ID
        request = crm_service.projects().search(query=f"id:{project_id}")
        response = request.execute()

        projects = response.get("projects", [])
        if not projects:
            raise FileNotFoundError(f"Project with ID '{project_id}' not found.")
        if len(projects) > 1:
            # This should not happen for a project ID search, but handle it just in case
            raise ValueError(f"Found multiple projects with ID '{project_id}'.")

        project_resource = projects[0]

        # Determine the parent container
        parent_resource_name = project_resource.get("parent")

        if parent_resource_name and parent_resource_name.startswith("organizations/"):
            org_id = parent_resource_name.split("/")[1]
            parent = Organization.lookup(org_id, credentials=credentials)
        elif parent_resource_name and parent_resource_name.startswith("folders/"):
            # Use crm_v3 to get folder details
            folder_resource = crm_service.folders().get(name=parent_resource_name).execute()
            parent = Folder(
                id=folder_resource["name"].split("/")[1],
                resource_name=folder_resource["name"],
                display_name=folder_resource.get("displayName", ""),
                parent_resource_name=folder_resource.get("parent", ""),
                _credentials=credentials,
            )
        else:
            # No organization or folder parent
            from pdum.gcp.types import NO_ORG

            parent = NO_ORG

        # Create and return the Project object
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
        """Suggest a valid GCP project id using an optional prefix.

        Generates names that follow GCP conventions:
        6–30 characters, lowercase letters, digits, and hyphens; must start with
        a lowercase letter.

        Parameters
        ----------
        prefix : str, optional
            If provided, used as the leading component (must start with a
            lowercase letter). If omitted, an adjective-animal slug is generated.
        random_digits : int, default 5
            Number of random digits to append (0–10). If 0, no digits are appended.

        Returns
        -------
        str
            A suggested project id string.

        Raises
        ------
        ValueError
            If ``prefix`` is invalid or ``random_digits`` is outside 0–10, or the
            final length violates GCP limits.
        """
        import random

        import coolname

        # Validate random_digits
        if not 0 <= random_digits <= 10:
            raise ValueError("random_digits must be between 0 and 10")

        # Generate or validate prefix
        if prefix is None:
            # Use coolname to generate adjective-animal name
            prefix = coolname.generate_slug(2)  # Generates "adjective-animal"
        else:
            # Validate prefix starts with lowercase letter
            if not prefix or not prefix[0].islower() or not prefix[0].isalpha():
                raise ValueError("prefix must start with a lowercase letter")

        # Build the final name
        if random_digits > 0:
            # Generate random digits
            digits = "".join(str(random.randint(0, 9)) for _ in range(random_digits))
            name = f"{prefix}-{digits}"
        else:
            name = prefix

        # Validate final name length (GCP requires 6-30 characters)
        if len(name) < 6 or len(name) > 30:
            raise ValueError(
                f"Generated name '{name}' is {len(name)} characters, "
                f"but GCP project IDs must be 6-30 characters long"
            )

        return name

    def list_roles(self, *, credentials=None) -> list[Role]:
        """List the IAM roles for the current user on this project.

        Args:
            credentials: Google Cloud credentials to use. If None, uses stored credentials or ADC.

        Returns:
            A list of Role objects.
        """
        creds = self._get_credentials(credentials=credentials)
        from pdum.gcp._helpers import _list_roles
        return _list_roles(credentials=creds, resource_name=f"projects/{self.id}")

    def add_user_as_owner(self, user_email: str, *, credentials=None) -> dict:
        """Add a user to the project's Owners (roles/owner) binding.

        This updates the project's IAM policy by adding ``user:{email}`` to the
        ``roles/owner`` binding. If the user is already present, returns the
        current policy unchanged.

        Parameters
        ----------
        user_email : str
            The user's email address (e.g., ``"user@example.com"``). The
            ``user:`` prefix is added automatically.
        credentials : Credentials, optional
            Explicit credentials to use. If ``None``, uses stored credentials or ADC.

        Returns
        -------
        dict
            The updated (or current, if no change) IAM policy as a dictionary.

        Raises
        ------
        ValueError
            If ``user_email`` does not appear to be a valid email address.
        googleapiclient.errors.HttpError
            If the get/set policy API calls fail.

        Notes
        -----
        This method mutates GCP IAM policy on the project. Ensure you have the
        necessary permissions (e.g., Project IAM Admin/Owner). Not executed in CI.
        """
        if "@" not in user_email or not user_email.strip():
            raise ValueError("user_email must be a valid email address")

        member = f"user:{user_email.strip()}"
        role = "roles/owner"

        creds = self._get_credentials(credentials=credentials)
        crm = crm_v3(creds)
        resource = f"projects/{self.id}"

        # Request policy with version 3 to support conditions if present
        policy = (
            crm.projects()
            .getIamPolicy(resource=resource, body={"options": {"requestedPolicyVersion": 3}})
            .execute()
        )

        # Ensure version >= 3
        if policy.get("version", 0) < 3:
            policy["version"] = 3

        # Locate or create the owners binding
        bindings = policy.setdefault("bindings", [])
        owner_binding = next((b for b in bindings if b.get("role") == role), None)

        if owner_binding is None:
            owner_binding = {"role": role, "members": [member]}
            bindings.append(owner_binding)
        else:
            members = owner_binding.setdefault("members", [])
            if member in members:
                return policy  # already present, no change
            members.append(member)

        # Set the modified policy
        updated = (
            crm.projects().setIamPolicy(resource=resource, body={"policy": policy}).execute()
        )
        return updated

def _project_from_api_response(
    project_dict: dict, parent: Container, credentials: Optional[Credentials] = None
) -> Project:
    """Create a Project from API response data.

    Args:
        project_dict: Project data from the API
        parent: The parent Container
        credentials: Optional credentials to store in the project

    Returns:
        Project instance
    """
    return Project(
        id=project_dict["projectId"],
        name=project_dict.get("name", ""),
        project_number=project_dict.get("projectNumber", ""),
        lifecycle_state=project_dict.get("lifecycleState", ""),
        parent=parent,
        _credentials=credentials,
    )


class _NoOrgSentinel(Container):
    """Sentinel subclass of Container to represent projects with no organization parent.

    This sentinel is used to explicitly indicate that a project should be created
    without an organization or folder parent, typically for personal GCP accounts.

    This is distinct from None, which might indicate "use the default" or "not specified".

    Being a subclass of Container allows it to be used uniformly in type hints
    and isinstance checks.
    """

    _instance: Optional[_NoOrgSentinel] = None

    def __new__(cls):
        if cls._instance is None:
            # Create instance without calling __init__ to avoid dataclass requirements
            instance = object.__new__(cls)
            # Manually set the Container fields
            instance.id = ""
            instance.resource_name = "NO_ORG"
            instance.display_name = "No Organization"
            instance._credentials = None
            cls._instance = instance
        return cls._instance

    def __init__(self):
        # Override __init__ to prevent dataclass __init__ from being called
        # The instance is already initialized in __new__
        pass

    def __repr__(self) -> str:
        return "NO_ORG"

    def __str__(self) -> str:
        return "NO_ORG"

    def __bool__(self) -> bool:
        # Always returns False so it can be used in boolean contexts
        return False

    def parent(self, *, credentials=None) -> Optional[Container]:
        """Get the parent container.

        NO_ORG has no parent.

        Args:
            credentials: Google Cloud credentials to use (ignored)

        Returns:
            None
        """
        return None

    def folders(self, *, credentials=None) -> list[Folder]:
        """List folders that are direct children of NO_ORG.

        NO_ORG cannot have folders as children.

        Args:
            credentials: Google Cloud credentials to use (ignored)

        Returns:
            Empty list (NO_ORG has no folders)
        """
        return []

    def create_folder(self, display_name: str, *, credentials=None) -> Folder:
        """Create a new folder as a child of NO_ORG.

        NO_ORG cannot have folders as children.

        Args:
            display_name: The human-readable name for the folder (ignored)
            credentials: Google Cloud credentials to use (ignored)

        Raises:
            TypeError: Always raised because NO_ORG cannot have folders
        """
        raise TypeError(
            "NO_ORG cannot have folders. Projects without an organization parent "
            "cannot contain folders. To create a folder, you must first create or "
            "use an existing organization or folder as the parent."
        )

    def cd(self, path: str, *, credentials=None) -> Folder:
        """Navigate to a folder at the given path.

        NO_ORG cannot have folders, so cd is not supported.

        Args:
            path: The folder path (ignored)
            credentials: Google Cloud credentials to use (ignored)

        Raises:
            TypeError: Always raised because NO_ORG cannot have folders
        """
        raise TypeError(
            "NO_ORG cannot have folders. Projects without an organization parent "
            "cannot contain folders. Use cd() on an organization or folder instead."
        )

    def projects(self, *, credentials=None) -> list[Project]:
        """List projects that have no organization or folder parent.

        This method lists projects that are not under an organization or folder,
        typically projects in personal GCP accounts.

        Args:
            credentials: Google Cloud credentials to use. If None, uses stored credentials or ADC.

        Returns:
            List of Project objects representing projects without organization parents

        Raises:
            google.auth.exceptions.DefaultCredentialsError: If no credentials can be found
            googleapiclient.errors.HttpError: If the API call fails

        Example:
            >>> from pdum.gcp import NO_ORG
            >>> projects = NO_ORG.projects()
            >>> for project in projects:
            ...     print(f"Project: {project.name} ({project.id})")
            Project: My Project (my-project-123)
        """
        creds = self._get_credentials(credentials=credentials)

        crm_service = crm_v1(creds)

        projects = []
        request = crm_service.projects().list()

        while request is not None:
            response = request.execute()
            for project in response.get("projects", []):
                # Check the project's 'parent' field
                parent = project.get("parent", {})
                parent_type = parent.get("type")

                # Projects under a personal/no-org account will *not* have a parent
                # of type 'organization' or 'folder'
                if not parent_type or parent_type not in ("organization", "folder"):
                    projects.append(_project_from_api_response(project, parent=self, credentials=creds))

            request = crm_service.projects().list_next(
                previous_request=request, previous_response=response
            )

        return projects

    # Keep the old method name for backward compatibility
    def list_projects(self, *, credentials=None) -> list[Project]:
        """Deprecated: Use projects() instead.

        This method is kept for backward compatibility.

        Args:
            credentials: Google Cloud credentials to use. If None, uses stored credentials or ADC.
        """
        return self.projects(credentials=credentials)

    def billing_accounts(self, *, credentials=None, open_only: bool = True) -> list[BillingAccount]:
        """List all billing accounts visible to the user.

        For NO_ORG (projects without an organization), this returns all billing accounts
        that the authenticated user has permission to view, regardless of their parent
        organization. This is useful for personal GCP accounts or when working across
        multiple organizations.

        The user must have the "Billing Account Viewer" role to see billing accounts.

        Args:
            credentials: Google Cloud credentials to use. If None, uses stored credentials or ADC.
            open_only: If True (default), include only open accounts.

        Returns:
            List of all BillingAccount objects visible to the user

        Raises:
            googleapiclient.errors.HttpError: If the API call fails

        Example:
            >>> from pdum.gcp import NO_ORG
            >>> billing_accounts = NO_ORG.billing_accounts()
            >>> for account in billing_accounts:
            ...     print(f"{account.display_name}: {account.id}")
            Personal Billing: 012345-567890-ABCDEF
        """
        creds = self._get_credentials(credentials=credentials)

        # Build the Cloud Billing V1 service client
        billing_service = cloud_billing(creds)

        billing_accounts = []

        # List all billing accounts without parent filter
        # This returns all billing accounts the user has permission to view
        request = billing_service.billingAccounts().list()

        # Handle pagination
        while request is not None:
            response = request.execute()

            for account in response.get("billingAccounts", []):
                # Extract billing account ID from resource name
                # Format is "billingAccounts/012345-567890-ABCDEF"
                billing_account_id = account["name"].split("/")[1]
                display_name = account.get("displayName", billing_account_id)
                is_open = account.get("open", False)
                status = "OPEN" if is_open else "CLOSED"

                if not open_only or is_open:
                    billing_accounts.append(
                        BillingAccount(id=billing_account_id, display_name=display_name, status=status)
                    )

            # Get next page
            request = billing_service.billingAccounts().list_next(
                previous_request=request, previous_response=response
            )

        return billing_accounts


# Singleton instance for representing "no organization"
NO_ORG = _NoOrgSentinel()


class _NoBillingAccountSentinel(BillingAccount):
    """Sentinel subclass of BillingAccount to represent projects with no billing account.

    This sentinel is used to explicitly indicate that a project does not have a billing
    account associated with it, or that the billing account is closed/disabled.

    This is distinct from None, which might indicate "not yet fetched" or "unknown".

    Being a subclass of BillingAccount allows it to be used uniformly in type hints
    and isinstance checks.
    """

    _instance: Optional[_NoBillingAccountSentinel] = None

    def __new__(cls):
        if cls._instance is None:
            # Create instance without calling __init__ to avoid dataclass requirements
            instance = object.__new__(cls)
            # Manually set the BillingAccount fields
            instance.id = ""
            instance.display_name = "No Billing Account"
            instance.status = ""
            cls._instance = instance
        return cls._instance

    def __init__(self):
        # Override __init__ to prevent dataclass __init__ from being called
        # The instance is already initialized in __new__
        pass

    def __repr__(self) -> str:
        return "NO_BILLING_ACCOUNT"

    def __str__(self) -> str:
        return "NO_BILLING_ACCOUNT"

    def __bool__(self) -> bool:
        # Always returns False so it can be used in boolean contexts
        return False


# Singleton instance for representing "no billing account"
NO_BILLING_ACCOUNT = _NoBillingAccountSentinel()
