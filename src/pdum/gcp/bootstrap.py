"""Bootstrap a super-admin service account for GCP automation.

This module provides idempotent functionality to create and configure
a GCP service account with organization-level admin permissions.
"""

import json
import subprocess
from typing import Optional

from InquirerPy import inquirer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

# --- Configuration ---
BOT_PROJECT_PREFIX = "h-papadum-admin"
BOT_SA_NAME = "admin-robot"

console = Console()

# Global verbose flag
_verbose = False


def set_verbose(enabled: bool) -> None:
    """Set global verbose flag."""
    global _verbose
    _verbose = enabled


# Import common utilities
# Note: Import at end to avoid circular dependencies
def _import_utils():
    """Import utils functions (deferred to avoid circular imports)."""
    from pdum.gcp import utils
    return utils


# Expose utils functions at module level for backward compatibility
def choose_config():
    """Choose a gcloud configuration."""
    return _import_utils().choose_config()


def get_current_account_email():
    """Get current account email."""
    return _import_utils().get_current_account_email()


def save_config_file(config_name, bot_email, trusted_humans, dry_run=False):
    """Save config file."""
    return _import_utils().save_config_file(config_name, bot_email, trusted_humans, dry_run)


def download_service_account_key(config_name, sa_email, project_id, dry_run=False):
    """Download service account key."""
    utils = _import_utils()
    # Add the step header that bootstrap expects
    console.print("\n[yellow]--- Step 5: Download Service Account Key ---[/yellow]")
    return utils.download_service_account_key(config_name, sa_email, project_id, dry_run)


class GCloudError(Exception):
    """Exception raised for gcloud command errors."""

    pass


def run_gcloud(args: list[str], check: bool = True, capture: bool = True, config: Optional[str] = None) -> Optional[str]:
    """Run a gcloud command and return output.

    Args:
        args: List of arguments to pass to gcloud
        check: If True, raise exception on non-zero exit code
        capture: If True, capture and return stdout
        config: Optional gcloud configuration name to use with --configuration flag

    Returns:
        Command stdout if capture=True, None otherwise
        Returns None if check=False and command failed

    Raises:
        GCloudError: If command fails and check=True
    """
    cmd = ["gcloud"]

    # Add --configuration flag if config is specified
    if config:
        cmd.extend(["--configuration", config])

    cmd.extend(args)

    # Print command in verbose mode
    if _verbose:
        console.print(f"[dim]$ {' '.join(cmd)}[/dim]")

    try:
        result = subprocess.run(
            cmd,
            check=False,  # Never let subprocess raise, we handle errors ourselves
            capture_output=capture,
            text=True,
        )

        # Check if command failed
        if result.returncode != 0:
            if check:
                raise GCloudError(f"Command failed: {' '.join(cmd)}\n{result.stderr}")
            return None

        return result.stdout.strip() if capture else None
    except subprocess.CalledProcessError as e:
        # This shouldn't happen since check=False above, but keep for safety
        if check:
            raise GCloudError(f"Command failed: {' '.join(cmd)}\n{e.stderr}") from e
        return None


def get_config_value(key: str) -> Optional[str]:
    """Get a value from gcloud config."""
    try:
        value = run_gcloud(["config", "get-value", key], check=False)
        return value if value else None
    except Exception:
        return None


def set_config_value(key: str, value: str) -> None:
    """Set a value in gcloud config.

    This is a best-effort operation - if it fails, we continue anyway.
    """
    try:
        run_gcloud(["config", "set", key, value], capture=False)
    except GCloudError:
        # Some gcloud configurations don't support custom properties
        # This is non-critical, so we just log and continue
        console.print(
            f"[dim]Note: Could not save {key} to config "
            "(custom properties may not be supported)[/dim]"
        )


def get_active_config() -> str:
    """Get the currently active gcloud configuration."""
    result = run_gcloud([
        "config", "configurations", "list",
        "--filter=IS_ACTIVE:True",
        "--format=value(NAME)"
    ])
    if not result:
        raise GCloudError("Could not determine active gcloud configuration")
    return result


def activate_config(config_name: str, dry_run: bool = False) -> None:
    """Activate a gcloud configuration."""
    if dry_run:
        console.print(f"[dim][DRY RUN] Would activate config: {config_name}[/dim]")
    else:
        console.print(f"[cyan]Activating config:[/cyan] {config_name}")
        run_gcloud(["config", "configurations", "activate", config_name], capture=False)


def restore_config(original_config: str, original_project: Optional[str], dry_run: bool = False) -> None:
    """Restore original gcloud configuration."""
    console.print("\n[yellow]--- Cleanup ---[/yellow]")
    if dry_run:
        console.print(f"[dim][DRY RUN] Would restore original gcloud config: {original_config}[/dim]")
        if original_project:
            console.print(f"[dim][DRY RUN] Would restore project: {original_project}[/dim]")
    else:
        console.print(f"[cyan]Restoring original gcloud config:[/cyan] {original_config}")
        activate_config(original_config, dry_run=False)
        if original_project:
            set_config_value("project", original_project)
    console.print("[green]Bootstrap complete.[/green]")


def get_available_configs() -> list[dict[str, str]]:
    """Get list of available gcloud configurations.

    Returns:
        List of dicts with 'name', 'is_active', and 'account' keys
    """
    output = run_gcloud([
        "config",
        "configurations",
        "list",
        "--format=json",
    ])
    if not output:
        return []

    import json
    configs = json.loads(output)
    return configs




def get_billing_accounts() -> list[dict[str, str]]:
    """Get list of available billing accounts (open only).

    Returns:
        List of dicts with billing account info (only open accounts)
    """
    output = run_gcloud([
        "billing",
        "accounts",
        "list",
        "--format=json",
    ])
    if not output:
        return []

    import json
    accounts = json.loads(output)

    # Filter to only include open accounts
    open_accounts = [acc for acc in accounts if acc.get("open", False)]
    return open_accounts


def choose_billing_account() -> str:
    """Interactively choose a billing account.

    Returns:
        The selected billing account ID
    """
    accounts = get_billing_accounts()

    if not accounts:
        raise GCloudError("No open billing accounts found. You need at least one open billing account.")

    # If only one account, auto-select it
    if len(accounts) == 1:
        account = accounts[0]
        name = account.get("displayName", "")
        account_id = account.get("name", "").replace("billingAccounts/", "")
        console.print(f"[cyan]Using only available billing account:[/cyan] {name} ({account_id})")
        return account_id

    # Format choices with additional info
    choices = []
    for account in accounts:
        name = account.get("displayName", "")
        account_id = account.get("name", "").replace("billingAccounts/", "")
        choices.append({
            "name": f"{name} ({account_id})",
            "value": account_id,
        })

    result = inquirer.select(
        message="Select billing account:",
        choices=choices,
    ).execute()

    return result


def get_organizations() -> list[dict[str, str]]:
    """Get list of organizations accessible to the user.

    Returns:
        List of dicts with organization info
    """
    output = run_gcloud([
        "organizations",
        "list",
        "--format=json",
    ])
    if not output:
        return []

    import json
    orgs = json.loads(output)
    return orgs


def choose_organization() -> Optional[str]:
    """Interactively choose an organization.

    Returns:
        The selected organization ID, or None if no organizations available
    """
    orgs = get_organizations()

    if not orgs:
        console.print(
            "[yellow]No organizations found. "
            "Continuing without organization (personal account mode).[/yellow]"
        )
        return None

    # If only one org, auto-select it
    if len(orgs) == 1:
        org = orgs[0]
        name = org.get("displayName", "")
        org_id = org.get("name", "").replace("organizations/", "")
        console.print(f"[cyan]Using only available organization:[/cyan] {name} ({org_id})")
        return org_id

    # Format choices with additional info
    choices = []
    for org in orgs:
        name = org.get("displayName", "")
        org_id = org.get("name", "").replace("organizations/", "")
        choices.append({
            "name": f"{name} ({org_id})",
            "value": org_id,
        })

    result = inquirer.select(
        message="Select organization:",
        choices=choices,
    ).execute()

    return result


def get_or_create_automation_folder(org_id: str, dry_run: bool = False) -> Optional[str]:
    """Get or create the Automation folder.

    Args:
        org_id: The organization ID
        dry_run: If True, don't actually create anything

    Returns:
        The folder ID, or None if dry run or no permissions
    """
    console.print("[cyan]Checking for Automation folder...[/cyan]")

    # Try to search for existing folder
    try:
        output = run_gcloud([
            "resource-manager",
            "folders",
            "list",
            f"--organization={org_id}",
            "--filter=displayName:Automation",
            "--format=json",
        ])

        if output:
            import json
            folders = json.loads(output)
            if folders:
                folder_id = folders[0].get("name", "").replace("folders/", "")
                console.print(f"[green]Found existing Automation folder:[/green] {folder_id}")
                return folder_id
    except GCloudError as e:
        # Check if it's a permission error
        if "PERMISSION_DENIED" in str(e) or "does not have permission" in str(e):
            console.print(
                "[yellow]No permission to list folders. "
                "Skipping Automation folder - will create project directly in org.[/yellow]"
            )
            return None
        # Re-raise if it's a different error
        raise

    # Create folder if it doesn't exist
    if dry_run:
        console.print("[dim][DRY RUN] Would create Automation folder[/dim]")
        return None

    console.print("[yellow]Creating Automation folder...[/yellow]")
    try:
        output = run_gcloud([
            "resource-manager",
            "folders",
            "create",
            "--display-name=Automation",
            f"--organization={org_id}",
            "--format=json",
        ])

        if output:
            import json
            folder_data = json.loads(output)
            folder_id = folder_data.get("name", "").replace("folders/", "")
            console.print(f"[green]Created Automation folder:[/green] {folder_id}")
            return folder_id
    except GCloudError as e:
        # Check if it's a permission error
        if "PERMISSION_DENIED" in str(e) or "does not have permission" in str(e):
            console.print(
                "[yellow]No permission to create folders. "
                "Will create project directly in org.[/yellow]"
            )
            return None
        # Re-raise if it's a different error
        raise

    raise GCloudError("Failed to create Automation folder")


def generate_random_hex(length: int = 4) -> str:
    """Generate a random hex string."""
    import secrets

    return secrets.token_hex(length)


def determine_bot_project_id() -> str:
    """Determine or generate the bot project ID (idempotent).

    Returns:
        The bot project ID to use
    """
    console.print("\n[yellow]--- Step 0: Determine Bot Project ID ---[/yellow]")

    console.print(
        f"[cyan]Searching for existing project with prefix '{BOT_PROJECT_PREFIX}-*'[/cyan]"
    )

    # Search for existing project using regex filter
    # Note: ~ is for regex matching in gcloud filters
    existing_id = run_gcloud([
        "projects",
        "list",
        f"--filter=projectId ~ ^{BOT_PROJECT_PREFIX}-.*",
        "--limit=1",
        "--format=value(projectId)",
    ])

    if existing_id:
        console.print(f"[green]Found existing project:[/green] {existing_id}")
        return existing_id

    console.print("[yellow]No existing project found. Generating new ID.[/yellow]")
    random_hex = generate_random_hex(4)
    bot_project_id = f"{BOT_PROJECT_PREFIX}-{random_hex}"
    console.print(f"[cyan]New project ID will be:[/cyan] {bot_project_id}")

    return bot_project_id


def get_organization_id(config_name: str) -> str:
    """Get the organization ID for the current project.

    Args:
        config_name: The gcloud config name

    Returns:
        The organization ID

    Raises:
        GCloudError: If no project is set or org cannot be determined
    """
    console.print("[cyan]Fetching Organization ID...[/cyan]")
    current_project = get_config_value("core/project")

    if not current_project:
        raise GCloudError(
            f"Error: The config '{config_name}' has no active project. Please set one."
        )

    # Get ancestors and take the last line (org ID)
    ancestors_output = run_gcloud([
        "projects",
        "get-ancestors",
        current_project,
        "--format=value(id)",
    ])

    if not ancestors_output:
        raise GCloudError(f"Could not determine organization for project {current_project}")

    org_id = ancestors_output.split("\n")[-1].strip()
    console.print(f"[green]Found Organization ID:[/green] {org_id}")
    return org_id


def project_exists(project_id: str) -> bool:
    """Check if a GCP project exists."""
    result = run_gcloud(
        ["projects", "describe", project_id, "--quiet"],
        check=False,
    )
    return result is not None


def create_project(
    project_id: str,
    org_id: Optional[str] = None,
    folder_id: Optional[str] = None,
    dry_run: bool = False
) -> None:
    """Create a GCP project if it doesn't exist.

    Args:
        project_id: The project ID to create
        org_id: Optional organization ID
        folder_id: Optional folder ID to create project in
        dry_run: If True, don't actually create
    """
    console.print("\n[yellow]--- Step 1: Project ---[/yellow]")

    if project_exists(project_id):
        console.print(f"[green]Project {project_id} already exists. Skipping creation.[/green]")
        return

    if dry_run:
        if folder_id:
            console.print(
                f"[dim][DRY RUN] Would create project: {project_id} in folder {folder_id}[/dim]"
            )
        elif org_id:
            console.print(
                f"[dim][DRY RUN] Would create project: {project_id} in org {org_id}[/dim]"
            )
        else:
            console.print(
                f"[dim][DRY RUN] Would create project: {project_id} (no org)[/dim]"
            )
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(description=f"Creating project: {project_id}...", total=None)

        args = [
            "projects",
            "create",
            project_id,
            "--name=Admin Service Bots",
        ]

        if folder_id:
            args.append(f"--folder={folder_id}")
        elif org_id:
            args.append(f"--organization={org_id}")
        # If neither folder nor org, create project without parent

        run_gcloud(args, capture=False)

    console.print("[green]Project created.[/green]")


def add_project_owner(project_id: str, email: str, dry_run: bool = False) -> None:
    """Add a user as owner of the project (idempotent).

    Args:
        project_id: The project ID
        email: The email address to add as owner
        dry_run: If True, don't actually add
    """
    console.print("\n[yellow]--- Step 1.5: Add Project Owner ---[/yellow]")

    if dry_run:
        console.print(f"[dim][DRY RUN] Would add {email} as owner of {project_id}[/dim]")
        return

    # Check if user already has owner role
    console.print(f"[cyan]Checking if {email} is already an owner...[/cyan]")

    try:
        # Get current IAM policy
        policy_output = run_gcloud([
            "projects",
            "get-iam-policy",
            project_id,
            "--format=json",
        ])

        if policy_output:
            import json
            policy = json.loads(policy_output)
            bindings = policy.get("bindings", [])

            # Check if user already has owner role
            for binding in bindings:
                if binding.get("role") == "roles/owner":
                    members = binding.get("members", [])
                    if f"user:{email}" in members:
                        console.print(
                            f"[green]{email} is already an owner of {project_id}. Skipping.[/green]"
                        )
                        return
    except GCloudError:
        # If we can't get the policy, we'll try to add anyway
        console.print("[yellow]Could not check existing policy, will attempt to add owner role.[/yellow]")

    # Add owner role
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(description=f"Adding {email} as owner...", total=None)

        run_gcloud([
            "projects",
            "add-iam-policy-binding",
            project_id,
            f"--member=user:{email}",
            "--role=roles/owner",
        ])

    console.print(f"[green]{email} added as owner of {project_id}.[/green]")


def link_billing_account(project_id: str, billing_id: str, dry_run: bool = False) -> None:
    """Link a billing account to the project (idempotent).

    Args:
        project_id: The project ID
        billing_id: The billing account ID
        dry_run: If True, don't actually link
    """
    console.print("\n[yellow]--- Step 2: Billing ---[/yellow]")

    if dry_run:
        console.print(
            f"[dim][DRY RUN] Would link project {project_id} to "
            f"billing account {billing_id}[/dim]"
        )
        return

    billing_account_name = f"billingAccounts/{billing_id}"

    # Get current billing info (only if project exists)
    if project_exists(project_id):
        current_billing = run_gcloud([
            "billing",
            "projects",
            "describe",
            project_id,
            "--format=value(billingAccountName)",
        ])
        is_enabled = run_gcloud([
            "billing",
            "projects",
            "describe",
            project_id,
            "--format=value(billingEnabled)",
        ])

        if current_billing == billing_account_name and is_enabled == "True":
            console.print(
                f"[green]Project {project_id} is already linked to "
                f"billing account {billing_id}.[/green]"
            )
            return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(
            description=f"Linking project {project_id} to billing account {billing_id}...",
            total=None,
        )
        run_gcloud([
            "billing",
            "projects",
            "link",
            project_id,
            f"--billing-account={billing_id}",
        ], capture=False)

    console.print("[green]Billing account linked.[/green]")


def api_is_enabled(project_id: str, api: str) -> bool:
    """Check if an API is enabled for a project.

    Args:
        project_id: The project ID
        api: The API name (e.g., 'iam.googleapis.com')

    Returns:
        True if the API is enabled, False otherwise
    """
    result = run_gcloud(
        [
            "services",
            "list",
            f"--project={project_id}",
            f"--filter=config.name:{api}",
            "--format=value(config.name)",
        ],
        check=False,
    )
    return result == api


def enable_api(project_id: str, api: str, api_display_name: str, dry_run: bool = False) -> None:
    """Enable an API for a project (idempotent).

    Args:
        project_id: The project ID
        api: The API name (e.g., 'iam.googleapis.com')
        api_display_name: Human-readable name for display
        dry_run: If True, don't actually enable
    """
    if api_is_enabled(project_id, api):
        console.print(f"[green]API {api_display_name} is already enabled. Skipping.[/green]")
        return

    if dry_run:
        console.print(f"[dim][DRY RUN] Would enable API: {api_display_name}[/dim]")
        return

    console.print(f"[cyan]Enabling {api_display_name}...[/cyan]")
    run_gcloud([
        "services",
        "enable",
        api,
        f"--project={project_id}",
    ])
    console.print(f"[green]API {api_display_name} enabled.[/green]")


def enable_required_apis(project_id: str, dry_run: bool = False) -> None:
    """Enable all required APIs for the admin project (idempotent).

    Args:
        project_id: The project ID
        dry_run: If True, don't actually enable APIs
    """
    console.print("\n[yellow]--- Step 2.5: Enable Required APIs ---[/yellow]")

    # List of APIs to enable with display names
    apis = [
        ("serviceusage.googleapis.com", "Service Usage API"),
        ("cloudresourcemanager.googleapis.com", "Cloud Resource Manager API"),
        ("iam.googleapis.com", "IAM API"),
        ("cloudbilling.googleapis.com", "Cloud Billing API"),
    ]

    for api, display_name in apis:
        enable_api(project_id, api, display_name, dry_run=dry_run)


def service_account_exists(sa_email: str, project_id: str) -> bool:
    """Check if a service account exists."""
    result = run_gcloud(
        [
            "iam",
            "service-accounts",
            "describe",
            sa_email,
            f"--project={project_id}",
            "--quiet",
        ],
        check=False,
    )
    return result is not None


def create_service_account(project_id: str, dry_run: bool = False) -> str:
    """Create a service account if it doesn't exist.

    Args:
        project_id: The project ID
        dry_run: If True, don't actually create

    Returns:
        The service account email
    """
    console.print("\n[yellow]--- Step 3: Service Account ---[/yellow]")
    sa_email = f"{BOT_SA_NAME}@{project_id}.iam.gserviceaccount.com"

    if service_account_exists(sa_email, project_id):
        console.print(
            f"[green]Service account {sa_email} already exists. Skipping creation.[/green]"
        )
        return sa_email

    if dry_run:
        console.print(f"[dim][DRY RUN] Would create service account: {BOT_SA_NAME}[/dim]")
        return sa_email

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(description=f"Creating service account: {BOT_SA_NAME}...", total=None)
        run_gcloud([
            "iam",
            "service-accounts",
            "create",
            BOT_SA_NAME,
            f"--project={project_id}",
            "--display-name=Organization Admin Robot",
        ], capture=False)

    console.print("[green]Service account created.[/green]")
    return sa_email


def billing_account_has_role(billing_id: str, sa_email: str, role: str) -> bool:
    """Check if a service account has a specific role on a billing account.

    Args:
        billing_id: The billing account ID
        sa_email: The service account email
        role: The role to check for

    Returns:
        True if the service account has the role, False otherwise
    """
    try:
        policy_output = run_gcloud([
            "billing",
            "accounts",
            "get-iam-policy",
            billing_id,
            "--format=json",
        ])

        if policy_output:
            import json
            policy = json.loads(policy_output)
            bindings = policy.get("bindings", [])

            # Check if service account has the role
            for binding in bindings:
                if binding.get("role") == role:
                    members = binding.get("members", [])
                    if f"serviceAccount:{sa_email}" in members:
                        return True
    except GCloudError:
        # If we can't get the policy, assume it doesn't have the role
        return False

    return False


def grant_billing_account_access(billing_id: str, sa_email: str, dry_run: bool = False) -> None:
    """Grant billing account admin access to the service account (idempotent).

    Args:
        billing_id: The billing account ID
        sa_email: The service account email
        dry_run: If True, don't actually grant access
    """
    console.print("\n[yellow]--- Step 4.5: Grant Billing Account Access ---[/yellow]")

    # Check if service account already has billing admin role
    if billing_account_has_role(billing_id, sa_email, "roles/billing.admin"):
        console.print(
            f"[green]Service account already has billing admin access to {billing_id}. Skipping.[/green]"
        )
        return

    if dry_run:
        console.print(
            f"[dim][DRY RUN] Would grant billing admin access for billing account {billing_id} to {sa_email}[/dim]"
        )
        return

    console.print(f"[cyan]Granting billing admin access for billing account {billing_id}...[/cyan]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(description="Granting billing admin access...", total=None)
        run_gcloud([
            "billing",
            "accounts",
            "add-iam-policy-binding",
            billing_id,
            f"--member=serviceAccount:{sa_email}",
            "--role=roles/billing.admin",
        ])

    console.print(f"[green]Billing admin access granted for {billing_id}.[/green]")


def grant_iam_roles(org_id: Optional[str], sa_email: str, dry_run: bool = False) -> None:
    """Grant organization-level IAM roles to the service account.

    Args:
        org_id: The organization ID (if None, skips org-level roles)
        sa_email: The service account email
        dry_run: If True, don't actually grant roles
    """
    console.print("\n[yellow]--- Step 4: IAM Permissions (at Organization Level) ---[/yellow]")

    if not org_id:
        console.print(
            "[yellow]No organization - skipping org-level IAM roles. "
            "Service account will have no special permissions.[/yellow]"
        )
        return

    console.print(
        "[bold red]WARNING: Granting Organization Administrator and Billing Admin roles.[/bold red]"
    )

    roles = [
        ("roles/resourcemanager.organizationAdmin", "Organization Admin"),
        ("roles/billing.admin", "Billing Admin"),
    ]

    if dry_run:
        for role, role_name in roles:
            console.print(f"[dim][DRY RUN] Would grant {role_name} to {sa_email}[/dim]")
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        for role, role_name in roles:
            task = progress.add_task(description=f"Granting {role_name}...", total=None)
            run_gcloud([
                "organizations",
                "add-iam-policy-binding",
                org_id,
                f"--member=serviceAccount:{sa_email}",
                f"--role={role}",
                "--condition=None",
            ])
            progress.remove_task(task)

    console.print("[green]All roles granted.[/green]")




def bootstrap(
    config_name: Optional[str] = None,
    billing_id: Optional[str] = None,
    org_id: Optional[str] = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    """Bootstrap a super-admin service account for GCP automation.

    This function is idempotent and self-configuring.

    Args:
        config_name: The gcloud configuration name to use (interactive if not provided)
        billing_id: The billing account ID (interactive if not provided)
        org_id: The organization ID (interactive if not provided)
        dry_run: If True, show what would be done without making changes
        verbose: If True, print all gcloud commands

    Raises:
        GCloudError: If any gcloud command fails
    """
    # Set verbose mode
    set_verbose(verbose)

    # Interactive config selection if not provided
    if not config_name:
        config_name = choose_config()

    # Interactive organization selection if not provided
    if not org_id:
        org_id = choose_organization()

    # Interactive billing selection if not provided
    if not billing_id:
        billing_id = choose_billing_account()

    # Determine mode: "organization" if org_id exists, otherwise "personal"
    mode = "organization" if org_id else "personal"

    # Display header
    mode_text = " [DRY RUN]" if dry_run else ""
    org_text = org_id if org_id else "None (personal account)"
    console.print(
        Panel.fit(
            f"[bold cyan]GCP Bootstrap - Super Admin Service Account{mode_text}[/bold cyan]\n"
            f"Config: {config_name}\n"
            f"Mode: {mode}\n"
            f"Organization: {org_text}\n"
            f"Billing: {billing_id}",
            border_style="cyan" if not dry_run else "yellow",
        )
    )

    # Get or create Automation folder (only if org exists)
    folder_id = None
    if org_id:
        folder_id = get_or_create_automation_folder(org_id, dry_run=dry_run)
    else:
        console.print(
            "[yellow]No organization - skipping Automation folder creation.[/yellow]"
        )

    # Determine bot project ID
    bot_project_id = determine_bot_project_id()
    sa_email = f"{BOT_SA_NAME}@{bot_project_id}.iam.gserviceaccount.com"

    # Get current user's email for trusted humans list
    current_user_email = get_current_account_email()

    # Create project in Automation folder
    create_project(bot_project_id, org_id, folder_id=folder_id, dry_run=dry_run)

    # Add trusted human as project owner
    add_project_owner(bot_project_id, current_user_email, dry_run=dry_run)

    # Link billing
    link_billing_account(bot_project_id, billing_id, dry_run=dry_run)

    # Enable required APIs
    enable_required_apis(bot_project_id, dry_run=dry_run)

    # Create service account
    create_service_account(bot_project_id, dry_run=dry_run)

    # Grant IAM roles
    grant_iam_roles(org_id, sa_email, dry_run=dry_run)

    # Grant billing account access
    grant_billing_account_access(billing_id, sa_email, dry_run=dry_run)

    # Save configuration file
    console.print("\n[yellow]--- Saving Configuration ---[/yellow]")
    config_file = save_config_file(
        config_name=config_name,
        bot_email=sa_email,
        trusted_humans=[current_user_email],
        mode=mode,
        dry_run=dry_run,
    )

    # Download service account key (not in dry-run)
    key_file = download_service_account_key(
        config_name=config_name,
        sa_email=sa_email,
        project_id=bot_project_id,
        dry_run=dry_run,
    )

    # Success summary
    status_text = "Dry Run Complete!" if dry_run else "Bootstrap Successful!"
    border_color = "yellow" if dry_run else "green"

    summary_lines = [
        f"[bold {'yellow' if dry_run else 'green'}]{status_text}[/bold {'yellow' if dry_run else 'green'}]\n",
        f"Project ID: {bot_project_id}",
        f"Service Account: {sa_email}",
        f"Mode: {mode}",
        f"Organization: {org_id or 'N/A (personal account)'}",
        f"Folder: {folder_id or 'N/A'}",
        f"Config File: {config_file}",
    ]

    if key_file and not dry_run:
        summary_lines.append(f"Key File: {key_file}")

    console.print(
        Panel.fit(
            "\n".join(summary_lines),
            border_style=border_color,
        )
    )
