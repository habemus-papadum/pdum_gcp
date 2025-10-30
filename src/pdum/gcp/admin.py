"""Admin layer for GCP automation using admin bot credentials.

This module provides the foundation for Phase 2 of the architecture - using
the Python GCP API with admin bot credentials to perform automated operations.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml
from google.auth import exceptions as auth_exceptions
from google.cloud import billing_v1
from google.oauth2 import service_account


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
