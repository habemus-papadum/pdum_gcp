"""Admin layer for GCP automation using admin bot credentials.

This module provides the foundation for Phase 2 of the architecture - using
the Python GCP API with admin bot credentials to perform automated operations.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml
from google.api_core import exceptions as api_exceptions
from google.auth import exceptions as auth_exceptions
from google.cloud import billing_v1, iam_admin_v1, resourcemanager_v3
from google.cloud import service_usage_v1
from google.iam.v1 import iam_policy_pb2, policy_pb2
from google.oauth2 import service_account
from google.protobuf import field_mask_pb2


class AdminCredentialsError(Exception):
    """Exception raised when admin credentials cannot be loaded."""

    pass


@dataclass
class BillingAccount:
    """Information about a GCP billing account.

    Attributes:
        name: The resource name (e.g., "billingAccounts/0X0X0X-0X0X0X-0X0X0X")
        display_name: The display name of the billing account
        open: Whether the billing account is open and active
        master_billing_account: The master billing account (for subaccounts)
    """

    name: str
    display_name: str
    open: bool
    master_billing_account: str

    @property
    def account_id(self) -> str:
        """Get the billing account ID without the 'billingAccounts/' prefix."""
        return self.name.replace("billingAccounts/", "")


@dataclass
class Project:
    """Information about a GCP project.

    Attributes:
        name: The full resource name (e.g., "projects/my-project-id")
        project_id: The project ID
        display_name: The human-readable display name
        labels: Dictionary of project labels
        state: Project state (e.g., "ACTIVE", "DELETE_REQUESTED")
    """

    name: str
    project_id: str
    display_name: str
    labels: dict[str, str]
    state: str


@dataclass
class AdminCredentials:
    """Container for admin bot credentials and configuration.

    Attributes:
        config_name: The gcloud configuration name
        config_data: The parsed config.yaml data (admin_bot, trusted_humans)
        google_cloud_credentials: Google Cloud service account credentials object
    """

    config_name: str
    config_data: dict
    google_cloud_credentials: service_account.Credentials

    @property
    def admin_bot_email(self) -> str:
        """Get the admin bot service account email."""
        return self.config_data.get("admin_bot", "")

    @property
    def trusted_humans(self) -> list[str]:
        """Get the list of trusted human email addresses."""
        return self.config_data.get("trusted_humans", [])

    @property
    def project_id(self) -> Optional[str]:
        """Get the project ID from the credentials."""
        return self.google_cloud_credentials.project_id

    def list_billing_accounts(self) -> list[BillingAccount]:
        """List all billing accounts accessible to the admin bot.

        Returns:
            List of BillingAccount objects

        Raises:
            Exception: If the API call fails

        Example:
            >>> creds = admin.load_admin_credentials("work")
            >>> accounts = creds.list_billing_accounts()
            >>> for account in accounts:
            ...     print(f"{account.display_name}: {account.account_id} (open={account.open})")
        """
        client = billing_v1.CloudBillingClient(credentials=self.google_cloud_credentials)

        request = billing_v1.ListBillingAccountsRequest()

        # List all billing accounts
        page_result = client.list_billing_accounts(request=request)

        accounts = []
        for account in page_result:
            accounts.append(
                BillingAccount(
                    name=account.name,
                    display_name=account.display_name,
                    open=account.open,
                    master_billing_account=account.master_billing_account,
                )
            )

        return accounts

    def get_default_billing_account(self) -> BillingAccount:
        """Get the default billing account (only works if there's exactly one open account).

        This is useful for automation scenarios where you want to use a billing account
        without explicit selection, but only when there's no ambiguity.

        Returns:
            The single open BillingAccount

        Raises:
            AdminCredentialsError: If there are zero or multiple open billing accounts

        Example:
            >>> creds = admin.load_admin_credentials("work")
            >>> account = creds.get_default_billing_account()
            >>> print(f"Using billing account: {account.display_name} ({account.account_id})")
        """
        # Get all billing accounts
        all_accounts = self.list_billing_accounts()

        # Filter to only open accounts
        open_accounts = [acc for acc in all_accounts if acc.open]

        # Check for exactly one open account
        if len(open_accounts) == 0:
            raise AdminCredentialsError(
                "No open billing accounts found.\n\n"
                "The admin bot needs access to at least one open billing account.\n"
                "To grant access, run:\n"
                f"  pdum_gcp manage-billing --config {self.config_name}"
            )

        if len(open_accounts) > 1:
            account_list = "\n".join(
                f"  - {acc.display_name} ({acc.account_id})" for acc in open_accounts
            )
            raise AdminCredentialsError(
                f"Multiple open billing accounts found ({len(open_accounts)}):\n\n"
                f"{account_list}\n\n"
                "Cannot determine default billing account.\n"
                "Please specify which billing account to use explicitly."
            )

        # Exactly one open account - return it
        return open_accounts[0]

    def create_project(
        self,
        project_id: str,
        display_name: Optional[str] = None,
        billing_account_id: Optional[str] = None,
        enable_apis: Optional[list[str]] = None,
    ) -> Project:
        """Create a new GCP project with billing, service account, and APIs enabled.

        This method creates a complete GCP project setup including:
        - Project creation with labels
        - Billing account linking
        - Service account creation (admin-robot)
        - IAM roles (owner) for service account and trusted humans
        - API/service enabling

        The method is idempotent - it will skip existing resources gracefully.

        Args:
            project_id: The project ID (must be globally unique)
            display_name: Human-readable project name (defaults to project_id)
            billing_account_id: Billing account ID to link (defaults to get_default_billing_account())
            enable_apis: List of APIs to enable (defaults to ML-focused APIs)

        Returns:
            Project object with project information

        Raises:
            AdminCredentialsError: If project creation fails or permissions are insufficient

        Example:
            >>> creds = admin.load_admin_credentials("work")
            >>> project = creds.create_project(
            ...     project_id="my-ml-project-12345",
            ...     display_name="My ML Project"
            ... )
            >>> print(f"Created project: {project.project_id}")
        """
        # Use defaults if not provided
        if display_name is None:
            display_name = project_id

        if billing_account_id is None:
            default_billing = self.get_default_billing_account()
            billing_account_id = default_billing.account_id

        if enable_apis is None:
            # Default ML-focused APIs
            enable_apis = [
                "firestore.googleapis.com",
                "aiplatform.googleapis.com",  # Vertex AI / Gemini
                "container.googleapis.com",  # GKE
                "storage-api.googleapis.com",  # Cloud Storage
                "storage-component.googleapis.com",  # Cloud Storage Component
                "bigtable.googleapis.com",  # BigTable
                "bigtableadmin.googleapis.com",  # BigTable Admin
            ]

        # Step 1: Create or verify project exists
        project = self._create_or_get_project(project_id, display_name)

        # Step 2: Link billing account
        self._link_project_billing(project_id, billing_account_id)

        # Step 3: Create service account "admin-robot"
        sa_email = self._create_project_service_account(project_id)

        # Step 4: Grant owner IAM roles
        self._grant_project_owners(project_id, sa_email)

        # Step 5: Enable APIs/services
        self._enable_project_apis(project_id, enable_apis)

        return project

    def _create_or_get_project(self, project_id: str, display_name: str) -> Project:
        """Create a new project or get existing one (idempotent).

        Args:
            project_id: The project ID
            display_name: The display name

        Returns:
            Project object

        Raises:
            AdminCredentialsError: If project creation fails
        """
        client = resourcemanager_v3.ProjectsClient(credentials=self.google_cloud_credentials)

        # Try to get existing project first
        try:
            existing = client.get_project(name=f"projects/{project_id}")
            # Project exists - verify it's active
            if existing.state != resourcemanager_v3.Project.State.ACTIVE:
                raise AdminCredentialsError(
                    f"Project {project_id} exists but is not ACTIVE (state: {existing.state.name})"
                )

            # Update labels if needed
            labels = dict(existing.labels)
            if "managed-by" not in labels:
                labels["managed-by"] = "pdum_gcp"
                update_mask = field_mask_pb2.FieldMask(paths=["labels"])
                update_request = resourcemanager_v3.UpdateProjectRequest(
                    project=resourcemanager_v3.Project(
                        name=existing.name,
                        labels=labels,
                    ),
                    update_mask=update_mask,
                )
                operation = client.update_project(request=update_request)
                operation.result(timeout=300)

            return Project(
                name=existing.name,
                project_id=project_id,
                display_name=existing.display_name,
                labels=labels,
                state=existing.state.name,
            )

        except (api_exceptions.NotFound, api_exceptions.PermissionDenied):
            # Project doesn't exist - create it
            # Note: GCP returns PermissionDenied (403) instead of NotFound (404)
            # when a project doesn't exist (for security reasons)
            pass

        # Create new project
        try:
            request = resourcemanager_v3.CreateProjectRequest(
                project=resourcemanager_v3.Project(
                    project_id=project_id,
                    display_name=display_name,
                    labels={"managed-by": "pdum_gcp"},
                )
            )
            operation = client.create_project(request=request)
            result = operation.result(timeout=300)

            return Project(
                name=result.name,
                project_id=project_id,
                display_name=result.display_name,
                labels=dict(result.labels),
                state=result.state.name,
            )

        except Exception as e:
            raise AdminCredentialsError(
                f"Failed to create project {project_id}: {e}"
            ) from e

    def _link_project_billing(self, project_id: str, billing_account_id: str) -> None:
        """Link billing account to project (idempotent).

        Args:
            project_id: The project ID
            billing_account_id: The billing account ID

        Raises:
            AdminCredentialsError: If billing linking fails
        """
        client = billing_v1.CloudBillingClient(credentials=self.google_cloud_credentials)

        # Check if billing is already linked
        try:
            billing_info = client.get_project_billing_info(name=f"projects/{project_id}")
            billing_account_name = f"billingAccounts/{billing_account_id}"

            if (
                billing_info.billing_account_name == billing_account_name
                and billing_info.billing_enabled
            ):
                # Already linked correctly
                return
        except Exception:
            # If we can't get billing info, try to set it
            pass

        # Link billing account
        try:
            request = billing_v1.UpdateProjectBillingInfoRequest(
                name=f"projects/{project_id}",
                project_billing_info=billing_v1.ProjectBillingInfo(
                    billing_account_name=f"billingAccounts/{billing_account_id}"
                ),
            )
            client.update_project_billing_info(request=request)
        except Exception as e:
            raise AdminCredentialsError(
                f"Failed to link billing account to project {project_id}: {e}"
            ) from e

    def _create_project_service_account(self, project_id: str) -> str:
        """Create admin-robot service account in project (idempotent).

        Args:
            project_id: The project ID

        Returns:
            Service account email

        Raises:
            AdminCredentialsError: If service account creation fails
        """
        client = iam_admin_v1.IAMClient(credentials=self.google_cloud_credentials)
        sa_email = f"admin-robot@{project_id}.iam.gserviceaccount.com"

        # Try to get existing service account
        try:
            client.get_service_account(name=f"projects/{project_id}/serviceAccounts/{sa_email}")
            # Service account exists - skip creation
            return sa_email
        except api_exceptions.NotFound:
            # Service account doesn't exist - create it
            pass

        # Create service account
        try:
            request = iam_admin_v1.CreateServiceAccountRequest(
                name=f"projects/{project_id}",
                account_id="admin-robot",
                service_account=iam_admin_v1.ServiceAccount(
                    display_name="Admin Robot"
                ),
            )
            client.create_service_account(request=request)
            return sa_email
        except Exception as e:
            raise AdminCredentialsError(
                f"Failed to create service account in project {project_id}: {e}"
            ) from e

    def _grant_project_owners(self, project_id: str, sa_email: str) -> None:
        """Grant owner role to service account and trusted humans (idempotent).

        Args:
            project_id: The project ID
            sa_email: Service account email

        Raises:
            AdminCredentialsError: If IAM policy update fails
        """
        client = resourcemanager_v3.ProjectsClient(credentials=self.google_cloud_credentials)

        # Get current IAM policy
        try:
            policy = client.get_iam_policy(
                request=iam_policy_pb2.GetIamPolicyRequest(
                    resource=f"projects/{project_id}"
                )
            )
        except Exception as e:
            raise AdminCredentialsError(
                f"Failed to get IAM policy for project {project_id}: {e}"
            ) from e

        # Build list of members that should have owner role
        desired_owners = [f"serviceAccount:{sa_email}"]
        for human in self.trusted_humans:
            desired_owners.append(f"user:{human}")

        # Find existing owner binding
        owner_binding = None
        for binding in policy.bindings:
            if binding.role == "roles/owner":
                owner_binding = binding
                break

        # Add missing owners
        if owner_binding is None:
            # No owner binding exists - create one
            owner_binding = policy_pb2.Binding(
                role="roles/owner",
                members=desired_owners,
            )
            policy.bindings.append(owner_binding)
        else:
            # Owner binding exists - add missing members
            existing_members = set(owner_binding.members)
            for member in desired_owners:
                if member not in existing_members:
                    owner_binding.members.append(member)

        # Set updated IAM policy
        try:
            client.set_iam_policy(
                request=iam_policy_pb2.SetIamPolicyRequest(
                    resource=f"projects/{project_id}",
                    policy=policy,
                )
            )
        except Exception as e:
            raise AdminCredentialsError(
                f"Failed to set IAM policy for project {project_id}: {e}"
            ) from e

    def _enable_project_apis(self, project_id: str, apis: list[str]) -> None:
        """Enable APIs/services for project (idempotent, best-effort).

        Args:
            project_id: The project ID
            apis: List of API names to enable

        Note:
            This method continues on errors - API enabling failures won't fail the entire operation.
        """
        client = service_usage_v1.ServiceUsageClient(credentials=self.google_cloud_credentials)

        for api in apis:
            try:
                # Check if API is already enabled
                service_name = f"projects/{project_id}/services/{api}"
                try:
                    get_request = service_usage_v1.GetServiceRequest(name=service_name)
                    service = client.get_service(request=get_request)
                    if service.state == service_usage_v1.State.ENABLED:
                        # Already enabled - skip
                        continue
                except (api_exceptions.NotFound, api_exceptions.PermissionDenied):
                    # Service not found or not accessible - proceed with enabling
                    pass

                # Enable the service
                enable_request = service_usage_v1.EnableServiceRequest(name=service_name)
                operation = client.enable_service(request=enable_request)
                # Wait for operation with timeout
                operation.result(timeout=300)

            except Exception:
                # Continue on errors - API enabling is best-effort
                # Don't fail the entire project creation if one API fails
                continue


def get_config_dir(config_name: str) -> Path:
    """Get the configuration directory path for a given config.

    Args:
        config_name: The gcloud configuration name

    Returns:
        Path to the config directory
    """
    home = Path.home()
    return home / ".config" / "gcloud" / "pdum_gcp" / config_name


def load_admin_credentials(config: str = "default") -> AdminCredentials:
    """Load admin bot credentials for a given configuration.

    This function loads the admin bot credentials from the local configuration
    directory (~/.config/gcloud/pdum_gcp/<config>/).

    Args:
        config: The gcloud configuration name (defaults to "default")

    Returns:
        AdminCredentials object with loaded credentials

    Raises:
        AdminCredentialsError: If credentials cannot be loaded

    Example:
        >>> from pdum.gcp import admin
        >>> creds = admin.load_admin_credentials("work")
        >>> print(creds.admin_bot_email)
        admin-robot@h-papadum-admin-abc123.iam.gserviceaccount.com
    """
    config_dir = get_config_dir(config)
    config_file = config_dir / "config.yaml"
    key_file = config_dir / "admin.json"

    # Check if config directory exists
    if not config_dir.exists():
        raise AdminCredentialsError(
            f"Configuration directory not found: {config_dir}\n\n"
            f"To set up admin credentials for config '{config}':\n\n"
            f"  1. If you haven't bootstrapped yet, run:\n"
            f"     pdum_gcp bootstrap --config {config}\n\n"
            f"  2. If admin bot already exists (bootstrapped on another machine), run:\n"
            f"     pdum_gcp import --config {config}\n\n"
            f"See README.md for more information."
        )

    # Check if config.yaml exists
    if not config_file.exists():
        raise AdminCredentialsError(
            f"Configuration file not found: {config_file}\n\n"
            f"The directory exists but config.yaml is missing. This suggests an incomplete setup.\n\n"
            f"To fix this:\n\n"
            f"  1. If you haven't bootstrapped yet, run:\n"
            f"     pdum_gcp bootstrap --config {config}\n\n"
            f"  2. If admin bot already exists (bootstrapped on another machine), run:\n"
            f"     pdum_gcp import --config {config}\n"
        )

    # Check if admin.json exists
    if not key_file.exists():
        raise AdminCredentialsError(
            f"Service account key not found: {key_file}\n\n"
            f"The config.yaml exists but admin.json is missing.\n\n"
            f"To download the service account key:\n\n"
            f"  If admin bot already exists (bootstrapped on another machine), run:\n"
            f"     pdum_gcp import --config {config}\n\n"
            f"  Otherwise, you may need to manually download the key:\n"
            f"     gcloud iam service-accounts keys create {key_file} \\\n"
            f"       --iam-account=<admin-bot-email> \\\n"
            f"       --project=<project-id>\n"
        )

    # Load config.yaml
    try:
        with open(config_file, "r") as f:
            config_data = yaml.safe_load(f)

        if not isinstance(config_data, dict):
            raise AdminCredentialsError(
                f"Invalid config.yaml format in {config_file}\n"
                f"Expected a YAML dictionary with 'admin_bot' and 'trusted_humans' keys."
            )

        if "admin_bot" not in config_data:
            raise AdminCredentialsError(
                f"Missing 'admin_bot' key in {config_file}\n"
                f"The config.yaml file should contain the admin bot email address."
            )

    except yaml.YAMLError as e:
        raise AdminCredentialsError(
            f"Failed to parse config.yaml: {config_file}\n"
            f"Error: {e}\n"
            f"The file may be corrupted. Consider re-running:\n"
            f"  pdum_gcp import --config {config}"
        ) from e
    except OSError as e:
        raise AdminCredentialsError(
            f"Failed to read config.yaml: {config_file}\n"
            f"Error: {e}"
        ) from e

    # Load service account credentials from JSON key file
    try:
        credentials = service_account.Credentials.from_service_account_file(
            str(key_file),
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
    except auth_exceptions.DefaultCredentialsError as e:
        raise AdminCredentialsError(
            f"Failed to load service account credentials from {key_file}\n"
            f"Error: {e}\n"
            f"The key file may be invalid or corrupted. Consider re-running:\n"
            f"  pdum_gcp import --config {config}"
        ) from e
    except OSError as e:
        raise AdminCredentialsError(
            f"Failed to read service account key file: {key_file}\n"
            f"Error: {e}"
        ) from e
    except Exception as e:
        raise AdminCredentialsError(
            f"Unexpected error loading credentials from {key_file}\n"
            f"Error: {e}"
        ) from e

    # Validate that the credentials are for the expected admin bot
    if credentials.service_account_email != config_data["admin_bot"]:
        raise AdminCredentialsError(
            f"Credential mismatch detected!\n"
            f"  config.yaml admin_bot: {config_data['admin_bot']}\n"
            f"  admin.json account:    {credentials.service_account_email}\n\n"
            f"The service account in admin.json doesn't match the one in config.yaml.\n"
            f"This suggests the files are out of sync. Consider re-running:\n"
            f"  pdum_gcp import --config {config}"
        )

    return AdminCredentials(
        config_name=config,
        config_data=config_data,
        google_cloud_credentials=credentials,
    )


def list_available_configs() -> list[str]:
    """List all available admin configurations.

    Returns:
        List of configuration names that have been set up

    Example:
        >>> from pdum.gcp import admin
        >>> configs = admin.list_available_configs()
        >>> print(configs)
        ['default', 'work', 'personal']
    """
    base_dir = Path.home() / ".config" / "gcloud" / "pdum_gcp"

    if not base_dir.exists():
        return []

    configs = []
    for item in base_dir.iterdir():
        if item.is_dir():
            # Check if it has the required files
            config_file = item / "config.yaml"
            key_file = item / "admin.json"
            if config_file.exists() and key_file.exists():
                configs.append(item.name)

    return sorted(configs)
