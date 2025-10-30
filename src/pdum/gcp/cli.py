"""CLI entry point for pdum_gcp."""

import sys
from typing import Optional

import typer
from rich.console import Console

from pdum.gcp import bootstrap as bootstrap_module

app = typer.Typer(
    help="Utilities and tools for Google Cloud",
    no_args_is_help=True,
)
console = Console()

@app.command("version")
def version():
    """Show the version of pdum_gcp."""
    from pdum.gcp import __version__

    console.print(f"pdum_gcp version: [bold green]{__version__}[/bold green]")

@app.command("bootstrap")
def bootstrap(
    config_name: Optional[str] = typer.Option(
        None,
        "--config",
        "-c",
        help="The gcloud configuration name to use (interactive if not provided)",
    ),
    billing_id: Optional[str] = typer.Option(
        None,
        "--billing",
        "-b",
        help="The billing account ID (interactive if not provided)",
    ),
    org_id: Optional[str] = typer.Option(
        None,
        "--org",
        "-o",
        help="The organization ID (interactive if not provided)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be done without making changes",
    ),
):
    """
    Bootstrap a super-admin service account for GCP automation.

    This command creates a GCP project with a service account that has
    organization-level admin permissions. The process is idempotent and
    self-configuring.

    If --config, --billing, or --org are not provided, you'll be
    prompted to select them interactively.

    The project will be created in an "Automation" folder (created if needed).

    Examples:
        # Interactive mode (prompts for all options)
        pdum_gcp bootstrap

        # Specify all options
        pdum_gcp bootstrap --config work --billing 0X0X0X-0X0X0X-0X0X0X --org 123456789

        # Dry run to see what would happen
        pdum_gcp bootstrap --dry-run
    """
    try:
        bootstrap_module.bootstrap(
            config_name=config_name,
            billing_id=billing_id,
            org_id=org_id,
            dry_run=dry_run,
        )
    except bootstrap_module.GCloudError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Bootstrap interrupted by user.[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[bold red]Unexpected error:[/bold red] {e}")
        sys.exit(1)


def main():
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
