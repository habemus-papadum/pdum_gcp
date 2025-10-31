"""Type definitions for GCP resources.

This module contains dataclasses and type definitions for GCP resources
like organizations, folders, and projects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

import google.auth
from google.auth.credentials import Credentials
from googleapiclient import discovery

if TYPE_CHECKING:
    pass


@dataclass
class BillingAccount:
    """Information about a GCP billing account.

    Attributes:
        id: The billing account ID (e.g., "012345-567890-ABCDEF")
        display_name: The human-readable display name for the billing account
    """

    id: str
    display_name: str

    def __bool__(self) -> bool:
        """Return True for regular billing accounts."""
        return True


@dataclass
class Container:
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

    def _get_credentials(self, credentials: Optional[Credentials] = None) -> Credentials:
        """Get credentials for API calls.

        Args:
            credentials: Explicit credentials to use

        Returns:
            Credentials in order of preference: explicit > stored > ADC
        """
        if credentials is not None:
            return credentials
        if self._credentials is not None:
            return self._credentials
        creds, _ = google.auth.default()
        return creds

    def parent(self, credentials=None) -> Optional[Container]:
        """Get the parent container.

        Returns:
            The parent Container (Organization or Folder), or None if no parent

        Raises:
            NotImplementedError: Subclasses must implement this method
        """
        raise NotImplementedError("Subclasses must implement parent()")

    def folders(self, credentials=None) -> list[Folder]:
        """List folders that are direct children of this container.

        Args:
            credentials: Google Cloud credentials to use. If None, uses Application Default Credentials.

        Returns:
            List of Folder objects that are direct children

        Raises:
            NotImplementedError: Subclasses must implement this method
        """
        raise NotImplementedError("Subclasses must implement folders()")

    def projects(self, credentials=None) -> list[Project]:
        """List projects that are direct children of this container.

        Args:
            credentials: Google Cloud credentials to use. If None, uses Application Default Credentials.

        Returns:
            List of Project objects that are direct children

        Raises:
            NotImplementedError: Subclasses must implement this method
        """
        raise NotImplementedError("Subclasses must implement projects()")

    def create_folder(self, display_name: str, credentials=None) -> Folder:
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

    def tree(self, credentials=None, _prefix: str = "", _is_last: bool = True) -> None:
        """Print a tree view of this container and all its children.

        This method recursively prints a visual tree structure showing:
        - The current container (with 🌺 for organizations, 🎸 for folders, 🐞 for NO_ORG)
        - All child folders (with 🎸)
        - All child projects (with 🎵)

        The tree uses unicode box-drawing characters:
        - ├── for branches
        - └── for the last item
        - │   for vertical continuation
        - "    " for empty space

        Args:
            credentials: Google Cloud credentials to use. If None, uses stored credentials or ADC.
            _prefix: Internal parameter for indentation (do not use)
            _is_last: Internal parameter for branch drawing (do not use)

        Example:
            >>> from pdum.gcp import list_organizations
            >>> orgs = list_organizations()
            >>> for org in orgs:
            ...     org.tree()
            🌺 My Organization (organizations/123456789)
            ├── 🎸 Development (folders/111)
            │   ├── 🎵 dev-project-1 (ACTIVE)
            │   └── 🎵 dev-project-2 (ACTIVE)
            ├── 🎸 Production (folders/222)
            │   └── 🎵 prod-project-1 (ACTIVE)
            └── 🎵 shared-project (ACTIVE)
        """
        creds = self._get_credentials(credentials)

        # Determine the emoji based on the container type (whimsical and colorful!)
        if self is NO_ORG:
            emoji = "🐞"  # Ladybug - free-floating projects
        elif isinstance(self, Organization):
            emoji = "🌺"  # Hibiscus - beautiful organization flower
        else:  # Folder
            emoji = "🎸"  # Guitar - folders rock!

        # Print the current container
        print(f"{_prefix}{emoji} {self.display_name} ({self.resource_name})")

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

    def _tree_children(self, credentials=None, _prefix: str = "") -> None:
        """Internal helper to print children without printing the parent again.

        Args:
            credentials: Google Cloud credentials to use
            _prefix: The prefix for indentation
        """
        creds = self._get_credentials(credentials)

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


@dataclass
class Organization(Container):
    """Information about a GCP organization.

    Attributes:
        id: The organization ID (numeric string)
        resource_name: The resource name (e.g., "organizations/123456789")
        display_name: The human-readable display name
    """

    def parent(self, credentials=None) -> Optional[Container]:
        """Get the parent container.

        Organizations are root-level resources and have no parent.

        Returns:
            None (organizations have no parent)
        """
        return None

    def folders(self, credentials=None) -> list[Folder]:
        """List folders that are direct children of this organization.

        Args:
            credentials: Google Cloud credentials to use. If None, uses stored credentials or ADC.

        Returns:
            List of Folder objects that are direct children of this organization
        """
        creds = self._get_credentials(credentials)

        crm_service = discovery.build(
            "cloudresourcemanager", "v2", credentials=creds, cache_discovery=False
        )

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

    def projects(self, credentials=None) -> list[Project]:
        """List projects that are direct children of this organization.

        Args:
            credentials: Google Cloud credentials to use. If None, uses stored credentials or ADC.

        Returns:
            List of Project objects that are direct children of this organization
        """
        creds = self._get_credentials(credentials)

        crm_service = discovery.build(
            "cloudresourcemanager", "v1", credentials=creds, cache_discovery=False
        )

        projects = []
        # Filter projects by parent organization
        request = crm_service.projects().list(
            filter=f"parent.type:organization parent.id:{self.id}"
        )

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

    def create_folder(self, display_name: str, credentials=None) -> Folder:
        """Create a new folder as a child of this organization.

        Args:
            display_name: The human-readable name for the folder
            credentials: Google Cloud credentials to use. If None, uses stored credentials or ADC.

        Returns:
            A Folder object representing the newly created folder

        Raises:
            googleapiclient.errors.HttpError: If the API call fails
        """
        creds = self._get_credentials(credentials)

        crm_service = discovery.build(
            "cloudresourcemanager", "v2", credentials=creds, cache_discovery=False
        )

        # Create folder request body
        # Note: parent is passed as a parameter, not in the body
        folder_body = {
            "displayName": display_name,
        }

        # Call the folders.create() method
        # parent parameter is required and separate from the body
        operation = crm_service.folders().create(
            body=folder_body,
            parent=self.resource_name
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

    def parent(self, credentials=None) -> Optional[Container]:
        """Get the parent container.

        Returns:
            The parent Container (Organization or Folder), or None if parent cannot be determined

        Args:
            credentials: Google Cloud credentials to use. If None, uses stored credentials or ADC.
        """
        if not self.parent_resource_name:
            return None

        creds = self._get_credentials(credentials)

        # Parse the parent resource name
        if self.parent_resource_name.startswith("organizations/"):
            org_id = self.parent_resource_name.split("/")[1]
            crm_service = discovery.build(
                "cloudresourcemanager", "v1", credentials=creds, cache_discovery=False
            )

            org = crm_service.organizations().get(name=self.parent_resource_name).execute()
            return Organization(
                id=org_id,
                resource_name=self.parent_resource_name,
                display_name=org.get("displayName", ""),
                _credentials=creds,
            )
        elif self.parent_resource_name.startswith("folders/"):
            folder_id = self.parent_resource_name.split("/")[1]
            crm_service = discovery.build(
                "cloudresourcemanager", "v2", credentials=creds, cache_discovery=False
            )

            folder = crm_service.folders().get(name=self.parent_resource_name).execute()
            return Folder(
                id=folder_id,
                resource_name=self.parent_resource_name,
                display_name=folder.get("displayName", ""),
                parent_resource_name=folder.get("parent", ""),
                _credentials=creds,
            )

        return None

    def folders(self, credentials=None) -> list[Folder]:
        """List folders that are direct children of this folder.

        Args:
            credentials: Google Cloud credentials to use. If None, uses stored credentials or ADC.

        Returns:
            List of Folder objects that are direct children of this folder
        """
        creds = self._get_credentials(credentials)

        crm_service = discovery.build(
            "cloudresourcemanager", "v2", credentials=creds, cache_discovery=False
        )

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

    def projects(self, credentials=None) -> list[Project]:
        """List projects that are direct children of this folder.

        Args:
            credentials: Google Cloud credentials to use. If None, uses stored credentials or ADC.

        Returns:
            List of Project objects that are direct children of this folder
        """
        creds = self._get_credentials(credentials)

        crm_service = discovery.build(
            "cloudresourcemanager", "v1", credentials=creds, cache_discovery=False
        )

        projects = []
        # Filter projects by parent folder
        request = crm_service.projects().list(filter=f"parent.type:folder parent.id:{self.id}")

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

    def create_folder(self, display_name: str, credentials=None) -> Folder:
        """Create a new folder as a child of this folder.

        Args:
            display_name: The human-readable name for the folder
            credentials: Google Cloud credentials to use. If None, uses stored credentials or ADC.

        Returns:
            A Folder object representing the newly created folder

        Raises:
            googleapiclient.errors.HttpError: If the API call fails
        """
        creds = self._get_credentials(credentials)

        crm_service = discovery.build(
            "cloudresourcemanager", "v2", credentials=creds, cache_discovery=False
        )

        # Create folder request body
        # Note: parent is passed as a parameter, not in the body
        folder_body = {
            "displayName": display_name,
        }

        # Call the folders.create() method
        # parent parameter is required and separate from the body
        operation = crm_service.folders().create(
            body=folder_body,
            parent=self.resource_name
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
class Project:
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

    def _get_credentials(self, credentials: Optional[Credentials] = None) -> Credentials:
        """Get credentials for API calls.

        Args:
            credentials: Explicit credentials to use

        Returns:
            Credentials in order of preference: explicit > stored > ADC
        """
        if credentials is not None:
            return credentials
        if self._credentials is not None:
            return self._credentials
        creds, _ = google.auth.default()
        return creds

    def billing_account(self, credentials=None) -> BillingAccount:
        """Get the billing account associated with this project.

        This method retrieves the billing information for the project and returns
        the associated billing account. If the project does not have a billing
        account (billing is disabled or account is closed), returns NO_BILLING_ACCOUNT.

        Args:
            credentials: Google Cloud credentials to use. If None, uses stored credentials or ADC.

        Returns:
            A BillingAccount object representing the billing account, or NO_BILLING_ACCOUNT
            if the project has no billing account

        Raises:
            googleapiclient.errors.HttpError: If the API call fails

        Example:
            >>> project = org.projects()[0]
            >>> billing = project.billing_account()
            >>> if billing:
            ...     print(f"Billing Account: {billing.display_name}")
            ... else:
            ...     print("No billing account")
        """
        creds = self._get_credentials(credentials)

        # Build the Cloud Billing V1 service client
        billing_service = discovery.build(
            "cloudbilling", "v1", credentials=creds, cache_discovery=False
        )

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

        return BillingAccount(id=billing_account_id, display_name=display_name)

    @classmethod
    def suggest_name(cls, *, prefix: Optional[str] = None, random_digits: int = 5) -> str:
        """Suggest a GCP project name with optional prefix and random digits.

        This method generates project names that follow GCP naming conventions:
        - Must be 6-30 characters long
        - Can only contain lowercase letters, digits, and hyphens
        - Must start with a lowercase letter

        Args:
            prefix: Optional prefix for the project name. If None, generates a coolname
                   (adjective-animal format like "quick-fox"). If provided, must start
                   with a lowercase letter.
            random_digits: Number of random digits to append (0-10). Defaults to 5.
                          If > 0, appends a dash followed by the specified number of
                          random digits.

        Returns:
            A suggested project name string

        Raises:
            ValueError: If prefix doesn't start with a lowercase letter, or if
                       random_digits is not between 0-10

        Example:
            >>> Project.suggest_name()
            'quick-fox-12345'
            >>> Project.suggest_name(prefix='myapp')
            'myapp-67890'
            >>> Project.suggest_name(prefix='myapp', random_digits=0)
            'myapp'
            >>> Project.suggest_name(prefix='myapp', random_digits=8)
            'myapp-12345678'
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

    def parent(self, credentials=None) -> Optional[Container]:
        """Get the parent container.

        NO_ORG has no parent.

        Returns:
            None
        """
        return None

    def folders(self, credentials=None) -> list[Folder]:
        """List folders that are direct children of NO_ORG.

        NO_ORG cannot have folders as children.

        Returns:
            Empty list (NO_ORG has no folders)
        """
        return []

    def create_folder(self, display_name: str, credentials=None) -> Folder:
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

    def projects(self, credentials=None) -> list[Project]:
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
        creds = self._get_credentials(credentials)

        crm_service = discovery.build(
            "cloudresourcemanager", "v1", credentials=creds, cache_discovery=False
        )

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
    def list_projects(self, credentials=None) -> list[Project]:
        """Deprecated: Use projects() instead.

        This method is kept for backward compatibility.
        """
        return self.projects(credentials=credentials)


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
