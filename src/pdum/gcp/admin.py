"""Admin utilities using Google Cloud Application Default Credentials (ADC).

This module provides utilities for working with Google Cloud Application Default Credentials,
which automatically discovers credentials from the environment (gcloud CLI, service accounts, etc.).
"""

import csv
import difflib
from pathlib import Path
from typing import Generator, Optional

import backoff
import google.auth
import google.auth.transport.requests
from google.auth.credentials import Credentials
from googleapiclient import discovery
from googleapiclient.errors import HttpError

from pdum.gcp.types import NO_ORG, APIResolutionError, Organization, Project


def get_email(*, credentials: Optional[Credentials] = None) -> str:
    """Get the email address associated with the given credentials or ADC.

    This function retrieves the credentials (using provided credentials or
    Application Default Credentials) and extracts the associated email address.

    ADC discovers credentials from:
    1. GOOGLE_APPLICATION_CREDENTIALS environment variable (service account key file)
    2. gcloud CLI user credentials (`gcloud auth application-default login`)
    3. Compute Engine/Cloud Run/GKE metadata server
    4. Other Google Cloud environments

    Args:
        credentials: Google Cloud credentials to use. If None, uses Application Default Credentials.

    Returns:
        The email address associated with the credentials

    Raises:
        google.auth.exceptions.DefaultCredentialsError: If no credentials can be found
        AttributeError: If the credentials type doesn't have an email/service_account_email attribute

    Example:
        >>> from pdum.gcp.admin import get_email
        >>> email = get_email()
        >>> print(f"Using credentials for: {email}")
        Using credentials for: user@example.com
    """
    # Get credentials if not provided
    if credentials is None:
        credentials, project_id = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )

    # Try to get email from various credential types
    email = _extract_email_from_credentials(credentials)

    if email:
        return email

    # If we can't extract email directly, try refreshing and getting from token info
    # This works for user credentials
    if hasattr(credentials, "refresh"):
        request = google.auth.transport.requests.Request()
        credentials.refresh(request)

        # After refresh, try to get email from the token
        if hasattr(credentials, "id_token") and credentials.id_token:
            import base64
            import json

            # Decode the JWT payload (second part of the token)
            parts = credentials.id_token.split(".")
            if len(parts) >= 2:
                # Add padding if needed
                payload_encoded = parts[1]
                padding = 4 - len(payload_encoded) % 4
                if padding != 4:
                    payload_encoded += "=" * padding

                payload = json.loads(base64.urlsafe_b64decode(payload_encoded))
                if "email" in payload:
                    return payload["email"]

    # If all else fails, raise an error
    raise AttributeError(
        f"Could not extract email from credentials of type {type(credentials).__name__}. "
        f"The credentials may not have an associated email address, or the credential type "
        f"is not supported by this function."
    )


def _extract_email_from_credentials(credentials: Credentials) -> Optional[str]:
    """Extract email from credentials object.

    Args:
        credentials: Google auth credentials object

    Returns:
        Email address if found, None otherwise
    """
    # Service account credentials
    if hasattr(credentials, "service_account_email"):
        return credentials.service_account_email

    # User credentials (from gcloud auth application-default login)
    if hasattr(credentials, "client_id") and hasattr(credentials, "_id_token"):
        # Try to extract from id_token if available
        try:
            if credentials._id_token:
                import base64
                import json

                parts = credentials._id_token.split(".")
                if len(parts) >= 2:
                    payload_encoded = parts[1]
                    padding = 4 - len(payload_encoded) % 4
                    if padding != 4:
                        payload_encoded += "=" * padding

                    payload = json.loads(base64.urlsafe_b64decode(payload_encoded))
                    if "email" in payload:
                        return payload["email"]
        except Exception:
            pass

    # Compute Engine credentials
    if hasattr(credentials, "service_account_email"):
        return credentials.service_account_email

    return None


def list_organizations(*, credentials: Optional[Credentials] = None) -> list[Organization]:
    """List all Google Cloud organizations accessible to the given credentials or ADC.

    This function uses the Cloud Resource Manager V1 API to list all organizations
    for which the current user or service account has at least basic permissions
    (e.g., Viewer role).

    If there are any projects without an organization parent, NO_ORG will be included
    in the returned list.

    Args:
        credentials: Google Cloud credentials to use. If None, uses Application Default Credentials.

    Returns:
        List of Organization/Container objects representing accessible organizations,
        including NO_ORG if there are projects without an organization parent

    Raises:
        google.auth.exceptions.DefaultCredentialsError: If no credentials can be found
        googleapiclient.errors.HttpError: If the API call fails

    Example:
        >>> from pdum.gcp.admin import list_organizations
        >>> organizations = list_organizations()
        >>> for org in organizations:
        ...     print(f"ID: {org.id} | Name: {org.display_name}")
        ID: 123456789 | Name: My Organization
        ID:  | Name: No Organization  # If there are projects without org

    Note:
        This function requires the Cloud Resource Manager API to be accessible.
        The user must have at least the `resourcemanager.organizations.get` permission
        on the organizations they want to see.
    """
    # Import here to avoid circular dependency
    from pdum.gcp.types import NO_ORG

    # Get credentials if not provided
    if credentials is None:
        credentials, _ = google.auth.default()

    # Build the Resource Manager V1 service client
    # The V1 API is required for listing organizations visible to the user
    crm_service = discovery.build(
        "cloudresourcemanager", "v1", credentials=credentials, cache_discovery=False
    )

    organizations = []

    # Call the organizations.search() method
    # This method uses the current identity to search for Organizations
    # for which the user has at least basic permissions
    # Empty body means "search all organizations visible to me"
    request = crm_service.organizations().search(body={})

    # Handle pagination
    while request is not None:
        response = request.execute()
        for org in response.get("organizations", []):
            # The 'name' field is in the format 'organizations/ORG_ID'
            org_id = org["name"].split("/")[1]
            organizations.append(
                Organization(
                    id=org_id,
                    resource_name=org["name"],
                    display_name=org.get("displayName", ""),
                    _credentials=credentials,
                )
            )

        request = crm_service.organizations().search_next(
            previous_request=request, previous_response=response
        )

    # Check if there are any projects without an organization parent
    # If so, add NO_ORG to the list
    no_org_projects = NO_ORG.projects(credentials=credentials)
    if no_org_projects:
        organizations.append(NO_ORG)

    return organizations


def quota_project(*, credentials: Optional[Credentials] = None) -> Project:
    """Get the quota project from Application Default Credentials.

    This function retrieves the project ID from the environment (via google.auth.default())
    and fetches the full project details to return as a Project object. The quota project
    is the project that will be billed for API requests.

    The project ID is determined from:
    1. GOOGLE_CLOUD_PROJECT environment variable
    2. gcloud CLI configuration (`gcloud config get-value project`)
    3. GCE/Cloud Run/GKE metadata server
    4. Other Google Cloud environments

    Args:
        credentials: Google Cloud credentials to use. If None, uses Application Default Credentials.

    Returns:
        A Project object representing the quota project

    Raises:
        google.auth.exceptions.DefaultCredentialsError: If no credentials can be found
        ValueError: If no project ID can be determined from the environment
        googleapiclient.errors.HttpError: If the API call fails

    Example:
        >>> from pdum.gcp.admin import quota_project
        >>> project = quota_project()
        >>> print(f"Quota Project: {project.id}")
        Quota Project: my-project-123
    """
    # Get credentials and project ID from Application Default Credentials
    if credentials is None:
        credentials, project_id = google.auth.default()
    else:
        # If credentials are provided, still need to determine the project ID from environment
        _, project_id = google.auth.default()

    # Validate that we got a project ID
    if not project_id:
        raise ValueError(
            "No project ID could be determined from the environment. "
            "Set GOOGLE_CLOUD_PROJECT environment variable or configure gcloud CLI with a default project."
        )

    # Build the Resource Manager V1 service client
    crm_service = discovery.build(
        "cloudresourcemanager", "v1", credentials=credentials, cache_discovery=False
    )

    # Get the project details
    project_resource = crm_service.projects().get(projectId=project_id).execute()

    # Determine the parent container
    parent_info = project_resource.get("parent", {})
    parent_type = parent_info.get("type")
    parent_id = parent_info.get("id")

    if parent_type == "organization":
        parent_resource_name = f"organizations/{parent_id}"
        # Get organization details
        org_resource = crm_service.organizations().get(name=parent_resource_name).execute()
        parent = Organization(
            id=parent_id,
            resource_name=parent_resource_name,
            display_name=org_resource.get("displayName", ""),
            _credentials=credentials,
        )
    elif parent_type == "folder":
        parent_resource_name = f"folders/{parent_id}"
        # Import here to avoid circular dependency
        from pdum.gcp.types import Folder

        # Get folder details using CRM v2 API
        crm_v2_service = discovery.build(
            "cloudresourcemanager", "v2", credentials=credentials, cache_discovery=False
        )
        folder_resource = crm_v2_service.folders().get(name=parent_resource_name).execute()
        parent = Folder(
            id=parent_id,
            resource_name=parent_resource_name,
            display_name=folder_resource.get("displayName", ""),
            parent_resource_name=folder_resource.get("parent", ""),
            _credentials=credentials,
        )
    else:
        # No organization or folder parent
        parent = NO_ORG

    # Create and return the Project object
    return Project(
        id=project_resource["projectId"],
        name=project_resource.get("name", ""),
        project_number=str(project_resource.get("projectNumber", "")),
        lifecycle_state=project_resource.get("lifecycleState", ""),
        parent=parent,
        _credentials=credentials,
    )


def walk_projects(
    *, credentials: Optional[Credentials] = None, active_only: bool = True
) -> Generator[Project, None, None]:
    """Recursively yield all projects from all accessible organizations.

    This function lists all organizations accessible to the credentials (or ADC),
    then recursively walks through each organization's folder hierarchy to yield
    all projects found. This includes projects at the organization level, within
    folders, and within nested folders.

    Args:
        credentials: Google Cloud credentials to use. If None, uses Application Default Credentials.
        active_only: If True (default), only yield projects in ACTIVE state.
            If False, yield all projects regardless of lifecycle state
            (including DELETE_REQUESTED and DELETE_IN_PROGRESS).

    Yields:
        Project objects from all accessible organizations and their subfolders

    Raises:
        google.auth.exceptions.DefaultCredentialsError: If no credentials can be found
        googleapiclient.errors.HttpError: If any API call fails

    Example:
        >>> from pdum.gcp.admin import walk_projects
        >>> for project in walk_projects():
        ...     print(f"{project.id} - {project.parent.display_name}")
        project-1 - My Organization
        project-2 - My Organization
        nested-project - Development Folder

        >>> # Include deleted/pending-delete projects
        >>> for project in walk_projects(active_only=False):
        ...     print(f"{project.id} - {project.lifecycle_state}")

    Note:
        This function walks through all organizations, which may take some time
        if you have access to many organizations with many folders and projects.
    """
    # Get credentials if not provided
    if credentials is None:
        credentials, _ = google.auth.default()

    # List all accessible organizations
    organizations = list_organizations(credentials=credentials)

    # Walk through each organization and yield all projects
    for org in organizations:
        yield from org.walk_projects(credentials=credentials, active_only=active_only)


def _load_api_map() -> dict[str, str]:
    """Load the API mapping from the bundled text file.

    The API map file is generated using the gcloud command:
        gcloud services list --available --filter="name:googleapis.com" > src/pdum/gcp/data/api_map.txt

    The file format is:
        NAME                                   TITLE
        serviceusage.googleapis.com           Service Usage API
        compute.googleapis.com                Compute Engine API

    Returns:
        Dictionary mapping display names (TITLE) to service IDs (NAME)

    Raises:
        FileNotFoundError: If the API map file is not found
    """
    # Find the text file in the package data directory
    package_dir = Path(__file__).parent
    txt_path = package_dir / "data" / "api_map.txt"

    if not txt_path.exists():
        raise FileNotFoundError(
            f"API map file not found at {txt_path}. "
            f"Generate it with: gcloud services list --available --filter=\"name:googleapis.com\" > {txt_path}"
        )

    api_map = {}

    with open(txt_path, "r", encoding="utf-8") as f:
        # Skip the header line (NAME TITLE)
        header = f.readline()

        for line in f:
            line = line.strip()
            if not line:
                continue

            # Split on whitespace - first token is service_id (NAME), rest is display_name (TITLE)
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                service_id = parts[0]
                display_name = parts[1]

                # Only include googleapis.com services
                if "googleapis.com" in service_id:
                    api_map[display_name] = service_id

    return api_map


def lookup_api(display_name: str) -> str:
    """Resolve an API display name to its service ID using fuzzy matching.

    This function takes a friendly API name (e.g., "Compute Engine", "Big Query")
    and returns the official service ID (e.g., "compute.googleapis.com",
    "bigquery.googleapis.com"). It uses fuzzy matching to handle minor typos
    and variations in naming.

    The function reads from a bundled text file that contains the mapping of all
    available Google Cloud services. The file is generated using:

        gcloud services list --available --filter="name:googleapis.com" > src/pdum/gcp/data/api_map.txt

    Args:
        display_name: The human-readable name of the API (e.g., "Compute Engine")

    Returns:
        The official service ID (e.g., "compute.googleapis.com")

    Raises:
        APIResolutionError: If no unique match is found or multiple ambiguous matches exist
        FileNotFoundError: If the API map file is not found

    Example:
        >>> from pdum.gcp import lookup_api
        >>> api_id = lookup_api("Compute Engine")
        >>> print(api_id)
        compute.googleapis.com

        >>> # Works with partial names and fuzzy matching
        >>> api_id = lookup_api("Big Query")
        >>> print(api_id)
        bigquery.googleapis.com

        >>> # Raises error on ambiguous matches
        >>> try:
        ...     lookup_api("Cloud")  # Too ambiguous
        ... except APIResolutionError as e:
        ...     print(f"Error: {e}")
    """
    # Load the API map from the text file
    api_map = _load_api_map()

    # 1. Standardize the input for better matching
    normalized_input = display_name.strip().lower().replace("cloud", "").strip()

    # 2. Check for an exact match or normalized match first
    # We use a case-insensitive check against normalized keys
    normalized_keys = {
        k.lower().replace("cloud", "").strip(): v for k, v in api_map.items()
    }

    if display_name in api_map:
        return api_map[display_name]

    if normalized_input in normalized_keys:
        return normalized_keys[normalized_input]

    # 3. Check for substring matches to detect overly generic short terms
    # This catches cases like "Cloud" which appears in many API names
    # Only apply for short terms (< 10 chars) to avoid catching longer specific terms
    if len(display_name) < 10:
        substring_matches = [
            name for name in api_map.keys()
            if display_name.lower() in name.lower()
        ]

        if len(substring_matches) > 1:
            # Too many substring matches - term is too generic
            # Show a few examples
            examples = substring_matches[:5]
            raise APIResolutionError(
                f"The term '{display_name}' is too generic and matches multiple APIs. "
                f"Please be more specific. Found matches in: {', '.join(examples)}"
                + (f" and {len(substring_matches) - 5} more..." if len(substring_matches) > 5 else "")
            )

        if len(substring_matches) == 1:
            # Only one substring match, return it
            return api_map[substring_matches[0]]

    # 4. Perform Fuzzy Matching
    # Use the full display names from the map as possibilities for fuzzy matching
    possibilities = list(api_map.keys())

    # difflib.get_close_matches is part of Python's standard library
    # We use a strict cutoff of 0.6 and look for up to 5 matches.
    close_matches = difflib.get_close_matches(
        word=display_name, possibilities=possibilities, n=5, cutoff=0.6
    )

    # 5. Handle Results
    if len(close_matches) == 1:
        # If there is only one "good enough" match, we treat it as the intended target.
        return api_map[close_matches[0]]

    if len(close_matches) > 1:
        # Multiple close matches found
        raise APIResolutionError(
            f"Multiple close matches found for '{display_name}'. Please be more specific. "
            f"Did you mean one of these: {', '.join(close_matches)}?"
        )

    # No matches found
    raise APIResolutionError(
        f"No direct match or close fuzzy match found for API '{display_name}'. "
        f"Please check the spelling or try a different name."
    )
