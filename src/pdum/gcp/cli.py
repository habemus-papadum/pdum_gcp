"""CLI entry point for pdum_gcp."""

import typer

app = typer.Typer(help="Utilities and tools for Google Cloud")


@app.command()
def hello(name: str = typer.Option("World", help="Name to greet")):
    """
    Say hello to someone.
    """
    typer.echo(f"Hello, {name}!")


def main():
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
