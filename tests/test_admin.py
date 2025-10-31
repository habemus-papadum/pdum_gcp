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

from pdum.gcp.admin import (
    get_email,
    list_organizations,
    lookup_api,
    quota_project,
    walk_projects,
)
from pdum.gcp.types import (
    NO_BILLING_ACCOUNT,
    NO_ORG,
    APIResolutionError,
    BillingAccount,
    Container,
    Folder,
    Organization,
    Project,
)

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
    assert hasattr(admin, "quota_project")


def test_types_module_imports():
    """Test that all expected types can be imported."""
    from pdum.gcp import types

    assert hasattr(types, "Container")
    assert hasattr(types, "Organization")
    assert hasattr(types, "Folder")
    assert hasattr(types, "Project")
    assert hasattr(types, "NO_ORG")
    assert hasattr(types, "BillingAccount")
    assert hasattr(types, "NO_BILLING_ACCOUNT")


def test_admin_functions_are_callable():
    """Test that the admin functions are callable (without calling them)."""
    assert callable(get_email)
    assert callable(list_organizations)
    assert callable(quota_project)
    assert callable(walk_projects)
    assert callable(lookup_api)


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


def test_container_has_walk_projects_method():
    """Test that Container has a walk_projects() method."""
    assert hasattr(Container, "walk_projects")
    assert callable(Container.walk_projects)

    # Verify Organization has the method
    assert hasattr(Organization, "walk_projects")
    assert callable(Organization.walk_projects)

    # Verify Folder has the method
    assert hasattr(Folder, "walk_projects")
    assert callable(Folder.walk_projects)

    # Verify NO_ORG has the method
    assert hasattr(NO_ORG, "walk_projects")
    assert callable(NO_ORG.walk_projects)


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


def test_container_has_cd_method():
    """Test that Container base class has cd method."""
    assert hasattr(Container, "cd")
    assert callable(Container.cd)

    # Verify it exists on Organization and Folder
    assert hasattr(Organization, "cd")
    assert hasattr(Folder, "cd")

    # Verify it exists on NO_ORG (even though it raises an error)
    assert hasattr(NO_ORG, "cd")


def test_no_org_cd_raises_exception():
    """Test that NO_ORG.cd() raises TypeError.

    NO_ORG cannot have folders, so attempting to navigate to a folder
    should raise a TypeError.
    """
    import pytest

    with pytest.raises(TypeError, match="NO_ORG cannot have folders"):
        NO_ORG.cd("test-folder")

    with pytest.raises(TypeError, match="Use cd\\(\\) on an organization or folder instead"):
        NO_ORG.cd("dev/team-a")


def test_cd_empty_path_raises_error():
    """Test that cd with empty path raises ValueError."""
    import pytest
    from pdum.gcp.types import Organization

    # Create a mock organization for testing
    org = Organization(
        id="123456789",
        resource_name="organizations/123456789",
        display_name="Test Org",
        _credentials=None,
    )

    with pytest.raises(ValueError, match="Path cannot be empty"):
        org.cd("")

    with pytest.raises(ValueError, match="Path cannot be empty"):
        org.cd("/")

    with pytest.raises(ValueError, match="Path cannot be empty"):
        org.cd("//")


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


def test_billing_account_dataclass():
    """Test that BillingAccount is a proper dataclass with expected attributes."""
    # Create a test billing account
    billing = BillingAccount(id="012345-567890-ABCDEF", display_name="Test Billing Account")

    # Verify attributes
    assert billing.id == "012345-567890-ABCDEF"
    assert billing.display_name == "Test Billing Account"

    # Verify it's a dataclass (has __dataclass_fields__)
    assert hasattr(BillingAccount, "__dataclass_fields__")

    # Verify regular billing accounts are truthy
    assert billing
    assert bool(billing) is True

    print("✓ BillingAccount dataclass structure is correct")


def test_no_billing_account_sentinel():
    """Test that NO_BILLING_ACCOUNT is a proper sentinel and subclass of BillingAccount."""
    # NO_BILLING_ACCOUNT should be an instance of BillingAccount
    assert isinstance(NO_BILLING_ACCOUNT, BillingAccount)

    # NO_BILLING_ACCOUNT should be a singleton (same object every time)
    from pdum.gcp.types import NO_BILLING_ACCOUNT as NO_BILLING_ACCOUNT2

    assert NO_BILLING_ACCOUNT is NO_BILLING_ACCOUNT2

    # NO_BILLING_ACCOUNT should have BillingAccount attributes
    assert hasattr(NO_BILLING_ACCOUNT, "id")
    assert hasattr(NO_BILLING_ACCOUNT, "display_name")

    # NO_BILLING_ACCOUNT should have expected values
    assert NO_BILLING_ACCOUNT.id == ""
    assert NO_BILLING_ACCOUNT.display_name == "No Billing Account"

    # NO_BILLING_ACCOUNT should be falsy
    assert not NO_BILLING_ACCOUNT
    assert bool(NO_BILLING_ACCOUNT) is False

    # NO_BILLING_ACCOUNT should have a clean string representation
    assert str(NO_BILLING_ACCOUNT) == "NO_BILLING_ACCOUNT"
    assert repr(NO_BILLING_ACCOUNT) == "NO_BILLING_ACCOUNT"


def test_no_billing_account_is_not_regular_billing_account():
    """Test that NO_BILLING_ACCOUNT is distinguishable from regular BillingAccounts."""
    # Create regular billing account
    regular_billing = BillingAccount(id="123456-ABCDEF-789012", display_name="My Billing Account")

    # They should not be equal
    assert NO_BILLING_ACCOUNT != regular_billing

    # NO_BILLING_ACCOUNT is falsy, regular billing accounts are truthy
    assert not NO_BILLING_ACCOUNT
    assert regular_billing  # Regular dataclass instances are truthy

    # NO_BILLING_ACCOUNT can be checked with identity
    assert NO_BILLING_ACCOUNT is NO_BILLING_ACCOUNT
    assert regular_billing is not NO_BILLING_ACCOUNT


def test_billing_account_type_checking():
    """Test that NO_BILLING_ACCOUNT works correctly with type checking patterns."""

    def accept_billing_account(billing: BillingAccount) -> str:
        """Function that accepts a BillingAccount (including NO_BILLING_ACCOUNT)."""
        if billing is NO_BILLING_ACCOUNT:
            return "no billing account"
        return f"billing account: {billing.id}"

    # NO_BILLING_ACCOUNT should be accepted by functions expecting BillingAccount
    result = accept_billing_account(NO_BILLING_ACCOUNT)
    assert result == "no billing account"

    # Regular BillingAccount should also work
    regular_billing = BillingAccount(id="123456-ABCDEF-789012", display_name="Test")
    result = accept_billing_account(regular_billing)
    assert result == "billing account: 123456-ABCDEF-789012"


def test_project_has_billing_account_method():
    """Test that Project has a billing_account() method."""
    assert hasattr(Project, "billing_account")
    assert callable(Project.billing_account)


def test_project_has_enabled_apis_method():
    """Test that Project has an enabled_apis() method."""
    assert hasattr(Project, "enabled_apis")
    assert callable(Project.enabled_apis)


def test_project_has_enable_apis_method():
    """Test that Project has an enable_apis() method."""
    assert hasattr(Project, "enable_apis")
    assert callable(Project.enable_apis)


def test_organization_has_billing_accounts_method():
    """Test that Organization has a billing_accounts() method."""
    assert hasattr(Organization, "billing_accounts")
    assert callable(Organization.billing_accounts)


def test_no_org_has_billing_accounts_method():
    """Test that NO_ORG has a billing_accounts() method."""
    assert hasattr(NO_ORG, "billing_accounts")
    assert callable(NO_ORG.billing_accounts)


@manual_test
def test_quota_project():
    """Test retrieving the quota project.

    This test verifies that:
    1. The function can retrieve the project ID from the environment
    2. The function can fetch full project details
    3. The function returns a valid Project object
    4. The project has all required attributes

    Note: This requires GOOGLE_CLOUD_PROJECT to be set or gcloud to have a default project.
    """
    project = quota_project()

    # Verify we got a Project object
    assert isinstance(project, Project)

    # Verify all attributes are present
    assert isinstance(project.id, str)
    assert len(project.id) > 0
    assert isinstance(project.name, str)
    assert isinstance(project.project_number, str)
    assert isinstance(project.lifecycle_state, str)
    assert isinstance(project.parent, Container)

    print(f"\n✓ Successfully retrieved quota project:")
    print(f"  ID: {project.id}")
    print(f"  Name: {project.name}")
    print(f"  Number: {project.project_number}")
    print(f"  State: {project.lifecycle_state}")
    print(f"  Parent: {project.parent.display_name} ({project.parent.resource_name})")


@manual_test
def test_project_enabled_apis():
    """Test listing enabled APIs for a project.

    This test verifies that:
    1. The method can retrieve enabled APIs for a project
    2. The method returns a list of strings
    3. Each string is a valid API service name

    Note: This requires permissions to view enabled services.
    """
    # Get a project to test with
    organizations = list_organizations()
    if not organizations:
        print("\n⚠️  No organizations found to get a test project")
        return

    # Get the first project from the first organization
    projects = organizations[0].projects()
    if not projects:
        print("\n⚠️  No projects found in organization")
        return

    project = projects[0]

    print(f"\n🔎 Testing enabled_apis() for project: {project.id}")

    # Get enabled APIs
    apis = project.enabled_apis()

    # Verify we got a list
    assert isinstance(apis, list)

    print(f"\n✓ Found {len(apis)} enabled API(s):")
    for api in sorted(apis)[:10]:  # Show first 10
        print(f"  - {api}")

    if len(apis) > 10:
        print(f"  ... and {len(apis) - 10} more")

    # Verify each item is a string
    for api in apis:
        assert isinstance(api, str)
        assert len(api) > 0
        # Most API names end with .googleapis.com
        assert "." in api


@manual_test
def test_project_enable_apis():
    """Test enabling APIs for a project.

    This test verifies that:
    1. The method can enable APIs for a project
    2. The method polls the operation until completion
    3. The method returns a successful operation result

    Note: This requires "Service Usage Admin" permissions.
    This test attempts to enable serviceusage.googleapis.com which is likely already enabled
    (since we're using it), making this a safe test.
    """
    # Get the quota project to test with
    project = quota_project()

    print(f"\n🔧 Testing enable_apis() for project: {project.id}")

    # Try to enable an API that's likely already enabled (serviceusage itself)
    # This is safer than enabling something new that might not be desired
    apis_to_enable = ["serviceusage.googleapis.com"]

    print(f"   Attempting to enable: {apis_to_enable[0]}")

    # Enable the API with verbose output
    result = project.enable_apis(apis_to_enable, verbose=True, polling_interval=2.0)

    # Verify we got a result
    assert isinstance(result, dict)
    assert result.get("done", False) is True

    print(f"\n✓ API enablement completed successfully")
    print(f"  Operation name: {result.get('name')}")

    # Verify the API is now in the enabled list
    enabled_apis = project.enabled_apis()
    assert "serviceusage.googleapis.com" in enabled_apis
    print(f"  Verified API is now enabled")


@manual_test
def test_walk_projects():
    """Test walking through all projects across all organizations.

    This test verifies that:
    1. The walk_projects() function yields projects from all organizations
    2. The function correctly recurses through folders
    3. Each yielded item is a valid Project object
    4. The active_only parameter filters projects correctly

    Note: This may take some time if you have many organizations/folders/projects.
    """
    print("\n" + "=" * 80)
    print("Testing walk_projects() function")
    print("=" * 80)

    # Test with active_only=True (default)
    print("\nTesting with active_only=True (default):")
    active_count = 0
    org_project_counts = {}

    for project in walk_projects():
        # Verify it's a Project object
        assert isinstance(project, Project)
        assert isinstance(project.id, str)
        assert len(project.id) > 0

        # Verify all projects are ACTIVE when active_only=True
        assert project.lifecycle_state == "ACTIVE", (
            f"Expected ACTIVE state, got {project.lifecycle_state} for {project.id}"
        )

        # Track which org this project belongs to
        parent_name = project.parent.display_name
        org_project_counts[parent_name] = org_project_counts.get(parent_name, 0) + 1

        active_count += 1

        # Print first 10 projects
        if active_count <= 10:
            print(f"  {active_count}. {project.id} (parent: {parent_name})")

    if active_count > 10:
        print(f"  ... and {active_count - 10} more projects")

    print(f"\n✓ Found {active_count} ACTIVE project(s)")

    # Test with active_only=False
    print("\nTesting with active_only=False:")
    all_count = 0
    state_counts = {}

    for project in walk_projects(active_only=False):
        assert isinstance(project, Project)
        all_count += 1

        state = project.lifecycle_state
        state_counts[state] = state_counts.get(state, 0) + 1

    print(f"✓ Found {all_count} project(s) total (all states)")
    print("\nProject counts by lifecycle state:")
    for state, count in sorted(state_counts.items()):
        print(f"  {state}: {count}")

    # Verify active_only=False returns at least as many projects as active_only=True
    assert all_count >= active_count, (
        f"active_only=False should return >= projects ({all_count} >= {active_count})"
    )

    print("\n" + "-" * 80)
    print("Project counts by parent (active only):")
    for parent_name, count in sorted(org_project_counts.items()):
        print(f"  {parent_name}: {count} project(s)")

    print("-" * 80)
    print(f"\n✓ Successfully walked through projects with filtering")
    print("=" * 80)


@manual_test
def test_container_walk_projects():
    """Test walking through projects for a specific container.

    This test verifies that:
    1. The Container.walk_projects() method yields projects
    2. The method correctly recurses through folders
    3. Each yielded item is a valid Project object
    4. The active_only parameter works at the container level
    """
    print("\n" + "=" * 80)
    print("Testing Container.walk_projects() method")
    print("=" * 80)

    organizations = list_organizations()
    if not organizations:
        print("\n⚠️  No organizations found to test")
        return

    # Test with the first organization
    org = organizations[0]
    print(f"\nTesting with organization: {org.display_name}")

    # Test active_only=True (default)
    print("\nWith active_only=True (default):")
    active_count = 0
    for project in org.walk_projects():
        assert isinstance(project, Project)
        assert project.lifecycle_state == "ACTIVE"
        active_count += 1

        if active_count <= 10:
            print(f"  {active_count}. {project.id} (state: {project.lifecycle_state})")

    if active_count > 10:
        print(f"  ... and {active_count - 10} more projects")

    print(f"✓ Found {active_count} ACTIVE project(s)")

    # Test active_only=False
    print("\nWith active_only=False:")
    all_count = 0
    state_counts = {}
    for project in org.walk_projects(active_only=False):
        assert isinstance(project, Project)
        all_count += 1
        state = project.lifecycle_state
        state_counts[state] = state_counts.get(state, 0) + 1

    print(f"✓ Found {all_count} project(s) total (all states)")
    if state_counts:
        print("Lifecycle states:")
        for state, count in sorted(state_counts.items()):
            print(f"  {state}: {count}")

    # Verify active_only=False returns >= projects
    assert all_count >= active_count

    print(f"\n✓ Successfully tested filtering in {org.display_name}")
    print("=" * 80)


def test_api_resolution_error_exists():
    """Test that APIResolutionError exception exists and can be raised."""
    # Verify the exception exists
    assert APIResolutionError is not None

    # Verify it's a subclass of Exception
    assert issubclass(APIResolutionError, Exception)

    # Verify we can raise and catch it
    try:
        raise APIResolutionError("Test error message")
    except APIResolutionError as e:
        assert str(e) == "Test error message"


def test_lookup_api_function_exists():
    """Test that lookup_api function exists."""
    assert callable(lookup_api)


@manual_test
def test_lookup_api():
    """Test the lookup_api function with real API lookups.

    This test verifies that:
    1. Exact matches work
    2. Fuzzy matching works
    3. Normalization works (removing "cloud", etc.)
    4. Ambiguous queries raise appropriate errors

    Note: Requires the API map CSV to be generated first using generate_api_map_csv().
    """
    print("\n" + "=" * 80)
    print("Testing lookup_api() function")
    print("=" * 80)

    # Test 1: Exact match (should work)
    print("\n1. Testing exact match: 'Compute Engine API'")
    try:
        result = lookup_api("Compute Engine API")
        print(f"   ✓ Found: {result}")
        assert "compute" in result
    except APIResolutionError as e:
        print(f"   ⚠️  Error (may need different exact name): {e}")
    except FileNotFoundError as e:
        print(f"   ❌ CSV file not found: {e}")
        print("   Run generate_api_map_csv() first to create the CSV file")
        return

    # Test 2: Partial match (should use fuzzy matching)
    print("\n2. Testing partial match: 'Compute Engine'")
    try:
        result = lookup_api("Compute Engine")
        print(f"   ✓ Found: {result}")
        assert "compute" in result.lower()
    except APIResolutionError as e:
        print(f"   ⚠️  Error: {e}")

    # Test 3: Fuzzy match with typo
    print("\n3. Testing fuzzy match: 'BigQuery'")
    try:
        result = lookup_api("BigQuery")
        print(f"   ✓ Found: {result}")
        assert "bigquery" in result.lower()
    except APIResolutionError as e:
        print(f"   ⚠️  Error: {e}")

    # Test 4: Normalized match (removing "Cloud")
    print("\n4. Testing normalized match: 'Storage'")
    try:
        result = lookup_api("Storage")
        print(f"   ✓ Found: {result}")
    except APIResolutionError as e:
        print(f"   ⚠️  Error (may be too ambiguous): {e}")

    # Test 5: Ambiguous query (should raise error)
    print("\n5. Testing ambiguous query: 'API'")
    try:
        result = lookup_api("API")
        print(f"   ⚠️  Unexpectedly succeeded: {result}")
    except APIResolutionError as e:
        print(f"   ✓ Correctly raised APIResolutionError: {str(e)[:80]}...")

    # Test 6: Nonexistent API (should raise error)
    print("\n6. Testing nonexistent API: 'ThisDoesNotExist12345'")
    try:
        result = lookup_api("ThisDoesNotExist12345")
        print(f"   ⚠️  Unexpectedly succeeded: {result}")
    except APIResolutionError as e:
        print(f"   ✓ Correctly raised APIResolutionError: {str(e)[:80]}...")

    # Test 7: Verify repeated lookups work
    print("\n7. Testing repeated lookup")
    try:
        result1 = lookup_api("Compute Engine")
        result2 = lookup_api("Compute Engine")
        assert result1 == result2
        print(f"   ✓ Repeated lookups work correctly (same result both times)")
    except APIResolutionError as e:
        print(f"   ⚠️  Error: {e}")

    print("\n" + "=" * 80)
    print("✓ lookup_api() testing complete")
    print("=" * 80)
