"""Internal helper functions."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.auth.credentials import Credentials

    from pdum.gcp.types import Role


def _get_iam_policy(*, credentials: "Credentials", resource_name: str) -> dict:
    """Fetch the IAM policy for a resource using Cloud Resource Manager v3.

    Parameters
    ----------
    credentials : Credentials
        Materialized credentials to authenticate the request.
    resource_name : str
        Full resource name, e.g., ``projects/{id}``, ``folders/{id}``,
        or ``organizations/{id}``.

    Returns
    -------
    dict
        The IAM policy for the resource.
    """
    from pdum.gcp._clients import crm_v3

    crm = crm_v3(credentials)
    if resource_name.startswith("projects/"):
        return crm.projects().getIamPolicy(resource=resource_name, body={}).execute()
    if resource_name.startswith("folders/"):
        return crm.folders().getIamPolicy(resource=resource_name, body={}).execute()
    if resource_name.startswith("organizations/"):
        return crm.organizations().getIamPolicy(resource=resource_name, body={}).execute()
    raise ValueError(f"Unsupported resource_name: {resource_name}")


def _list_roles(*, credentials: "Credentials", resource_name: str, user_email: str | None = None) -> list[Role]:
    """List IAM roles bound directly to a user on a resource.

    This helper is intentionally decoupled from high-level objects. Callers pass
    in materialized `credentials` and the target `resource_name` (e.g.,
    ``"projects/my-project"``, ``"folders/123"``, ``"organizations/456"``),
    and optionally the target ``user_email``. If ``user_email`` is omitted,
    the email is derived from the provided credentials (ADC).
    """
    from pdum.gcp._clients import iam_v1
    from pdum.gcp.admin import get_email
    from pdum.gcp.types import Role

    creds = credentials
    email = user_email or get_email(credentials=creds)

    # Fetch IAM policy via shared helper
    policy = _get_iam_policy(credentials=creds, resource_name=resource_name)
    user_roles = []
    for binding in policy.get("bindings", []):
        if f"user:{email}" in binding.get("members", []):
            user_roles.append(binding["role"])

    iam_service = iam_v1(creds)
    predefined_roles = {}
    request = iam_service.roles().list()
    while request is not None:
        response = request.execute()
        for role in response.get("roles", []):
            predefined_roles[role["name"]] = role
        request = iam_service.roles().list_next(previous_request=request, previous_response=response)

    roles = []
    for role_name in user_roles:
        role_info = predefined_roles.get(role_name)
        if role_info:
            roles.append(
                Role(
                    name=role_info["name"],
                    title=role_info.get("title", ""),
                    description=role_info.get("description", ""),
                )
            )
        else:
            # Custom role
            try:
                role_info = iam_service.roles().get(name=role_name).execute()
                roles.append(
                    Role(
                        name=role_info["name"],
                        title=role_info.get("title", ""),
                        description=role_info.get("description", ""),
                    )
                )
            except Exception:
                # If we can't get the role, just append the name
                roles.append(Role(name=role_name, title="", description=""))

    return roles
