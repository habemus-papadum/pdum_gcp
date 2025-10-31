"""Internal helper functions."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pdum.gcp.types import Role, Container, Project


def _list_roles(resource: "Container | Project") -> list[Role]:
    """Internal helper to list IAM roles for a resource."""
    from pdum.gcp.admin import get_email
    from pdum.gcp._clients import iam_v1
    from pdum.gcp.types import Role

    creds = resource._get_credentials()
    email = get_email(credentials=creds)

    policy = resource.get_iam_policy(credentials=creds)
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
