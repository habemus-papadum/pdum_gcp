"""Tests for the list_roles method."""

import os

import pytest

from pdum.gcp.admin import list_organizations, quota_project
from pdum.gcp.types import Organization

# Skip these tests in CI unless PDUM_GCP_MANUAL_TESTS environment variable is set
manual_test = pytest.mark.skipif(
    not os.getenv("PDUM_GCP_MANUAL_TESTS"),
    reason="Manual test - requires GCP credentials. Set PDUM_GCP_MANUAL_TESTS=1 to run.",
)


@manual_test
def test_list_roles_organization():
    """Test listing roles for an organization."""
    orgs = list_organizations()
    if not orgs:
        pytest.skip("No organizations found to test.")

    for org in orgs:
        if isinstance(org, Organization):
            roles = org.list_roles()
            assert isinstance(roles, list)
            print(f"\n✓ Found {len(roles)} roles for organization {org.display_name}:")
            for role in roles:
                print(f"  - {role.name}: {role.title}")


@manual_test
def test_list_roles_project():
    """Test listing roles for a project."""
    project = quota_project()
    roles = project.list_roles()
    assert isinstance(roles, list)
    print(f"\n✓ Found {len(roles)} roles for project {project.id}:")
    for role in roles:
        print(f"  - {role.name}: {role.title}")


@manual_test
def test_list_roles_folder():
    """Test listing roles for a folder."""
    orgs = list_organizations()
    if not orgs:
        pytest.skip("No organizations found to test.")

    for org in orgs:
        if isinstance(org, Organization):
            folders = org.folders()
            if not folders:
                continue

            for folder in folders:
                roles = folder.list_roles()
                assert isinstance(roles, list)
                print(f"\n✓ Found {len(roles)} roles for folder {folder.display_name}:")
                for role in roles:
                    print(f"  - {role.name}: {role.title}")
                return  # Only test one folder

