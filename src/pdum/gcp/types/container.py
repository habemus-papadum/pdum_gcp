"""Container base class implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Generator, Optional

from google.auth.credentials import Credentials

from pdum.gcp._clients import crm_v3
from pdum.gcp._helpers import _list_roles

from .resource import Resource

if TYPE_CHECKING:
    from .billing_account import BillingAccount
    from .folder import Folder
    from .project import Project
    from .role import Role


@dataclass
class Container(Resource):
    """Base class for GCP resource containers (Organizations, Folders, and NO_ORG).

    This base class provides common functionality for all container types that can
    hold projects and folders.

    Attributes
    ----------
    id : str
        Container identifier (numeric for organizations/folders, empty for ``NO_ORG``).
    resource_name : str
        Fully-qualified resource name (e.g., ``"organizations/123"`` or ``"folders/456"``).
    display_name : str
        Human-readable label for the container.
    _credentials : Credentials, optional
        Cached credentials used for API calls when provided.
    """

    id: str
    resource_name: str
    display_name: str
    _credentials: Optional[Credentials] = field(default=None, repr=False, compare=False)

    def full_resource_name(self) -> str:
        return self.resource_name

    def parent(self, *, credentials: Optional[Credentials] = None) -> Optional[Container]:
        """Get the parent container.

        Parameters
        ----------
        credentials : Credentials, optional
            Explicit credentials to use. When omitted, stored credentials or ADC are used.

        Returns
        -------
        Container or None
            The parent container (organization or folder), or ``None`` if no parent exists.

        Raises
        ------
        NotImplementedError
            Always raised on the base class; subclasses must implement this method.
        """
        raise NotImplementedError("Subclasses must implement parent()")

    def folders(self, *, credentials: Optional[Credentials] = None) -> list[Folder]:
        """List folders that are direct children of this container.

        Parameters
        ----------
        credentials : Credentials, optional
            Explicit credentials to use. When omitted, stored credentials or ADC are used.

        Returns
        -------
        list[Folder]
            Direct child folders of this container.

        Raises
        ------
        NotImplementedError
            Always raised on the base class; subclasses must implement this method.
        """
        raise NotImplementedError("Subclasses must implement folders()")

    def projects(self, *, credentials: Optional[Credentials] = None) -> list[Project]:
        """List projects that are direct children of this container.

        Parameters
        ----------
        credentials : Credentials, optional
            Explicit credentials to use. When omitted, stored credentials or ADC are used.

        Returns
        -------
        list[Project]
            Direct child projects of this container.

        Raises
        ------
        NotImplementedError
            Always raised on the base class; subclasses must implement this method.
        """
        raise NotImplementedError("Subclasses must implement projects()")

    def create_folder(self, display_name: str, *, credentials: Optional[Credentials] = None) -> Folder:
        """Create a new folder as a child of this container.

        Parameters
        ----------
        display_name : str
            Human-readable name for the folder.
        credentials : Credentials, optional
            Explicit credentials to use. When omitted, stored credentials or ADC are used.

        Returns
        -------
        Folder
            The newly created folder.

        Raises
        ------
        NotImplementedError
            Always raised on the base class; subclasses must implement this method.
        """
        raise NotImplementedError("Subclasses must implement create_folder()")

    def list_roles(
        self,
        *,
        credentials: Optional[Credentials] = None,
        user_email: str | None = None,
    ) -> list[Role]:
        """List IAM roles for a user on this container.

        Parameters
        ----------
        credentials : Credentials, optional
            Explicit credentials to use. When omitted, stored credentials or ADC are used.
        user_email : str, optional
            Identity to query. If omitted, the email associated with the credentials is used.

        Returns
        -------
        list[Role]
            Roles that directly bind the user on this container.
        """
        creds = self._get_credentials(credentials=credentials)
        return _list_roles(credentials=creds, resource_name=self.resource_name, user_email=user_email)

    def create_project(
        self,
        project_id: str,
        display_name: str,
        *,
        billing_account: BillingAccount | str | None = None,
        credentials: Optional[Credentials] = None,
        timeout: float = 600.0,
        polling_interval: float = 5.0,
    ) -> Project:
        """Create a new project under this container and optionally attach billing.

        Parameters
        ----------
        project_id : str
            The new project's ID (must satisfy GCP constraints).
        display_name : str
            Human-friendly display name for the project.
        billing_account : BillingAccount | str | None, optional
            Billing account to attach after creation. If omitted or falsy (e.g., ``NO_BILLING_ACCOUNT``),
            billing is not attached.
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
        from .billing_account import NO_BILLING_ACCOUNT
        from .no_org import NO_ORG
        from .project import Project

        if billing_account is None:
            billing_account = NO_BILLING_ACCOUNT

        creds = self._get_credentials(credentials=credentials)
        crm = crm_v3(creds)

        body = {
            "projectId": project_id,
            "displayName": display_name,
        }

        is_no_org = (self is NO_ORG) or (getattr(self, "resource_name", "") == "NO_ORG")
        parent_name = None if is_no_org else self.resource_name
        if parent_name:
            body["parent"] = parent_name

        operation = crm.projects().create(body=body).execute()

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

        get_start = time.time()
        while True:
            try:
                crm.projects().get(name=f"projects/{project_id}").execute()
                break
            except Exception:
                if time.time() - get_start > timeout:
                    raise TimeoutError(f"Project get timed out after {timeout}s for 'projects/{project_id}'")
                time.sleep(polling_interval)

        if billing_account:
            Project.update_billing_account_for_id(project_id, billing_account, credentials=creds)

        search_start = time.time()
        while True:
            try:
                return Project.lookup(project_id, credentials=creds)
            except FileNotFoundError:
                if time.time() - search_start > timeout:
                    return Project(
                        id=project_id,
                        name=display_name,
                        project_number="",
                        lifecycle_state="",
                        parent=self,
                        _credentials=creds,
                    )
                time.sleep(polling_interval)

    def walk_projects(
        self,
        *,
        credentials: Optional[Credentials] = None,
        active_only: bool = True,
    ) -> Generator[Project, None, None]:
        """Recursively yield all projects within this container and its subfolders.

        Parameters
        ----------
        credentials : Credentials, optional
            Explicit credentials to use. When omitted, stored credentials or ADC are used.
        active_only : bool, default True
            If ``True``, yield only ``ACTIVE`` projects. If ``False``, yield all lifecycle states.

        Yields
        ------
        Project
            Projects discovered in this container and all nested folders.
        """
        creds = self._get_credentials(credentials=credentials)

        for project in self.projects(credentials=creds):
            if active_only and project.lifecycle_state != "ACTIVE":
                continue
            yield project

        for folder in self.folders(credentials=creds):
            yield from folder.walk_projects(credentials=creds, active_only=active_only)

    def tree(self, *, credentials: Optional[Credentials] = None, _prefix: str = "", _is_last: bool = True) -> None:
        """Print a visual tree of this container and its children."""
        from .no_org import NO_ORG

        creds = self._get_credentials(credentials=credentials)

        if self is NO_ORG:
            emoji = "🐞"
        elif self.__class__.__name__ == "Organization":
            emoji = "🌺"
        else:
            emoji = "🎸"

        print(f"{_prefix}{emoji} {self.display_name} ({self.resource_name})")
        self._tree_children(credentials=creds, _prefix=_prefix)

    def _tree_children(self, *, credentials: Optional[Credentials] = None, _prefix: str = "") -> None:
        """Internal helper to print children without printing the parent again."""
        from .project import Project

        creds = self._get_credentials(credentials=credentials)

        folders = self.folders(credentials=creds)
        projects = self.projects(credentials=creds)

        all_children = folders + projects  # type: ignore[arg-type]
        total_children = len(all_children)

        for idx, child in enumerate(all_children):
            is_last_child = idx == total_children - 1

            branch = "└── " if is_last_child else "├── "

            if isinstance(child, Project):
                print(f"{_prefix}{branch}🎵 {child.id} ({child.lifecycle_state})")
            else:
                extension = "    " if is_last_child else "│   "
                new_prefix = _prefix + extension

                print(f"{_prefix}{branch}🎸 {child.display_name} ({child.resource_name})")
                child._tree_children(credentials=creds, _prefix=new_prefix)

    def cd(self, path: str, *, credentials: Optional[Credentials] = None) -> Folder:
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
        """
        from .no_org import NO_ORG

        if self is NO_ORG:
            raise TypeError(
                "NO_ORG cannot have folders. Projects without an organization parent "
                "cannot contain folders. Use cd() on an organization or folder instead."
            )

        creds = self._get_credentials(credentials=credentials)

        clean_path = path.strip("/")
        if not clean_path:
            raise ValueError("Path cannot be empty")

        components = clean_path.split("/")
        current: Container = self

        for component in components:
            folders = current.folders(credentials=creds)

            matching_folder = next((folder for folder in folders if folder.display_name == component), None)
            if matching_folder is None:
                available = ", ".join(folder.display_name for folder in folders) or "(none)"
                raise ValueError(
                    f"Folder '{component}' not found in {current.display_name}. Available folders: {available}"
                )

            current = matching_folder

        return current  # type: ignore[return-value]


__all__ = ["Container"]
