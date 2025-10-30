"""Manage billing account access for admin bots."""

from typing import Optional

from InquirerPy import inquirer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pdum.gcp.bootstrap import (
    BOT_PROJECT_PREFIX,
    GCloudError,
    billing_account_has_role,
    get_billing_accounts,
    run_gcloud,
    set_verbose,
)
from pdum.gcp.utils import choose_config

console = Console()


def get_admin_bot_email(config_name: str) -> str:
    """Get the admin bot email for a given config.

    Args:
        config_name: The gcloud configuration name

    Returns:
        The admin bot service account email

    Raises:
        GCloudError: If admin bot cannot be found
    """
    console.print(f"[cyan]Looking up admin bot for config '{config_name}'...[/cyan]")

    # Find the bot project
    bot_project_id = run_gcloud([
        "projects",
        "list",
        f"--filter=projectId ~ ^{BOT_PROJECT_PREFIX}-.*",
        "--limit=1",
        "--format=value(projectId)",
    ])

    if not bot_project_id:
        raise GCloudError(
            f"No admin bot project found for config '{config_name}'. "
            "Run 'pdum_gcp bootstrap' first."
        )

    # Construct service account email
    sa_email = f"admin-robot@{bot_project_id}.iam.gserviceaccount.com"
    console.print(f"[green]Found admin bot:[/green] {sa_email}")
    return sa_email


def manage_billing_access(
    config_name: Optional[str] = None,
    verbose: bool = False,
) -> None:
    """Manage billing account access for the admin bot.

    This command allows you to grant the admin bot access to additional
    billing accounts using an interactive multi-select interface.

    Args:
        config_name: The gcloud configuration name (interactive if not provided)
        verbose: If True, print all gcloud commands

    Raises:
        GCloudError: If operation fails
    """
    # Set verbose mode
    set_verbose(verbose)

    # Interactive config selection if not provided
    if not config_name:
        config_name = choose_config()

    # Display header
    console.print(
        Panel.fit(
            "[bold cyan]Manage Billing Account Access[/bold cyan]\n"
            f"Config: {config_name}",
            border_style="cyan",
        )
    )

    # Get admin bot email
    sa_email = get_admin_bot_email(config_name)

    # Get all billing accounts
    console.print("\n[cyan]Fetching billing accounts...[/cyan]")
    billing_accounts = get_billing_accounts()

    if not billing_accounts:
        console.print("[yellow]No billing accounts found.[/yellow]")
        return

    # Check current access for each billing account
    console.print("[cyan]Checking current access...[/cyan]")
    account_status = []
    for account in billing_accounts:
        account_id = account.get("name", "").replace("billingAccounts/", "")
        display_name = account.get("displayName", "")
        is_open = account.get("open", False)
        has_access = billing_account_has_role(account_id, sa_email, "roles/billing.admin")

        account_status.append({
            "id": account_id,
            "name": display_name,
            "open": is_open,
            "has_access": has_access,
        })

    # Display current status
    console.print("\n[bold]Current Billing Account Access:[/bold]")
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Billing Account")
    table.add_column("Account ID")
    table.add_column("Status")
    table.add_column("Admin Bot Access")

    for account in account_status:
        status = "[green]Open[/green]" if account["open"] else "[red]Closed[/red]"
        access = "[green]Yes[/green]" if account["has_access"] else "[yellow]No[/yellow]"
        table.add_row(
            account["name"],
            account["id"],
            status,
            access,
        )

    console.print(table)

    # Filter to accounts that don't have access yet
    accounts_without_access = [acc for acc in account_status if not acc["has_access"]]

    if not accounts_without_access:
        console.print("\n[green]Admin bot already has access to all billing accounts![/green]")
        return

    # Multi-select interface
    console.print("\n[cyan]Select billing accounts to grant access to:[/cyan]")

    choices = []
    for account in accounts_without_access:
        status_indicator = "✓ Open" if account["open"] else "✗ Closed"
        choices.append({
            "name": f"{account['name']} ({account['id']}) - {status_indicator}",
            "value": account["id"],
        })

    if not choices:
        console.print("[green]No additional billing accounts to grant access to.[/green]")
        return

    selected_accounts = inquirer.checkbox(
        message="Select billing accounts (space to select, enter to confirm):",
        choices=choices,
    ).execute()

    if not selected_accounts:
        console.print("[yellow]No accounts selected. Exiting.[/yellow]")
        return

    # Grant access to selected accounts
    console.print("\n[yellow]--- Granting Access ---[/yellow]")
    for account_id in selected_accounts:
        account_name = next(
            (acc["name"] for acc in account_status if acc["id"] == account_id),
            account_id
        )

        console.print(f"\n[cyan]Granting access to {account_name} ({account_id})...[/cyan]")

        try:
            run_gcloud([
                "billing",
                "accounts",
                "add-iam-policy-binding",
                account_id,
                f"--member=serviceAccount:{sa_email}",
                "--role=roles/billing.admin",
            ])
            console.print(f"[green]✓ Access granted to {account_name}[/green]")
        except GCloudError as e:
            console.print(f"[red]✗ Failed to grant access to {account_name}: {e}[/red]")

    # Success summary
    console.print(
        Panel.fit(
            f"[bold green]Access Management Complete![/bold green]\n\n"
            f"Granted access to {len(selected_accounts)} billing account(s)",
            border_style="green",
        )
    )
