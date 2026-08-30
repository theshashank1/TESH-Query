"""
CLI Commands for GGUF model management in TESH-Query.
"""

import os
import typer
from rich.progress import Progress, BarColumn, TextColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn
from teshq.cli.ui import print_header, print_footer, status, error, warning, tip, success
from teshq.core.model_manager import ModelManager, REGISTRY

app = typer.Typer(help="Manage local GGUF model downloads and files.")

@app.command(name="list")
def list_models():
    """
    List currently installed models and available models in the registry.
    """
    print_header("TESHQ LOCAL MODELS", level=1)
    
    manager = ModelManager()
    
    # 1. Fetch installed models
    with status("Scanning models directory...", success_message="Scan complete."):
        installed = manager.get_installed_models()
        
    typer.echo("")
    typer.secho("📥 Installed Models:", bold=True, fg="cyan")
    if installed:
        for model in installed:
            typer.secho(f"  • {model['filename']}", bold=True)
            typer.echo(f"    - Registry Name: {model['name']}")
            typer.echo(f"    - Size:          {model['size_gb']:.2f} GB")
            typer.echo(f"    - Description:   {model['description']}")
            typer.echo(f"    - Local Path:    {model['path']}")
            typer.echo("")
    else:
        typer.echo("  No local GGUF models installed yet. Run 'teshq model pull' to download one.")
        typer.echo("")
        
    # 2. Fetch available models in registry
    typer.secho("🌐 Registry Models Available for Download:", bold=True, fg="magenta")
    for name, info in REGISTRY.items():
        # Check if already installed
        is_installed = any(item["name"] == name for item in installed)
        installed_flag = " [Installed]" if is_installed else ""
        
        typer.secho(f"  • {name}{installed_flag}", bold=True)
        typer.echo(f"    - Repository:    {info['repo']}")
        typer.echo(f"    - Target File:   {info['file']}")
        typer.echo(f"    - Size:          {info['size_gb']:.2f} GB (Requires ~{info['required_ram_gb']}GB RAM)")
        typer.echo(f"    - Description:   {info['description']}")
        typer.echo("")
        
    print_footer()

@app.command(name="pull")
def pull_model(
    name: str = typer.Argument(..., help="Registry name (e.g. qwen3b-coder) or Hugging Face repo path."),
    file: str = typer.Option(None, "--file", "-f", help="Target filename on HF (required if specifying custom repo path)."),
    force: bool = typer.Option(False, "--force", help="Skip system compatibility warnings and force download."),
):
    """
    Download a GGUF model from Hugging Face.
    """
    print_header(f"PULLING MODEL: {name}", level=1)
    
    manager = ModelManager()
    
    # 1. Compatibility check for registry models
    if name in REGISTRY and not force:
        is_compat, warn_msg = manager.check_compatibility(name)
        if not is_compat:
            typer.secho("🚨 RESOURCE WARNING 🚨", fg="red", bold=True, blink=True)
            typer.echo("")
            typer.secho(warn_msg, fg="yellow", bold=True)
            typer.echo("")
            
            proceed = typer.confirm("Do you still want to proceed with downloading the model?", default=False)
            if not proceed:
                warning("Download cancelled by user.")
                print_footer()
                return
            
            typer.echo("")
            warning("Proceeding with download. Note: TESHQ is NOT liable for any system instability.")

    # 2. Download with Rich progress bar
    try:
        # Create progress bar
        progress = Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn()
        )
        
        with progress:
            task_id = progress.add_task("Downloading GGUF model...", total=100)
            
            def progress_callback(downloaded: int, total: int):
                # Update task percentage
                if total > 0:
                    # Update progress bar
                    progress.update(task_id, completed=downloaded, total=total)
                    
            local_path = manager.download_model(name, filename=file, progress_callback=progress_callback)
            
        success(f"🎉 Model downloaded successfully to: {local_path}")
        
        # Suggest configuration update
        tip("To use this model, update your config LOCAL_MODEL_PATH:")
        typer.secho(f"  teshq config --local-model-path \"{local_path}\" --llm-provider local", bold=True)
        
    except Exception as e:
        error(f"Download failed: {e}")
        raise typer.Exit(1)
        
    print_footer()

@app.command(name="remove")
def remove_model(
    filename: str = typer.Argument(..., help="Filename of GGUF model to remove (e.g. qwen2.5-coder-3b-instruct-q4_k_m.gguf)"),
):
    """
    Delete a local GGUF model file.
    """
    print_header("REMOVING MODEL", level=1)
    
    manager = ModelManager()
    
    confirm_del = typer.confirm(f"Are you sure you want to delete the model file '{filename}'?", default=False)
    if not confirm_del:
        warning("Deletion cancelled.")
        print_footer()
        return
        
    if manager.delete_model(filename):
        success(f"✅ Model '{filename}' removed successfully.")
    else:
        error(f"Model file '{filename}' not found or could not be removed.")
        raise typer.Exit(1)
        
    print_footer()
