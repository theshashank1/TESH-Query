"""
CLI Commands for GGUF model management in TESH-Query.

Provides commands to view, download, and manage local GGUF models stored in ~/.teshq/models/.
"""

import json
from typing import Optional
import typer
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.prompt import Confirm
from rich.table import Table

from teshq.cli.ui import error, handle_error, print_header, status, success, tip, warning
from teshq.cli.ui.theme import Colors, Icons, ROUNDED_BOX, console
from teshq.core.model_manager import ModelManager, REGISTRY

app = typer.Typer(
    name="model",
    help="Manage local GGUF model downloads and files.",
    invoke_without_command=True,
)

PANEL_OUTPUT = "📊 Output Options"
PANEL_MODEL = "📥 Model Selection"
PANEL_OPTIONS = "⚙️ Download Options"
PANEL_ACTIONS = "⚙️ Actions"


@app.callback(invoke_without_command=True)
def model_default(ctx: typer.Context):
    """Manage local GGUF model downloads and files."""
    if ctx.invoked_subcommand is None:
        list_models(as_json=False)


@app.command(name="list")
def list_models(
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Output installed and available models as machine-readable JSON.",
        rich_help_panel=PANEL_OUTPUT,
    ),
):
    """
    List currently installed models and available models in the registry.
    """
    try:
        manager = ModelManager()

        if as_json:
            installed = manager.get_installed_models()
            registry_list = []
            for name, info in REGISTRY.items():
                is_installed = any(item["name"] == name for item in installed)
                item = dict(info)
                item["name"] = name
                item["installed"] = is_installed
                registry_list.append(item)
            print(json.dumps({"installed": installed, "registry": registry_list}, indent=2))
            raise typer.Exit(0)

        print_header("Local GGUF Models", level=2)

        with status("Scanning models directory...", success_message="Scan complete."):
            installed = manager.get_installed_models()

        # 1. Installed Models Table
        if installed:
            table = Table(
                box=ROUNDED_BOX,
                border_style=Colors.BORDER_DEFAULT,
                header_style=f"bold {Colors.TEXT_PRIMARY}",
                title=f"[bold {Colors.SUCCESS}]{Icons.check()} Installed Local Models[/bold {Colors.SUCCESS}]",
                title_justify="left",
                expand=False,
            )
            table.add_column("Filename", style=f"bold {Colors.PRIMARY}")
            table.add_column("Registry ID", style=Colors.AI_ACCENT)
            table.add_column("Size", justify="right", style=Colors.WARNING)
            table.add_column("Local Path", style=f"dim {Colors.TEXT_MUTED}")
            table.add_column("Description", style=Colors.TEXT_SECONDARY)

            for m in installed:
                table.add_row(
                    m["filename"],
                    m["name"],
                    f"{m['size_gb']:.2f} GB",
                    m["path"],
                    m["description"],
                )
            console.print(table)
            console.print()
        else:
            tip("No local GGUF models installed yet. Run 'teshq model pull <name>' to download one.")
            console.print()

        # 2. Registry Models Table
        reg_table = Table(
            box=ROUNDED_BOX,
            border_style=Colors.BORDER_DEFAULT,
            header_style=f"bold {Colors.TEXT_PRIMARY}",
            title=f"[bold {Colors.PRIMARY}]{Icons.sparkle()} Registry Models Available for Download[/bold {Colors.PRIMARY}]",
            title_justify="left",
            expand=False,
        )
        reg_table.add_column("Model Name", style=f"bold {Colors.PRIMARY}")
        reg_table.add_column("Status", justify="center")
        reg_table.add_column("Size", justify="right", style=Colors.WARNING)
        reg_table.add_column("Min RAM", justify="right", style=Colors.TEXT_TERTIARY)
        reg_table.add_column("Description", style=Colors.TEXT_SECONDARY)

        for name, info in REGISTRY.items():
            is_installed = any(item["name"] == name for item in installed)
            status_badge = (
                f"[bold {Colors.SUCCESS}]{Icons.check()} Installed[/bold {Colors.SUCCESS}]"
                if is_installed
                else f"[dim {Colors.TEXT_MUTED}]Available[/dim {Colors.TEXT_MUTED}]"
            )
            reg_table.add_row(
                name,
                status_badge,
                f"{info['size_gb']:.1f} GB",
                f"~{info['required_ram_gb']} GB",
                info["description"],
            )
        console.print(reg_table)
        console.print()

        tip("To switch to local inference with an installed model:")
        console.print(
            f"  [bold {Colors.PRIMARY}]teshq config --llm-provider local --local-model-path <path>[/bold {Colors.PRIMARY}]\n"
        )

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        console.print(f"\n[{Colors.TEXT_MUTED}]Operation cancelled.[/{Colors.TEXT_MUTED}]")
        raise typer.Exit(0)
    except Exception as e:
        handle_error(e, "Model Listing", suggest_action="Check directory permissions in ~/.teshq/models/")
        raise typer.Exit(1)


@app.command(name="pull")
def pull_model(
    name: str = typer.Argument(
        ...,
        help="Registry name (e.g. qwen3b-coder) or Hugging Face repo path.",
    ),
    file: Optional[str] = typer.Option(
        None,
        "--file",
        "-f",
        help="Target filename on HF (required if specifying custom repo path).",
        rich_help_panel=PANEL_MODEL,
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Skip system compatibility warnings and force download.",
        rich_help_panel=PANEL_OPTIONS,
    ),
):
    """
    Download a GGUF model from Hugging Face.
    """
    print_header(f"Downloading Model: {name}", level=2)

    manager = ModelManager()

    # 1. Compatibility check for registry models
    if name in REGISTRY and not force:
        is_compat, warn_msg = manager.check_compatibility(name)
        if not is_compat:
            console.print(f"\n[bold {Colors.WARNING}]{Icons.warn()} Resource Notice[/bold {Colors.WARNING}]")
            console.print(f"[{Colors.TEXT_SECONDARY}]{warn_msg}[/{Colors.TEXT_SECONDARY}]\n")

            try:
                proceed = Confirm.ask(
                    f"[{Colors.WARNING}]Do you still want to proceed with downloading the model?[/{Colors.WARNING}]",
                    default=False,
                )
            except KeyboardInterrupt:
                console.print(f"\n[{Colors.TEXT_MUTED}]Download cancelled.[/{Colors.TEXT_MUTED}]")
                raise typer.Exit(0)

            if not proceed:
                warning("Download cancelled by user.")
                raise typer.Exit(0)

            console.print()
            warning("Proceeding with download. Note: high RAM usage may slow down background tasks.")

    # 2. Download with Rich progress bar
    try:
        progress = Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
        )

        with progress:
            task_id = progress.add_task("Downloading GGUF model...", total=100)

            def progress_callback(downloaded: int, total: int):
                if total > 0:
                    progress.update(task_id, completed=downloaded, total=total)

            local_path = manager.download_model(name, filename=file, progress_callback=progress_callback)

        success(f"Model downloaded successfully to: {local_path}")
        tip("To use this model, configure TESHQ:")
        console.print(
            f"  [bold {Colors.PRIMARY}]teshq config --local-model-path \"{local_path}\" --llm-provider local[/bold {Colors.PRIMARY}]\n"
        )

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        console.print(f"\n[{Colors.TEXT_MUTED}]Download cancelled.[/{Colors.TEXT_MUTED}]")
        raise typer.Exit(0)
    except Exception as e:
        error(f"Download failed: {e}")
        raise typer.Exit(1)


@app.command(name="remove")
def remove_model(
    filename: str = typer.Argument(
        ...,
        help="Filename of GGUF model to remove (e.g. qwen2.5-coder-3b-instruct-q4_k_m.gguf)",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip deletion confirmation prompt.",
        rich_help_panel=PANEL_ACTIONS,
    ),
):
    """
    Delete a local GGUF model file.
    """
    print_header("Removing Model", level=2)

    manager = ModelManager()

    if not yes:
        try:
            confirm_del = Confirm.ask(
                f"[{Colors.WARNING}]Are you sure you want to delete model '{filename}'?[/{Colors.WARNING}]",
                default=False,
            )
        except KeyboardInterrupt:
            console.print(f"\n[{Colors.TEXT_MUTED}]Deletion cancelled.[/{Colors.TEXT_MUTED}]")
            raise typer.Exit(0)

        if not confirm_del:
            warning("Deletion cancelled.")
            raise typer.Exit(0)

    try:
        if manager.delete_model(filename):
            success(f"Model '{filename}' removed successfully.")
        else:
            error(f"Model file '{filename}' not found or could not be removed.")
            raise typer.Exit(1)
    except typer.Exit:
        raise
    except KeyboardInterrupt:
        console.print(f"\n[{Colors.TEXT_MUTED}]Operation cancelled.[/{Colors.TEXT_MUTED}]")
        raise typer.Exit(0)
    except Exception as e:
        error(f"Failed to remove model: {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
