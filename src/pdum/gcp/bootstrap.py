"""Bootstrap a super-admin service account for GCP automation.

This module provides idempotent functionality to create and configure
a GCP service account with organization-level admin permissions.
"""

import subprocess
from typing import Optional

from InquirerPy import inquirer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# --- Configuration ---
CUSTOM_CONFIG_KEY = "bootstrap/bot_project_id"
BOT_PROJECT_PREFIX = "my-org-admin-bots"
BOT_SA_NAME = "admin-robot"

console = Console()


class GCloudError(Exception):
    """Exception raised for gcloud command errors."""

    pass


def run_gcloud(args: list[str], check: bool = True, capture: bool = True) -> Optional[str]:
    """Run a gcloud command and return output.

    Args:
        args: List of arguments to pass to gcloud
        check: If True, raise exception on non-zero exit code
        capture: If True, capture and return stdout

    Returns:
        Command stdout if capture=True, None otherwise

    Raises:
        GCloudError: If command fails and check=True
    """
    cmd = ["gcloud"] + args
    try:
        result = subprocess.run(
            cmd,
            check=check,
            capture_output=capture,
            text=True,
        )
        return result.stdout.strip() if capture else None
    except subprocess.CalledProcessError as e:
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
    """Set a value in gcloud config."""
    run_gcloud(["config", "set", key, value], capture=False)


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


def activate_config(config_name: str) -> None:
    """Activate a gcloud configuration."""
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
        activate_config(original_config)
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


def choose_config() -> str:
    """Interactively choose a gcloud configuration.

    Returns:
        The selected configuration name
    """
    configs = get_available_configs()

    if not configs:
        raise GCloudError("No gcloud configurations found. Please create one first.")

    # Format choices with additional info
    choices = []
    for config in configs:
        name = config.get("name", "")
        account = config.get("properties", {}).get("core", {}).get("account", "no account")
        is_active = config.get("is_active", False)
        active_marker = " [ACTIVE]" if is_active else ""
        choices.append({
            "name": f"{name} ({account}){active_marker}",
            "value": name,
        })

    result = inquirer.select(
        message="Select gcloud configuration:",
        choices=choices,
        default=next((c["value"] for c in choices if "[ACTIVE]" in c["name"]), None),
    ).execute()

    return result


def get_billing_accounts() -> list[dict[str, str]]:
    """Get list of available billing accounts.

    Returns:
        List of dicts with billing account info
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
    return accounts


def choose_billing_account() -> str:
    """Interactively choose a billing account.

    Returns:
        The selected billing account ID
    """
    accounts = get_billing_accounts()

    if not accounts:
        raise GCloudError("No billing accounts found. You need at least one billing account.")

    # Format choices with additional info
    choices = []
    for account in accounts:
        name = account.get("displayName", "")
        account_id = account.get("name", "").replace("billingAccounts/", "")
        open_status = "OPEN" if account.get("open", False) else "CLOSED"
        choices.append({
            "name": f"{name} ({account_id}) [{open_status}]",
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
        The folder ID, or None if dry run
    """
    console.print("[cyan]Checking for Automation folder...[/cyan]")

    # Search for existing folder
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

    # Create folder if it doesn't exist
    if dry_run:
        console.print("[dim][DRY RUN] Would create Automation folder[/dim]")
        return None

    console.print("[yellow]Creating Automation folder...[/yellow]")
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

    raise GCloudError("Failed to create Automation folder")


def generate_random_hex(length: int = 4) -> str:
    """Generate a random hex string."""
    import secrets

    return secrets.token_hex(length)


def determine_bot_project_id(dry_run: bool = False) -> str:
    """Determine or generate the bot project ID (idempotent).

    Args:
        dry_run: If True, don't save to config

    Returns:
        The bot project ID to use
    """
    console.print("\n[yellow]--- Step 0: Determine Bot Project ID ---[/yellow]")

    # Try to read from config
    bot_project_id = get_config_value(CUSTOM_CONFIG_KEY)

    if bot_project_id:
        console.print(f"[green]Found project ID in config:[/green] {bot_project_id}")
        return bot_project_id

    console.print(
        f"[yellow]No ID in config. Searching for existing project "
        f"with prefix '{BOT_PROJECT_PREFIX}-*'[/yellow]"
    )

    # Search for existing project
    existing_id = run_gcloud([
        "projects",
        "list",
        f"--filter=projectId:{BOT_PROJECT_PREFIX}-*",
        "--limit=1",
        "--format=value(projectId)",
    ])

    if existing_id:
        console.print(f"[green]Found existing project:[/green] {existing_id}")
        bot_project_id = existing_id
    else:
        console.print("[yellow]No existing project found. Generating new ID.[/yellow]")
        random_hex = generate_random_hex(4)
        bot_project_id = f"{BOT_PROJECT_PREFIX}-{random_hex}"
        console.print(f"[cyan]New project ID will be:[/cyan] {bot_project_id}")

    # Save to config
    if dry_run:
        console.print(f"[dim][DRY RUN] Would save project ID to config key '{CUSTOM_CONFIG_KEY}'[/dim]")
    else:
        console.print(f"[cyan]Saving project ID to config key '{CUSTOM_CONFIG_KEY}'[/cyan]")
        set_config_value(CUSTOM_CONFIG_KEY, bot_project_id)

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
            "--name=[Admin] Service Bots",
            "--no-activate",
        ]

        if folder_id:
            args.append(f"--folder={folder_id}")
        elif org_id:
            args.append(f"--organization={org_id}")
        # If neither folder nor org, create project without parent

        run_gcloud(args, capture=False)

    console.print("[green]Project created.[/green]")


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
) -> None:
    """Bootstrap a super-admin service account for GCP automation.

    This function is idempotent and self-configuring.

    Args:
        config_name: The gcloud configuration name to use (interactive if not provided)
        billing_id: The billing account ID (interactive if not provided)
        org_id: The organization ID (interactive if not provided)
        dry_run: If True, show what would be done without making changes

    Raises:
        GCloudError: If any gcloud command fails
    """
    # Save original state
    original_config = get_active_config()
    original_project = get_config_value("core/project")

    try:
        # Interactive config selection if not provided
        if not config_name:
            config_name = choose_config()

        # Activate target config
        activate_config(config_name)

        # Interactive organization selection if not provided
        if not org_id:
            org_id = choose_organization()

        # Interactive billing selection if not provided
        if not billing_id:
            billing_id = choose_billing_account()

        # Display header
        mode_text = " [DRY RUN]" if dry_run else ""
        org_text = org_id if org_id else "None (personal account)"
        console.print(
            Panel.fit(
                f"[bold cyan]GCP Bootstrap - Super Admin Service Account{mode_text}[/bold cyan]\n"
                f"Config: {config_name}\n"
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
        bot_project_id = determine_bot_project_id(dry_run=dry_run)
        sa_email = f"{BOT_SA_NAME}@{bot_project_id}.iam.gserviceaccount.com"

        # Create project in Automation folder
        create_project(bot_project_id, org_id, folder_id=folder_id, dry_run=dry_run)

        # Link billing
        link_billing_account(bot_project_id, billing_id, dry_run=dry_run)

        # Create service account
        create_service_account(bot_project_id, dry_run=dry_run)

        # Grant IAM roles
        grant_iam_roles(org_id, sa_email, dry_run=dry_run)

        # Success summary
        status_text = "Dry Run Complete!" if dry_run else "Bootstrap Successful!"
        border_color = "yellow" if dry_run else "green"
        console.print(
            Panel.fit(
                f"[bold {'yellow' if dry_run else 'green'}]{status_text}[/bold {'yellow' if dry_run else 'green'}]\n\n"
                f"Project ID: {bot_project_id}\n"
                f"Service Account: {sa_email}\n"
                f"Organization: {org_id or 'N/A (personal account)'}\n"
                f"Folder: {folder_id or 'N/A'}",
                border_style=border_color,
            )
        )

    finally:
        # Always restore original config
        restore_config(original_config, original_project, dry_run=dry_run)
