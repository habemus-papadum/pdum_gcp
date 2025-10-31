"""Admin utilities using Google Cloud Application Default Credentials (ADC).

This module provides utilities for working with Google Cloud Application Default Credentials,
which automatically discovers credentials from the environment (gcloud CLI, service accounts, etc.).
"""

from typing import Generator, Optional

import google.auth
import google.auth.transport.requests
from google.auth.credentials import Credentials
from googleapiclient import discovery

from pdum.gcp.types import NO_ORG, Organization, Project


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
    *, credentials: Optional[Credentials] = None
) -> Generator[Project, None, None]:
    """Recursively yield all projects from all accessible organizations.

    This function lists all organizations accessible to the credentials (or ADC),
    then recursively walks through each organization's folder hierarchy to yield
    all projects found. This includes projects at the organization level, within
    folders, and within nested folders.

    Args:
        credentials: Google Cloud credentials to use. If None, uses Application Default Credentials.

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
        yield from org.walk_projects(credentials=credentials)
