"""Tests for the admin module.

These tests interact with real GCP APIs using Application Default Credentials (ADC).
They are skipped in CI by default but can be run locally for manual testing.

To run these tests locally:
    # Run all tests including manual ones
    PDUM_GCP_MANUAL_TESTS=1 uv run pytest tests/test_admin.py -v

    # Run a specific test
    PDUM_GCP_MANUAL_TESTS=1 uv run pytest tests/test_admin.py::test_get_adc_email -v
"""

import os

import pytest

from pdum.gcp.admin import get_email, list_organizations
from pdum.gcp.types import NO_ORG, Container, Folder, Organization, Project

# Skip these tests in CI unless PDUM_GCP_MANUAL_TESTS environment variable is set
manual_test = pytest.mark.skipif(
    not os.getenv("PDUM_GCP_MANUAL_TESTS"),
    reason="Manual test - requires GCP credentials. Set PDUM_GCP_MANUAL_TESTS=1 to run.",
)


@manual_test
def test_get_email():
    """Test getting the email from credentials.

    This test verifies that:
    1. The function can retrieve credentials from ADC
    2. The function can extract an email address
    3. The email is a valid string format
    """
    email = get_email()

    # Verify we got a valid email string
    assert isinstance(email, str)
    assert len(email) > 0
    assert "@" in email

    print(f"\n✓ Successfully retrieved email: {email}")


@manual_test
def test_get_email_format():
    """Test that the email has a valid format."""
    email = get_email()

    # Split on @ to verify basic email structure
    parts = email.split("@")
    assert len(parts) == 2, "Email should have exactly one @ symbol"
    assert len(parts[0]) > 0, "Email should have a username part"
    assert len(parts[1]) > 0, "Email should have a domain part"
    assert "." in parts[1], "Email domain should contain at least one dot"

    print(f"\n✓ Email format is valid: {email}")


@manual_test
def test_list_organizations():
    """Test listing organizations accessible to the current credentials.

    This test verifies that:
    1. The function can call the Cloud Resource Manager API
    2. The function returns a list of Container objects (Organizations or NO_ORG)
    3. Each container has valid attributes
    4. NO_ORG is included if there are projects without an organization parent

    Note: This test may return an empty list if the user doesn't have
    access to any organizations (e.g., personal GCP account).
    """
    organizations = list_organizations()

    # Verify we got a list
    assert isinstance(organizations, list)

    print(f"\n✓ Found {len(organizations)} organization(s)/container(s)")

    # If there are organizations, verify their structure
    for org in organizations:
        # All items should be Containers (Organization or NO_ORG)
        assert isinstance(org, Container)
        assert isinstance(org.id, str)
        assert isinstance(org.resource_name, str)
        assert isinstance(org.display_name, str)

        if org is NO_ORG:
            print(f"  - ID: (none) | Name: {org.display_name} (NO_ORG)")
        else:
            # Regular organizations
            assert isinstance(org, Organization)
            assert len(org.id) > 0, "Organization ID should not be empty"
            assert org.resource_name.startswith(
                "organizations/"
            ), "Organization resource_name should start with 'organizations/'"
            assert org.resource_name.endswith(org.id), "Organization resource_name should end with the ID"
            print(f"  - ID: {org.id} | Name: {org.display_name}")


@manual_test
def test_list_organizations_consistency():
    """Test that calling list_organizations multiple times returns consistent results."""
    orgs1 = list_organizations()
    orgs2 = list_organizations()

    # Both calls should return the same number of organizations
    assert len(orgs1) == len(orgs2), "Multiple calls should return the same number of organizations"

    # Extract IDs from both lists and verify they match
    ids1 = sorted([org.id for org in orgs1])
    ids2 = sorted([org.id for org in orgs2])
    assert ids1 == ids2, "Organization IDs should be consistent across calls"

    print(f"\n✓ Consistency check passed: {len(orgs1)} organizations found in both calls")


@manual_test
def test_organization_dataclass():
    """Test that Organization is a proper dataclass with expected attributes."""
    # Create a test organization
    org = Organization(
        id="123456789", resource_name="organizations/123456789", display_name="Test Org"
    )

    # Verify attributes
    assert org.id == "123456789"
    assert org.resource_name == "organizations/123456789"
    assert org.display_name == "Test Org"

    # Verify it's a dataclass (has __dataclass_fields__)
    assert hasattr(Organization, "__dataclass_fields__")

    # Verify it's a Container
    assert isinstance(org, Container)

    print("\n✓ Organization dataclass structure is correct")


@manual_test
def test_no_org_list_projects():
    """Test listing projects without organization parent using NO_ORG.

    This test verifies that:
    1. The NO_ORG.list_projects() method can call the Cloud Resource Manager API
    2. The method returns a list of Project objects
    3. Each project has valid attributes
    4. Projects returned have no organization parent

    Note: The number of projects may vary over time as projects are created/deleted.
    """
    projects = NO_ORG.list_projects()

    # Verify we got a list
    assert isinstance(projects, list)

    print(f"\n✓ Found {len(projects)} project(s) without organization parent")

    # If there are projects, verify their structure
    for project in projects:
        assert isinstance(project, Project)
        assert isinstance(project.id, str)
        assert isinstance(project.name, str)
        assert isinstance(project.project_number, str)
        assert isinstance(project.lifecycle_state, str)
        assert len(project.id) > 0, "Project ID should not be empty"

        # Verify that the parent is NO_ORG
        assert project.parent is NO_ORG, f"Project {project.id} should have NO_ORG as parent"

        print(f"  - ID: {project.id} | Name: {project.name} | State: {project.lifecycle_state}")


@manual_test
def test_no_org_list_projects_with_credentials():
    """Test that NO_ORG.list_projects() works with explicit credentials."""
    import google.auth

    # Get credentials explicitly
    credentials, _ = google.auth.default()

    # Call with explicit credentials
    projects = NO_ORG.list_projects(credentials=credentials)

    # Should return a list
    assert isinstance(projects, list)

    print(f"\n✓ Successfully listed {len(projects)} projects with explicit credentials")


@manual_test
def test_no_org_list_projects_returns_project_dataclass():
    """Test that NO_ORG.list_projects() returns proper Project dataclass instances."""
    projects = NO_ORG.list_projects()

    # If there are projects, verify they are Project instances
    for project in projects:
        # Should be a Project instance
        assert isinstance(project, Project)

        # Should have all required fields
        assert hasattr(project, "id")
        assert hasattr(project, "name")
        assert hasattr(project, "project_number")
        assert hasattr(project, "lifecycle_state")
        assert hasattr(project, "parent")

        # Parent should be a Container
        assert isinstance(project.parent, Container)

    print(f"\n✓ All {len(projects)} projects are valid Project dataclass instances")


# Unit tests that don't require credentials (these run in CI)


def test_container_base_class():
    """Test that Container base class exists and has expected methods."""
    assert hasattr(Container, "parent")
    assert hasattr(Container, "folders")
    assert hasattr(Container, "projects")


def test_organization_dataclass_fields():
    """Test that Organization dataclass has the expected fields."""
    assert hasattr(Organization, "__dataclass_fields__")
    fields = Organization.__dataclass_fields__
    assert "id" in fields
    assert "resource_name" in fields
    assert "display_name" in fields


def test_folder_dataclass_fields():
    """Test that Folder dataclass has the expected fields."""
    assert hasattr(Folder, "__dataclass_fields__")
    fields = Folder.__dataclass_fields__
    assert "id" in fields
    assert "resource_name" in fields
    assert "display_name" in fields
    assert "parent_resource_name" in fields


def test_project_dataclass_fields():
    """Test that Project dataclass has the expected fields."""
    assert hasattr(Project, "__dataclass_fields__")
    fields = Project.__dataclass_fields__
    assert "id" in fields
    assert "name" in fields
    assert "project_number" in fields
    assert "lifecycle_state" in fields
    assert "parent" in fields


def test_project_dataclass_creation():
    """Test that Project dataclass can be instantiated."""
    project = Project(
        id="test-project-123",
        name="Test Project",
        project_number="123456789",
        lifecycle_state="ACTIVE",
        parent=NO_ORG,
    )

    assert project.id == "test-project-123"
    assert project.name == "Test Project"
    assert project.project_number == "123456789"
    assert project.lifecycle_state == "ACTIVE"
    assert project.parent is NO_ORG


def test_admin_module_imports():
    """Test that all expected functions and classes can be imported."""
    from pdum.gcp import admin

    assert hasattr(admin, "get_email")
    assert hasattr(admin, "list_organizations")


def test_types_module_imports():
    """Test that all expected types can be imported."""
    from pdum.gcp import types

    assert hasattr(types, "Container")
    assert hasattr(types, "Organization")
    assert hasattr(types, "Folder")
    assert hasattr(types, "Project")
    assert hasattr(types, "NO_ORG")


def test_admin_functions_are_callable():
    """Test that the admin functions are callable (without calling them)."""
    assert callable(get_email)
    assert callable(list_organizations)


def test_project_suggest_name_with_prefix():
    """Test Project.suggest_name() with a custom prefix."""
    name = Project.suggest_name(prefix="myapp", random_digits=5)

    # Should start with the prefix
    assert name.startswith("myapp-")

    # Should have the format prefix-XXXXX where X is a digit
    parts = name.split("-")
    assert len(parts) == 2
    assert parts[0] == "myapp"
    assert len(parts[1]) == 5
    assert parts[1].isdigit()

    # Should be valid length
    assert 6 <= len(name) <= 30


def test_project_suggest_name_without_prefix():
    """Test Project.suggest_name() without prefix (uses coolname)."""
    name = Project.suggest_name()

    # Should have at least 2 parts (adjective-animal) plus digits
    assert "-" in name

    # Should be valid length
    assert 6 <= len(name) <= 30

    # Should end with 5 digits (default)
    parts = name.split("-")
    assert len(parts) >= 2  # At least adjective-animal
    assert parts[-1].isdigit()
    assert len(parts[-1]) == 5


def test_project_suggest_name_no_random_digits():
    """Test Project.suggest_name() with random_digits=0."""
    name = Project.suggest_name(prefix="myproject", random_digits=0)

    # Should be just the prefix
    assert name == "myproject"

    # Should not have any digits appended
    assert not name.endswith("-")


def test_project_suggest_name_custom_digit_count():
    """Test Project.suggest_name() with custom random_digits."""
    name = Project.suggest_name(prefix="app", random_digits=8)

    # Should have 8 random digits
    parts = name.split("-")
    assert len(parts) == 2
    assert parts[0] == "app"
    assert len(parts[1]) == 8
    assert parts[1].isdigit()


def test_project_suggest_name_invalid_prefix():
    """Test that invalid prefix raises ValueError."""
    import pytest

    # Prefix must start with lowercase letter
    with pytest.raises(ValueError, match="must start with a lowercase letter"):
        Project.suggest_name(prefix="MyApp")

    with pytest.raises(ValueError, match="must start with a lowercase letter"):
        Project.suggest_name(prefix="123app")

    with pytest.raises(ValueError, match="must start with a lowercase letter"):
        Project.suggest_name(prefix="-app")


def test_project_suggest_name_invalid_random_digits():
    """Test that invalid random_digits raises ValueError."""
    import pytest

    # random_digits must be 0-10
    with pytest.raises(ValueError, match="must be between 0 and 10"):
        Project.suggest_name(prefix="app", random_digits=-1)

    with pytest.raises(ValueError, match="must be between 0 and 10"):
        Project.suggest_name(prefix="app", random_digits=11)


def test_project_suggest_name_length_validation():
    """Test that generated names are within GCP limits (6-30 characters)."""
    # Short prefix with no digits should fail (< 6 chars)
    import pytest

    with pytest.raises(ValueError, match="must be 6-30 characters"):
        Project.suggest_name(prefix="app", random_digits=0)

    # Very long prefix might exceed 30 chars
    long_prefix = "a" * 25
    with pytest.raises(ValueError, match="must be 6-30 characters"):
        Project.suggest_name(prefix=long_prefix, random_digits=5)  # Would be 31 chars


def test_project_suggest_name_randomness():
    """Test that suggest_name() generates different names each time."""
    # Generate 10 names and verify they're not all the same
    names = [Project.suggest_name(prefix="test") for _ in range(10)]

    # All names should start with "test-"
    assert all(name.startswith("test-") for name in names)

    # At least some names should be different (very unlikely all 10 are the same)
    assert len(set(names)) > 1


def test_project_suggest_name_coolname_randomness():
    """Test that suggest_name() with coolname generates different names."""
    # Generate 5 coolnames and verify they're not all identical
    names = [Project.suggest_name(random_digits=3) for _ in range(5)]

    # Should have variety (very unlikely all 5 are identical)
    assert len(set(names)) > 1


def test_no_org_has_container_methods():
    """Test that NO_ORG has Container methods."""
    assert hasattr(NO_ORG, "parent")
    assert callable(NO_ORG.parent)
    assert hasattr(NO_ORG, "folders")
    assert callable(NO_ORG.folders)
    assert hasattr(NO_ORG, "projects")
    assert callable(NO_ORG.projects)
    # Backward compatibility
    assert hasattr(NO_ORG, "list_projects")
    assert callable(NO_ORG.list_projects)


def test_no_org_sentinel():
    """Test that NO_ORG is a proper sentinel and subclass of Container."""
    # NO_ORG should be an instance of Container
    assert isinstance(NO_ORG, Container)

    # NO_ORG should be a singleton (same object every time)
    from pdum.gcp.types import NO_ORG as NO_ORG2

    assert NO_ORG is NO_ORG2

    # NO_ORG should have Container attributes
    assert hasattr(NO_ORG, "id")
    assert hasattr(NO_ORG, "resource_name")
    assert hasattr(NO_ORG, "display_name")

    # NO_ORG should have expected values
    assert NO_ORG.id == ""
    assert NO_ORG.resource_name == "NO_ORG"
    assert NO_ORG.display_name == "No Organization"

    # NO_ORG should be falsy
    assert not NO_ORG
    assert bool(NO_ORG) is False

    # NO_ORG should have a clean string representation
    assert str(NO_ORG) == "NO_ORG"
    assert repr(NO_ORG) == "NO_ORG"


def test_no_org_container_methods_work():
    """Test that NO_ORG Container methods return expected values."""
    # parent() should return None
    assert NO_ORG.parent() is None

    # folders() should return empty list
    assert NO_ORG.folders() == []

    # projects() method should exist (actual API call tested in manual tests)
    assert callable(NO_ORG.projects)


def test_no_org_is_not_regular_container():
    """Test that NO_ORG is distinguishable from regular Containers."""
    # Create regular containers
    regular_org = Organization(id="123", resource_name="organizations/123", display_name="Test Org")
    regular_folder = Folder(
        id="456", resource_name="folders/456", display_name="Test Folder", parent_resource_name="organizations/123"
    )

    # They should not be equal
    assert NO_ORG != regular_org
    assert NO_ORG != regular_folder

    # NO_ORG is falsy, regular containers are truthy
    assert not NO_ORG
    assert regular_org  # Regular dataclass instances are truthy
    assert regular_folder

    # NO_ORG can be checked with identity
    assert NO_ORG is NO_ORG
    assert regular_org is not NO_ORG
    assert regular_folder is not NO_ORG


def test_no_org_type_checking():
    """Test that NO_ORG works correctly with type checking patterns."""

    def accept_container(container: Container) -> str:
        """Function that accepts a Container (including NO_ORG)."""
        if container is NO_ORG:
            return "no organization"
        return f"container: {container.id}"

    # NO_ORG should be accepted by functions expecting Container
    result = accept_container(NO_ORG)
    assert result == "no organization"

    # Regular Container subclasses should also work
    regular_org = Organization(id="123", resource_name="organizations/123", display_name="Test")
    result = accept_container(regular_org)
    assert result == "container: 123"

    regular_folder = Folder(
        id="456", resource_name="folders/456", display_name="Test", parent_resource_name="organizations/123"
    )
    result = accept_container(regular_folder)
    assert result == "container: 456"


def test_container_has_tree_method():
    """Test that Container has a tree() method."""
    assert hasattr(Container, "tree")
    assert callable(Container.tree)

    # Verify NO_ORG has the tree method
    assert hasattr(NO_ORG, "tree")
    assert callable(NO_ORG.tree)


def test_container_has_create_folder_method():
    """Test that Container has a create_folder() method."""
    assert hasattr(Container, "create_folder")
    assert callable(Container.create_folder)

    # Verify Organization has the method
    assert hasattr(Organization, "create_folder")
    assert callable(Organization.create_folder)

    # Verify Folder has the method
    assert hasattr(Folder, "create_folder")
    assert callable(Folder.create_folder)

    # Verify NO_ORG has the method (but it raises exception)
    assert hasattr(NO_ORG, "create_folder")
    assert callable(NO_ORG.create_folder)


def test_no_org_create_folder_raises_exception():
    """Test that NO_ORG.create_folder() raises TypeError.

    NO_ORG cannot have folders as children, so attempting to create
    a folder should raise a TypeError.
    """
    import pytest

    with pytest.raises(TypeError, match="NO_ORG cannot have folders"):
        NO_ORG.create_folder("test-folder")

    with pytest.raises(
        TypeError,
        match="Projects without an organization parent cannot contain folders",
    ):
        NO_ORG.create_folder("another-test")


@manual_test
def test_tree_method():
    """Test that the tree() method prints a nice tree structure.

    This test calls tree() on all organizations to verify it works with real data.
    It doesn't verify the exact output format, just that it runs without errors.
    """
    organizations = list_organizations()

    print("\n" + "=" * 80)
    print("Testing tree() method output:")
    print("=" * 80)

    for org in organizations:
        print()
        org.tree()
        print()

    print("=" * 80)
    print("✓ tree() method executed successfully for all containers")


@manual_test
def test_tree_method_no_org():
    """Test that the tree() method works specifically for NO_ORG."""
    print("\n" + "=" * 80)
    print("Testing tree() method for NO_ORG:")
    print("=" * 80)
    print()

    NO_ORG.tree()

    print()
    print("=" * 80)
    print("✓ tree() method executed successfully for NO_ORG")
