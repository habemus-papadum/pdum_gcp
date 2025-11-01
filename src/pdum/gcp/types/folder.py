"""Folder container implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from pdum.gcp._clients import crm_v3

from .container import Container

if TYPE_CHECKING:
    from .project import Project


@dataclass
class Folder(Container):
    """Information about a GCP folder."""

    parent_resource_name: str = ""

    def parent(self, *, credentials=None) -> Optional[Container]:
        """Return the parent container."""
        if not self.parent_resource_name:
            return None

        creds = self._get_credentials(credentials=credentials)
        crm_service = crm_v3(creds)

        if self.parent_resource_name.startswith("organizations/"):
            from .organization import Organization

            org_id = self.parent_resource_name.split("/")[1]
            return Organization.lookup(org_id, credentials=creds)

        if self.parent_resource_name.startswith("folders/"):
            folder_resource = crm_service.folders().get(name=self.parent_resource_name).execute()
            return Folder(
                id=folder_resource["name"].split("/")[1],
                resource_name=folder_resource["name"],
                display_name=folder_resource.get("displayName", ""),
                parent_resource_name=folder_resource.get("parent", ""),
                _credentials=creds,
            )

        return None

    def folders(self, *, credentials=None) -> list["Folder"]:
        """List direct child folders of this folder."""
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

    def projects(self, *, credentials=None) -> list["Project"]:
        """List direct child projects of this folder."""
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

    def create_folder(self, display_name: str, *, credentials=None) -> "Folder":
        """Create a folder directly under this folder."""
        creds = self._get_credentials(credentials=credentials)
        crm_service = crm_v3(creds)

        folder_body = {"displayName": display_name, "parent": self.resource_name}

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


__all__ = ["Folder"]
