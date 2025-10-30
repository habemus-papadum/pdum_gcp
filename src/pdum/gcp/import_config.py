"""Import existing bootstrap configuration."""

from typing import Optional

from rich.console import Console
from rich.panel import Panel

from pdum.gcp.bootstrap import BOT_PROJECT_PREFIX, BOT_SA_NAME, GCloudError, run_gcloud, set_verbose
from pdum.gcp.utils import (
    choose_config,
    download_service_account_key,
    get_current_account_email,
    save_config_file,
)

console = Console()


def find_bot_project() -> Optional[str]:
    """Find existing bot project by searching for the prefix.

    Returns:
        The bot project ID if found, None otherwise
    """
    console.print(f"[cyan]Searching for bot project with prefix '{BOT_PROJECT_PREFIX}-*'[/cyan]")

    # Search for existing project using regex filter
    existing_id = run_gcloud([
        "projects",
        "list",
        f"--filter=projectId ~ ^{BOT_PROJECT_PREFIX}-.*",
        "--limit=1",
        "--format=value(projectId)",
    ])

    if existing_id:
        console.print(f"[green]Found bot project:[/green] {existing_id}")
        return existing_id

    console.print("[yellow]No bot project found.[/yellow]")
    return None


def get_service_account_email(project_id: str) -> str:
    """Get the service account email for the bot project.

    Args:
        project_id: The project ID

    Returns:
        The service account email

    Raises:
        GCloudError: If service account is not found
    """
    console.print(f"[cyan]Looking for service account in project {project_id}...[/cyan]")

    # List service accounts in the project
    output = run_gcloud([
        "iam",
        "service-accounts",
        "list",
        f"--project={project_id}",
        f"--filter=email:{BOT_SA_NAME}@*",
        "--format=value(email)",
    ])

    if not output:
        raise GCloudError(
            f"No service account with name '{BOT_SA_NAME}' found in project {project_id}"
        )

    sa_email = output.strip()
    console.print(f"[green]Found service account:[/green] {sa_email}")
    return sa_email


def import_bootstrap_config(
    config_name: Optional[str] = None,
    verbose: bool = False,
) -> None:
    """Import existing bootstrap configuration.

    This command is used to set up an auxiliary machine with access to an
    already-bootstrapped admin service account.

    Args:
        config_name: The gcloud configuration name (interactive if not provided)
        verbose: If True, print all gcloud commands

    Raises:
        GCloudError: If import fails
    """
    # Set verbose mode
    set_verbose(verbose)

    # Interactive config selection if not provided
    if not config_name:
        config_name = choose_config()

    # Display header
    console.print(
        Panel.fit(
            "[bold cyan]Import Bootstrap Configuration[/bold cyan]\n"
            f"Config: {config_name}",
            border_style="cyan",
        )
    )

    # Find the bot project
    bot_project_id = find_bot_project()
    if not bot_project_id:
        raise GCloudError(
            f"No bot project found with prefix '{BOT_PROJECT_PREFIX}-*'. "
            "You need to run 'bootstrap' first on another machine."
        )

    # Get the service account email
    sa_email = get_service_account_email(bot_project_id)

    # Get current user's email for trusted humans list
    current_user_email = get_current_account_email()

    # Save configuration file
    console.print("\n[yellow]--- Saving Configuration ---[/yellow]")
    config_file = save_config_file(
        config_name=config_name,
        bot_email=sa_email,
        trusted_humans=[current_user_email],
        dry_run=False,
    )

    # Download service account key
    key_file = download_service_account_key(
        config_name=config_name,
        sa_email=sa_email,
        project_id=bot_project_id,
        dry_run=False,
    )

    # Success summary
    console.print(
        Panel.fit(
            "[bold green]Import Successful![/bold green]\n\n"
            f"Project ID: {bot_project_id}\n"
            f"Service Account: {sa_email}\n"
            f"Config File: {config_file}\n"
            f"Key File: {key_file}",
            border_style="green",
        )
    )
