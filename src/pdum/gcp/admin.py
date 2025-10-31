"""Admin utilities using Google Cloud Application Default Credentials (ADC).

This module provides utilities for working with Google Cloud Application Default Credentials,
which automatically discovers credentials from the environment (gcloud CLI, service accounts, etc.).
"""

import csv
import difflib
from pathlib import Path
from typing import Generator, Optional

import google.auth
import google.auth.transport.requests
from google.auth.credentials import Credentials
from googleapiclient import discovery
from googleapiclient.errors import HttpError

from pdum.gcp.types import NO_ORG, APIResolutionError, Organization, Project


def get_email(*, credentials: Optional[Credentials] = None) -> str:
    """Return the email for the provided credentials or ADC.

    Parameters
    ----------
    credentials : Credentials, optional
        Explicit Google Cloud credentials to use. If ``None``, attempts to
        load Application Default Credentials (ADC).

    Returns
    -------
    str
        The email address associated with the active identity.

    Raises
    ------
    google.auth.exceptions.DefaultCredentialsError
        If no credentials can be found.
    AttributeError
        If an email cannot be extracted from the credential type.

    Examples
    --------
    >>> from pdum.gcp.admin import get_email
    >>> get_email()  # doctest: +SKIP
    'user@example.com'
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
    """List organizations visible to the caller.

    Uses Cloud Resource Manager v1 to search all organizations the current
    identity can see. If projects exist outside an organization, ``NO_ORG`` is
    appended to the result.

    Parameters
    ----------
    credentials : Credentials, optional
        Explicit credentials to use. If ``None``, uses ADC.

    Returns
    -------
    list[Organization]
        Organizations accessible to the caller, plus ``NO_ORG`` if applicable.

    Raises
    ------
    google.auth.exceptions.DefaultCredentialsError
        If no credentials can be found.
    googleapiclient.errors.HttpError
        If the API call fails.

    Notes
    -----
    Requires the Cloud Resource Manager API and basic permissions on target
    organizations (e.g., Viewer).
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
    """Return the quota (billing) project inferred from the environment.

    Parameters
    ----------
    credentials : Credentials, optional
        Explicit credentials to use for API calls. The project id is still
        derived from the environment or platform metadata.

    Returns
    -------
    Project
        The resolved quota project.

    Raises
    ------
    google.auth.exceptions.DefaultCredentialsError
        If no credentials can be found.
    ValueError
        If a project id cannot be determined.
    googleapiclient.errors.HttpError
        If the project lookup API call fails.

    Examples
    --------
    >>> from pdum.gcp.admin import quota_project
    >>> quota_project()  # doctest: +SKIP
    Project(id='my-project-123', ...)
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

    # Use Project.lookup() to get the full project details
    return Project.lookup(project_id, credentials=credentials)


def walk_projects(
    *, credentials: Optional[Credentials] = None, active_only: bool = True
) -> Generator[Project, None, None]:
    """Yield all projects across all accessible organizations.

    Parameters
    ----------
    credentials : Credentials, optional
        Explicit credentials to use. If ``None``, uses ADC.
    active_only : bool, default True
        If ``True``, yields only ACTIVE projects. If ``False``, yields all
        lifecycle states.

    Yields
    ------
    Project
        Projects from organizations and nested folders.

    Raises
    ------
    google.auth.exceptions.DefaultCredentialsError
        If no credentials can be found.
    googleapiclient.errors.HttpError
        If any API call fails.

    Notes
    -----
    Traversal may take time in estates with many organizations/folders.
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
    """Load the display-name → service-id map from the bundled data file.

    The file is generated periodically with:

    ``gcloud services list --available --filter="name:googleapis.com" > src/pdum/gcp/data/api_map.txt``

    Returns
    -------
    dict[str, str]
        Mapping of human-readable display names (``TITLE``) to service ids
        (``NAME``, e.g., ``compute.googleapis.com``).

    Raises
    ------
    FileNotFoundError
        If the bundled map file is missing.
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
    """Resolve a human-friendly API name to its service id.

    Uses normalization, substring checks (for short queries), and fuzzy matching
    against the bundled API map.

    Parameters
    ----------
    display_name : str
        Human-readable API name, e.g. ``"Compute Engine"``.

    Returns
    -------
    str
        Service id such as ``"compute.googleapis.com"``.

    Raises
    ------
    APIResolutionError
        If no match or multiple ambiguous matches are found.
    FileNotFoundError
        If the API map data file is missing.

    Examples
    --------
    >>> from pdum.gcp import lookup_api
    >>> lookup_api("Compute Engine")  # doctest: +SKIP
    'compute.googleapis.com'
    >>> lookup_api("Big Query")  # doctest: +SKIP
    'bigquery.googleapis.com'
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
