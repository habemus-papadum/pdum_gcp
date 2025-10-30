"""Common utilities for pdum_gcp commands."""

import json
from pathlib import Path
from typing import Optional

import yaml
from InquirerPy import inquirer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from pdum.gcp.bootstrap import (
    GCloudError,
    get_available_configs,
    get_config_value,
    run_gcloud,
)

console = Console()


def choose_config() -> str:
    """Interactively choose a gcloud configuration.

    Returns:
        The selected configuration name

    Raises:
        GCloudError: If no configurations are found
    """
    configs = get_available_configs()

    if not configs:
        raise GCloudError("No gcloud configurations found. Please create one first.")

    # If only one config, auto-select it
    if len(configs) == 1:
        config = configs[0]
        name = config.get("name", "")
        account = config.get("properties", {}).get("core", {}).get("account", "no account")
        console.print(f"[cyan]Using only available config:[/cyan] {name} ({account})")
        return name

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


def get_config_dir(config_name: str) -> Path:
    """Get the configuration directory path for a given config.

    Args:
        config_name: The gcloud configuration name

    Returns:
        Path to the config directory
    """
    home = Path.home()
    config_dir = home / ".config" / "gcloud" / "pdum_gcp" / config_name
    return config_dir


def get_current_account_email() -> str:
    """Get the email address of the currently active gcloud account.

    Returns:
        The email address

    Raises:
        GCloudError: If account email cannot be determined
    """
    email = get_config_value("core/account")
    if not email:
        raise GCloudError("Could not determine current account email")
    return email


def save_config_file(
    config_name: str,
    bot_email: str,
    trusted_humans: list[str],
    mode: str,
    dry_run: bool = False
) -> Path:
    """Save configuration to YAML file.

    Args:
        config_name: The gcloud configuration name
        bot_email: The admin bot email address
        trusted_humans: List of trusted human email addresses
        mode: Either "personal" or "organization"
        dry_run: If True, only simulate

    Returns:
        Path to the saved config file
    """
    config_dir = get_config_dir(config_name)
    config_file = config_dir / "config.yaml"

    config_data = {
        "mode": mode,
        "admin_bot": bot_email,
        "trusted_humans": trusted_humans,
    }

    if dry_run:
        console.print(f"[dim][DRY RUN] Would create config directory: {config_dir}[/dim]")
        console.print(f"[dim][DRY RUN] Would save config to: {config_file}[/dim]")
        console.print(f"[dim][DRY RUN] Config data: {config_data}[/dim]")
        return config_file

    # Create directory if it doesn't exist
    config_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"[cyan]Created config directory:[/cyan] {config_dir}")

    # Write YAML file
    with open(config_file, "w") as f:
        yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)

    console.print(f"[green]Saved configuration to:[/green] {config_file}")
    return config_file


def download_service_account_key(
    config_name: str,
    sa_email: str,
    project_id: str,
    dry_run: bool = False
) -> Optional[Path]:
    """Download service account key to admin.json.

    Args:
        config_name: The gcloud configuration name
        sa_email: The service account email
        project_id: The project ID
        dry_run: If True, only simulate

    Returns:
        Path to the key file, or None if dry run

    Raises:
        GCloudError: If key download fails
    """
    console.print("[cyan]Downloading service account key...[/cyan]")

    config_dir = get_config_dir(config_name)
    key_file = config_dir / "admin.json"

    if dry_run:
        console.print(f"[dim][DRY RUN] Would download SA key to: {key_file}[/dim]")
        return None

    # Ensure directory exists
    config_dir.mkdir(parents=True, exist_ok=True)

    # Check if key already exists
    if key_file.exists():
        console.print(
            f"[yellow]Key file already exists at {key_file}. "
            "Delete it manually if you want to regenerate.[/yellow]"
        )
        return key_file

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(description="Downloading service account key...", total=None)

        run_gcloud([
            "iam",
            "service-accounts",
            "keys",
            "create",
            str(key_file),
            f"--iam-account={sa_email}",
            f"--project={project_id}",
        ], capture=False)

    console.print(f"[green]Service account key saved to:[/green] {key_file}")
    console.print(
        "[bold yellow]WARNING:[/bold yellow] Keep this key file secure! "
        "It grants admin access to your GCP organization."
    )

    return key_file
