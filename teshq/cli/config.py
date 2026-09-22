"""
Configuration Command for TESH-Query CLI

Streamlined configuration experience:
  • `teshq config`          → Clean status dashboard
  • `teshq config --wizard` → Guided Quick Setup (DB + AI in 30 seconds)
  • `teshq config --db`     → Interactive database setup
  • `teshq config --ai`     → Interactive AI model provider setup
  • All existing CLI options preserved for scripting compatibility.

Secrets (DATABASE_URL, GEMINI_API_KEY, AZURE_OPENAI_API_KEY) → ~/.teshq/.teshq.env
Non-secret settings → ~/.teshq/config.yaml
"""

import os
import sys
from getpass import getpass
from typing import Optional
from urllib.parse import quote_plus

import typer
from sqlalchemy.engine.url import make_url

from teshq.config.loader import (
    DEFAULT_GEMINI_MODEL,
    get_config_with_source,
    save_config,
)
from teshq.core.connectors import UnifiedDatabaseConnector
from teshq.utils.ui import print_config
from teshq.utils.ui import (
    clear_screen,
    confirm,
    error,
    handle_error,
    indent_context,
    info,
    print_divider,
    print_header,
    prompt,
    section,
    space,
    success,
    tip,
    warning,
)
from teshq.core.validation import ConfigValidator, validate_production_readiness

app = typer.Typer(
    invoke_without_command=True,
    help="Configure database, AI models, and CLI settings.",
)
# Get supported database types from unified connector
SUPPORTED_DBS = UnifiedDatabaseConnector.get_supported_databases()

# Help panel category constants for beautiful CLI help organization
PANEL_QUICK = "✨ Quick Setup (Interactive)"
PANEL_DB = "🗄️ Database Options (Power Users & Scripting)"
PANEL_AI = "🤖 AI Provider Options (Power Users & Scripting)"
PANEL_STORAGE = "⚙️ Storage & Settings"


# ═══════════════════════════════════════════════════════════════════════════════
#  OBSIDIAN STATUS DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

def display_config_dashboard():
    """
    Render a clean, non-overwhelming Obsidian-styled status dashboard.

    Shows three categories at a glance:
      1. Database — connection status + clean relative URI (especially for SQLite)
      2. AI Model — provider + model name + readiness
      3. Exports  — relative output directory
    """
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich import box

    console = Console()
    config, sources = get_config_with_source()

    # ── Database ──────────────────────────────────────────────────────────
    db_url = config.get("DATABASE_URL", "")
    if db_url:
        try:
            url_obj = make_url(db_url)
            backend = (url_obj.get_backend_name() or "database").lower()
            if backend == "sqlite":
                db_path = url_obj.database or ""
                # Display clean relative path if inside cwd
                try:
                    rel_path = os.path.relpath(db_path, os.getcwd())
                    display_path = rel_path if not rel_path.startswith("..") else os.path.basename(db_path)
                except Exception:
                    display_path = os.path.basename(db_path) or db_path
                display_path = display_path.replace("\\", "/")
                masked = f"sqlite:///{display_path}"
                db_status = "[#10B981]● Connected[/#10B981]"
                db_detail = f"[#C8C8D4]{masked}[/#C8C8D4]"
            else:
                db_type = backend.upper()
                db_name = url_obj.database or "—"
                host = url_obj.host or "localhost"
                port_str = f":{url_obj.port}" if url_obj.port else ""
                user_str = f"{url_obj.username}@" if url_obj.username else ""
                masked = f"{backend}://{user_str}*****@{host}{port_str}/{db_name}" if url_obj.username else f"{backend}://{host}{port_str}/{db_name}"
                db_status = "[#10B981]● Connected[/#10B981]"
                db_detail = f"[#C8C8D4]{masked}[/#C8C8D4]"
        except Exception:
            db_status = "[#F59E0B]● Configured[/#F59E0B]"
            db_detail = "[#8888A0](URL set but could not parse)[/#8888A0]"
    else:
        db_status = "[#EF4444]● Not Configured[/#EF4444]"
        db_detail = "[#5E5E78]Run: teshq config --db[/#5E5E78]"

    # ── AI Model ──────────────────────────────────────────────────────────
    provider = config.get("LLM_PROVIDER", "google").lower()
    if provider == "azure":
        ai_name = "Azure OpenAI"
        deployment = config.get("AZURE_OPENAI_DEPLOYMENT", "—")
        ai_detail = f"[#C8C8D4]{deployment}[/#C8C8D4]"
        api_key = config.get("AZURE_OPENAI_API_KEY", "") or os.environ.get("AZURE_OPENAI_API_KEY", "")
        ai_status = "[#10B981]● Ready[/#10B981]" if api_key else "[#EF4444]● API Key Missing[/#EF4444]"
    elif provider == "local":
        ai_name = "Local GGUF"
        model_path = config.get("LOCAL_MODEL_PATH", "")
        if model_path:
            try:
                rel_m = os.path.relpath(model_path, os.getcwd())
                display_m = rel_m if not rel_m.startswith("..") else os.path.basename(model_path)
            except Exception:
                display_m = os.path.basename(model_path)
            display_m = display_m.replace("\\", "/")
        else:
            display_m = "—"
        ai_detail = f"[#C8C8D4]{display_m}[/#C8C8D4]"
        ai_status = "[#10B981]● Ready[/#10B981]" if model_path else "[#EF4444]● Model Missing[/#EF4444]"
    else:
        ai_name = "Google Gemini"
        model = config.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
        ai_detail = f"[#C8C8D4]{model}[/#C8C8D4]"
        api_key = config.get("GEMINI_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
        ai_status = "[#10B981]● Ready[/#10B981]" if api_key else "[#EF4444]● API Key Missing[/#EF4444]"

    # ── Exports ───────────────────────────────────────────────────────────
    output_path = config.get("OUTPUT_PATH", ".teshq/outputs/")
    home = os.path.expanduser("~")
    norm_out = os.path.normpath(output_path)
    norm_home = os.path.normpath(home)

    if norm_out.lower().startswith(norm_home.lower()):
        display_output = "~" + norm_out[len(norm_home):]
    else:
        try:
            rel_output = os.path.relpath(output_path, os.getcwd())
            display_output = rel_output if not rel_output.startswith("..") else output_path
        except Exception:
            display_output = output_path

    display_output = display_output.replace("\\", "/")
    if not display_output.endswith("/"):
        display_output += "/"

    # ── Build Dashboard Table ─────────────────────────────────────────────
    table = Table(
        show_header=False, box=box.SIMPLE, padding=(0, 2),
        expand=True, show_edge=False,
    )
    table.add_column("Category", style="#8888A0", width=14)
    table.add_column("Status", width=22)
    table.add_column("Detail", ratio=1)

    table.add_row("Database", db_status, db_detail)
    table.add_row("AI Engine", ai_status, f"[#6366F1]{ai_name}[/#6366F1]  {ai_detail}")
    table.add_row("Exports", "[#10B981]● Ready[/#10B981]", f"[#C8C8D4]{display_output}[/#C8C8D4]")

    panel = Panel(
        table,
        title="[bold #F1F1F6]⚙ TESHQ Configuration[/bold #F1F1F6]",
        subtitle="[#5E5E78]~/.teshq/[/#5E5E78]",
        border_style="#3A3A48",
        padding=(1, 2),
    )
    console.print()
    console.print(panel)
    console.print()

    # ── Quick Actions ─────────────────────────────────────────────────────
    console.print("  [#8888A0]Quick Actions:[/#8888A0]")
    console.print(f"    [#6366F1]teshq config --wizard[/#6366F1]   [#5E5E78]Guided setup (DB + AI in 30s)[/#5E5E78]")
    console.print(f"    [#6366F1]teshq config --db[/#6366F1]       [#5E5E78]Configure database interactively[/#5E5E78]")
    console.print(f"    [#6366F1]teshq config --ai[/#6366F1]       [#5E5E78]Configure AI provider (Gemini / Azure / Local)[/#5E5E78]")
    console.print(f"    [#6366F1]teshq config validate[/#6366F1]   [#5E5E78]Test connection & validate[/#5E5E78]")
    console.print(f"    [#6366F1]teshq config --help[/#6366F1]     [#5E5E78]Show all options & scripting flags[/#5E5E78]")
    console.print()


# ═══════════════════════════════════════════════════════════════════════════════
#  QUICK SETUP WIZARD
# ═══════════════════════════════════════════════════════════════════════════════

def run_quick_wizard() -> dict:
    """
    Guided quick setup: DB + AI in under 30 seconds.

    Returns a config dict ready for save_config().
    """
    from rich.console import Console
    console = Console()

    console.print()
    console.print("  [bold #F1F1F6]Quick Setup Wizard[/bold #F1F1F6]")
    console.print("  [#5E5E78]Configure database and AI in a few steps.[/#5E5E78]")
    console.print()

    config_to_save = {}

    # ── Step 1: Database ──────────────────────────────────────────────────
    console.print("  [bold #6366F1]Step 1/2[/bold #6366F1] [#C8C8D4]Database Connection[/#C8C8D4]")
    console.print()

    sqlite_files = [f for f in os.listdir(".") if f.endswith((".sqlite", ".db", ".sqlite3")) and os.path.isfile(f)]
    default_db_type = "sqlite" if sqlite_files else "postgresql"

    db_type = prompt("  Database type", choices=SUPPORTED_DBS, default=default_db_type).lower()
    if db_type == "sqlite":
        default_sqlite = sqlite_files[0] if sqlite_files else "sqlite.db"
        db_name = prompt("  SQLite file path", default=default_sqlite)
        config_to_save["DATABASE_URL"] = f"sqlite:///{db_name}"
    else:
        db_user = prompt("  Username")
        db_password = getpass("  Password: ")
        db_host = prompt("  Host", default="localhost")
        default_port = 5432 if db_type == "postgresql" else 3306
        db_port = prompt("  Port", default=default_port, expected_type=int, validate=lambda p: 1 <= p <= 65535)
        db_name = prompt("  Database name")
        safe_password = quote_plus(db_password)
        config_to_save["DATABASE_URL"] = f"{db_type}://{db_user}:{safe_password}@{db_host}:{db_port}/{db_name}"

    console.print(f"  [#10B981]✓[/#10B981] Database configured")
    console.print()

    # ── Step 2: AI Provider ───────────────────────────────────────────────
    console.print("  [bold #6366F1]Step 2/2[/bold #6366F1] [#C8C8D4]AI Model Provider[/#C8C8D4]")
    console.print()

    ai_choice = prompt(
        "  Provider",
        choices=["gemini", "azure", "local"],
        default="gemini"
    ).lower()

    if ai_choice == "gemini":
        api_key = getpass("  Gemini API Key: ")
        if api_key:
            config_to_save["GEMINI_API_KEY"] = api_key
        model = prompt("  Model", default=DEFAULT_GEMINI_MODEL)
        config_to_save["GEMINI_MODEL"] = model
        config_to_save["LLM_PROVIDER"] = "google"
    elif ai_choice == "azure":
        api_key = getpass("  Azure API Key: ")
        if api_key:
            config_to_save["AZURE_OPENAI_API_KEY"] = api_key
        endpoint = prompt("  Endpoint URL")
        deployment = prompt("  Deployment name")
        config_to_save["AZURE_OPENAI_ENDPOINT"] = endpoint
        config_to_save["AZURE_OPENAI_DEPLOYMENT"] = deployment
        config_to_save["AZURE_OPENAI_API_VERSION"] = "2024-10-21"
        config_to_save["LLM_PROVIDER"] = "azure"
    else:
        from teshq.core.hardware import detect_hardware
        hw = detect_hardware()
        default_model_dir = os.path.expanduser("~/.teshq/models")
        default_model_path = ""
        if os.path.exists(default_model_dir):
            files = [f for f in os.listdir(default_model_dir) if f.endswith(".gguf")]
            if files:
                default_model_path = os.path.join(default_model_dir, files[0])
        model_path = prompt("  GGUF model path", default=default_model_path)
        config_to_save["LOCAL_MODEL_PATH"] = model_path
        config_to_save["LOCAL_N_GPU_LAYERS"] = int(prompt(
            "  GPU layers (-1=auto, 0=CPU)",
            default=str(hw.recommended_n_gpu_layers),
        ))
        config_to_save["LLM_PROVIDER"] = "local"

    console.print(f"  [#10B981]✓[/#10B981] AI provider configured")
    console.print()

    return config_to_save


# ═══════════════════════════════════════════════════════════════════════════════
#  INTERACTIVE CONFIGURATION HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def display_current_config():
    """Displays the current configuration, masking sensitive data like API keys."""
    config, sources = get_config_with_source()
    if not config:
        warning("No configuration found.")
        with indent_context():
            tip("Use interactive configuration options (e.g., --db, --ai) to set up TESH-Query.")
        return

    try:
        print_config(config, "Current Configuration", mask_keys=["GEMINI_API_KEY", "AZURE_OPENAI_API_KEY"])
    except Exception:
        try:
            print_config(list(config.items()), "Current Configuration", mask_keys=["GEMINI_API_KEY", "AZURE_OPENAI_API_KEY"])
        except Exception:
            info("Current Configuration:")
            with indent_context():
                for key, value in config.items():
                    if key in ("GEMINI_API_KEY", "AZURE_OPENAI_API_KEY") and value:
                        display_value = "********"
                    else:
                        display_value = value
                    info(f"{key}: {display_value}")

    space()
    info("Configuration Source:")
    with indent_context():
        for key, source in sources.items():
            info(f"{key}: {source}")


def configure_database_interactive() -> str:
    """
    Interactively configure the database connection.
    Prompts the user for details and constructs the final DB URL.
    """
    info("Setting up database connection...")
    space()

    sqlite_files = [f for f in os.listdir(".") if f.endswith((".sqlite", ".db", ".sqlite3")) and os.path.isfile(f)]
    default_db_type = "sqlite" if sqlite_files else "postgresql"

    db_type = prompt("Database type", choices=SUPPORTED_DBS, default=default_db_type).lower()
    if db_type == "sqlite":
        default_sqlite = sqlite_files[0] if sqlite_files else "sqlite.db"
        db_name = prompt("SQLite database file path", default=default_sqlite)
        return f"sqlite:///{db_name}"

    info(f"Configuring {db_type.upper()} connection...")
    db_user = prompt("Database username")
    while True:
        db_password = getpass("Database password: ")
        if not db_password:
            if not confirm("Empty password – is this correct?"):
                continue
        break
    db_host = prompt("Database host", default="localhost")
    default_port = 5432 if db_type == "postgresql" else 3306
    db_port = prompt("Database port", default=default_port, expected_type=int, validate=lambda p: 1 <= p <= 65535)
    db_name = prompt("Database name")
    safe_password = quote_plus(db_password)
    db_url = f"{db_type}://{db_user}:{safe_password}@{db_host}:{db_port}/{db_name}"

    try:
        url_obj = make_url(db_url)
        masked_url = str(url_obj._replace(password="********")) if url_obj.password else db_url
        info(f"Database URL: {masked_url}")
    except Exception:
        info("Database URL configured successfully.")

    return db_url


def configure_gemini_interactive() -> tuple:
    """
    Interactively configure Gemini API settings.
    Prompts the user for the Gemini API key and model name.
    """
    info("Setting up Gemini API configuration...")
    space()

    while True:
        api_key = getpass("Gemini API Key (press Enter to skip): ")
        if api_key:
            break
        elif confirm("Skip Gemini API configuration?", default=True):
            api_key = None
            break
        else:
            warning("API key is required for Gemini functionality")
    model_name = prompt("Gemini model name", default=DEFAULT_GEMINI_MODEL)
    return api_key, model_name


def configure_azure_interactive() -> dict:
    """
    Interactively configure Azure OpenAI settings.
    Prompts the user for endpoint, deployment, API key, and version.
    """
    info("Setting up Azure OpenAI configuration...")
    space()

    while True:
        api_key = getpass("Azure OpenAI API Key: ")
        if api_key:
            break
        warning("Azure OpenAI API key is required.")

    endpoint = prompt("Azure OpenAI Endpoint (e.g. https://<resource>.openai.azure.com/)")
    deployment = prompt("Azure OpenAI Deployment name (model deployment)")
    api_version = prompt("Azure OpenAI API Version", default="2024-10-21")

    return {
        "AZURE_OPENAI_API_KEY": api_key,
        "AZURE_OPENAI_ENDPOINT": endpoint,
        "AZURE_OPENAI_DEPLOYMENT": deployment,
        "AZURE_OPENAI_API_VERSION": api_version,
        "LLM_PROVIDER": "azure",
    }


def configure_local_interactive() -> dict:
    """
    Interactively configure local GGUF LLM settings.
    """
    info("Setting up local GGUF LLM configuration...")
    space()

    from teshq.core.hardware import detect_hardware
    hw = detect_hardware()

    tip(f"Recommended model size: Sub-4B parameters. Suggested quant: {hw.recommended_quant}.")

    default_model_dir = os.path.expanduser("~/.teshq/models")
    default_model_path = ""
    if os.path.exists(default_model_dir):
        files = [f for f in os.listdir(default_model_dir) if f.endswith(".gguf")]
        if files:
            default_model_path = os.path.join(default_model_dir, files[0])

    model_path = prompt("Local GGUF model path", default=default_model_path)
    
    gpu_layers = prompt(
        "Number of layers to offload to GPU (-1 for auto, 0 for CPU-only)",
        default=str(hw.recommended_n_gpu_layers),
        validate=lambda x: x.replace("-", "").isdigit()
    )
    
    ctx_size = prompt(
        "Local model context size",
        default=str(hw.recommended_n_ctx),
        expected_type=int
    )
    
    threads = prompt(
        "Number of CPU threads (0 for auto)",
        default=str(max(1, hw.cpu_cores - 1)),
        expected_type=int
    )

    return {
        "LOCAL_MODEL_PATH": model_path,
        "LOCAL_N_GPU_LAYERS": int(gpu_layers),
        "LOCAL_N_CTX": int(ctx_size),
        "LOCAL_N_THREADS": int(threads),
        "LLM_PROVIDER": "local",
    }


def configure_ai_interactive() -> dict:
    """
    Interactively choose and configure an AI provider (Gemini, Azure, or Local).
    Returns a dict of configuration keys and values ready to save.
    """
    from rich.console import Console
    console = Console()
    console.print()
    console.print("  [bold #F1F1F6]Choose AI Provider:[/bold #F1F1F6]")
    console.print("    [#6366F1]1.[/#6366F1] [bold]Google Gemini[/bold]       [#5E5E78](Cloud API - Fast, free tier available)[/#5E5E78]")
    console.print("    [#6366F1]2.[/#6366F1] [bold]Azure OpenAI[/bold]        [#5E5E78](Enterprise Cloud API)[/#5E5E78]")
    console.print("    [#6366F1]3.[/#6366F1] [bold]Local GGUF Model[/bold]    [#5E5E78](Offline / On-Device, CPU or GPU)[/#5E5E78]")
    console.print()
    choice = prompt("  Select provider (1, 2, or 3)", choices=["1", "2", "3", "gemini", "azure", "local"], default="1").lower()

    if choice in ("1", "gemini"):
        api_key, model_name = configure_gemini_interactive()
        cfg = {"LLM_PROVIDER": "google", "GEMINI_MODEL": model_name}
        if api_key:
            cfg["GEMINI_API_KEY"] = api_key
        return cfg
    elif choice in ("2", "azure"):
        return configure_azure_interactive()
    else:
        return configure_local_interactive()


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN CONFIG COMMAND (Backward-compatible, beautifully grouped)
# ═══════════════════════════════════════════════════════════════════════════════

@app.callback(invoke_without_command=True)
def config(
    ctx: typer.Context,
    # ── Quick Setup (Interactive) ─────────────────────────────────────────────
    wizard: bool = typer.Option(
        False, "--wizard", "-w",
        help="Run the Quick Setup Wizard (DB + AI in 30 seconds)",
        rich_help_panel=PANEL_QUICK,
    ),
    show_status: bool = typer.Option(
        False, "--status", "-s",
        help="Show configuration status dashboard and exit",
        rich_help_panel=PANEL_QUICK,
    ),
    force_configure_db: bool = typer.Option(
        False, "--db", "-db",
        help="Interactive database configuration",
        rich_help_panel=PANEL_QUICK,
    ),
    force_configure_ai: bool = typer.Option(
        False, "--ai", "-ai",
        help="Interactive AI provider configuration (Gemini, Azure, or Local)",
        rich_help_panel=PANEL_QUICK,
    ),
    force_configure_gemini: bool = typer.Option(
        False, "--gemini", "-gemini",
        help="Interactive Google Gemini API configuration",
        rich_help_panel=PANEL_QUICK,
    ),
    force_configure_azure: bool = typer.Option(
        False, "--azure", "-azure",
        help="Interactive Azure OpenAI configuration",
        rich_help_panel=PANEL_QUICK,
    ),
    force_configure_local: bool = typer.Option(
        False, "--local", "-local",
        help="Interactive local GGUF model configuration",
        rich_help_panel=PANEL_QUICK,
    ),

    # ── Database Options (Power Users & Scripting) ───────────────────────────
    db_url: Optional[str] = typer.Option(
        None, "--db-url",
        help="Full database URL (e.g. postgresql://user:pass@host:port/dbname or sqlite:///path.db)",
        rich_help_panel=PANEL_DB,
    ),
    db_type_opt: Optional[str] = typer.Option(
        None, "--db-type",
        help=f"Database dialect ({', '.join(SUPPORTED_DBS)})",
        case_sensitive=False,
        rich_help_panel=PANEL_DB,
    ),
    db_host_opt: Optional[str] = typer.Option(
        None, "--db-host",
        help="Database server host [default: localhost]",
        rich_help_panel=PANEL_DB,
    ),
    db_port_opt: Optional[int] = typer.Option(
        None, "--db-port",
        help="Database server port (e.g. 5432 for Postgres, 3306 for MySQL)",
        rich_help_panel=PANEL_DB,
    ),
    db_name_opt: Optional[str] = typer.Option(
        None, "--db-name",
        help="Database name (or SQLite file path)",
        rich_help_panel=PANEL_DB,
    ),
    db_user_opt: Optional[str] = typer.Option(
        None, "--db-user",
        help="Database username",
        rich_help_panel=PANEL_DB,
    ),
    db_password_opt: Optional[str] = typer.Option(
        None, "--db-password",
        help="Database password (prompts securely if omitted)",
        rich_help_panel=PANEL_DB,
    ),

    # ── AI Provider Options (Power Users & Scripting) ─────────────────────────
    llm_provider_opt: Optional[str] = typer.Option(
        None, "--llm-provider",
        help="Active LLM provider: 'google', 'azure', or 'local'",
        rich_help_panel=PANEL_AI,
    ),
    gemini_api_key_opt: Optional[str] = typer.Option(
        None, "--gemini-api-key",
        help="Google Gemini API Key",
        rich_help_panel=PANEL_AI,
    ),
    gemini_model_name_opt: str = typer.Option(
        DEFAULT_GEMINI_MODEL, "--gemini-model",
        help="Gemini model name",
        show_default=True,
        rich_help_panel=PANEL_AI,
    ),
    azure_endpoint_opt: Optional[str] = typer.Option(
        None, "--azure-endpoint",
        help="Azure OpenAI endpoint URL (e.g. https://<resource>.openai.azure.com/)",
        rich_help_panel=PANEL_AI,
    ),
    azure_deployment_opt: Optional[str] = typer.Option(
        None, "--azure-deployment",
        help="Azure OpenAI model deployment name",
        rich_help_panel=PANEL_AI,
    ),
    azure_api_key_opt: Optional[str] = typer.Option(
        None, "--azure-api-key",
        help="Azure OpenAI API Key",
        rich_help_panel=PANEL_AI,
    ),
    azure_api_version_opt: Optional[str] = typer.Option(
        None, "--azure-api-version",
        help="Azure OpenAI API version [default: 2024-10-21]",
        rich_help_panel=PANEL_AI,
    ),
    local_model_path_opt: Optional[str] = typer.Option(
        None, "--local-model-path",
        help="Path to local GGUF model file",
        rich_help_panel=PANEL_AI,
    ),
    local_gpu_layers_opt: Optional[int] = typer.Option(
        None, "--local-gpu-layers",
        help="GPU layers to offload (-1 for auto, 0 for CPU-only)",
        rich_help_panel=PANEL_AI,
    ),
    local_ctx_opt: Optional[int] = typer.Option(
        None, "--local-ctx",
        help="Context window size for local LLM",
        rich_help_panel=PANEL_AI,
    ),
    local_threads_opt: Optional[int] = typer.Option(
        None, "--local-threads",
        help="CPU threads for local inference (0 for auto)",
        rich_help_panel=PANEL_AI,
    ),

    # ── Storage & System Settings ─────────────────────────────────────────────
    save: bool = typer.Option(
        True, "--save/--no-save",
        help="Save configuration to ~/.teshq/ [default: save]",
        rich_help_panel=PANEL_STORAGE,
    ),
    output_file_path: Optional[str] = typer.Option(
        None, "--output-file-path",
        help="Default output directory for exports [default: .teshq/outputs/]",
        rich_help_panel=PANEL_STORAGE,
    ),
    file_store_path: Optional[str] = typer.Option(
        None, "--file-store-path",
        help="File store directory [default: ~/.teshq/store]",
        rich_help_panel=PANEL_STORAGE,
    ),
):
    """
    Configure database, AI model providers, and export paths.

    Beginner & Interactive:
      • teshq config           → View current configuration dashboard
      • teshq config --wizard   → 30-second guided setup (DB + AI)
      • teshq config --db       → Configure database connection interactively
      • teshq config --ai       → Configure AI model provider interactively

    Power Users & Scripting:
      • Pass direct CLI flags (e.g. --db-url, --gemini-api-key, --llm-provider)
      • Use 'teshq config validate' to check connections and production readiness
    """
    if ctx.invoked_subcommand is not None:
        return

    try:
        # Determine if any direct options or action flags were passed
        db_options_provided = any([db_url, db_type_opt, db_user_opt, db_password_opt, db_host_opt, db_port_opt, db_name_opt])
        file_path_options_provided = any([output_file_path, file_store_path])
        gemini_options_provided = gemini_api_key_opt is not None or gemini_model_name_opt != DEFAULT_GEMINI_MODEL
        azure_options_provided = any([azure_endpoint_opt, azure_deployment_opt, azure_api_version_opt, azure_api_key_opt])
        local_options_provided = any([local_model_path_opt, local_gpu_layers_opt is not None, local_ctx_opt, local_threads_opt])
        interactive_requested = any([force_configure_db, force_configure_ai, force_configure_gemini, force_configure_azure, force_configure_local, wizard])

        # ── Default / Status: show dashboard and exit cleanly ──────────────
        if show_status or (
            not db_options_provided
            and not file_path_options_provided
            and not gemini_options_provided
            and not azure_options_provided
            and not local_options_provided
            and not interactive_requested
            and llm_provider_opt is None
        ):
            display_config_dashboard()
            raise typer.Exit(0)

        # ── --wizard flag: guided Quick Setup ──────────────────────────────
        if wizard:
            try:
                wizard_config = run_quick_wizard()
                if save and wizard_config:
                    if save_config(wizard_config):
                        success("🎉 Configuration saved successfully!")
                        space()
                        display_config_dashboard()
                    else:
                        error("Could not save configuration.")
                        raise typer.Exit(1)
                elif wizard_config:
                    warning("Configuration not saved (--no-save specified).")
            except KeyboardInterrupt:
                warning("\nWizard cancelled.")
                raise typer.Exit(0)
            raise typer.Exit(0)

        # ── Flag-based & Interactive Configuration ─────────────────────────
        clear_screen()
        print_header("🔧 TESHQ CONFIGURATION", "Database & LLM Setup")

        final_db_url_to_save = None
        actual_gemini_api_key_to_save = gemini_api_key_opt
        actual_gemini_model_to_save = gemini_model_name_opt
        azure_config_to_save: dict = {}
        local_config_to_save: dict = {}

        action_taken = False

        # Database configuration logic
        if db_url:
            with section("Database Configuration"):
                info("Using provided database URL.")
                final_db_url_to_save = db_url
                action_taken = True
        elif force_configure_db:
            with section("Database Configuration"):
                try:
                    final_db_url_to_save = configure_database_interactive()
                    action_taken = True
                except KeyboardInterrupt:
                    warning("Database configuration cancelled.")
                    raise typer.Exit(0)
        elif db_options_provided:
            with section("Database Configuration"):
                info("Constructing database URL from provided options...")
                if not db_type_opt:
                    error("--db-type is required with individual database options.")
                    raise typer.Exit(1)
                db_type = db_type_opt.lower()
                if db_type not in SUPPORTED_DBS:
                    error(f"Unsupported database type: {db_type}")
                    raise typer.Exit(1)
                if db_type == "sqlite":
                    if not db_name_opt:
                        error("--db-name is required for SQLite.")
                        raise typer.Exit(1)
                    final_db_url_to_save = f"sqlite:///{db_name_opt}"
                else:
                    required_opts = [db_user_opt, db_host_opt, db_name_opt]
                    if not all(required_opts):
                        error("--db-user, --db-host, and --db-name are required for non-SQLite databases.")
                        raise typer.Exit(1)
                    password = db_password_opt if db_password_opt else getpass("Database password: ")
                    host = db_host_opt or "localhost"
                    port = db_port_opt or (5432 if db_type == "postgresql" else 3306)
                    safe_password = quote_plus(password)
                    final_db_url_to_save = f"{db_type}://{db_user_opt}:{safe_password}@{host}:{port}/{db_name_opt}"
                success("Database URL constructed successfully.")
                action_taken = True

        # Interactive AI provider selector
        if force_configure_ai:
            with section("AI Model Configuration"):
                try:
                    ai_config_to_save = configure_ai_interactive()
                    if ai_config_to_save:
                        provider = ai_config_to_save.get("LLM_PROVIDER", "google")
                        if provider == "google":
                            if "GEMINI_API_KEY" in ai_config_to_save:
                                actual_gemini_api_key_to_save = ai_config_to_save["GEMINI_API_KEY"]
                            if "GEMINI_MODEL" in ai_config_to_save:
                                actual_gemini_model_to_save = ai_config_to_save["GEMINI_MODEL"]
                        elif provider == "azure":
                            azure_config_to_save = ai_config_to_save
                        elif provider == "local":
                            local_config_to_save = ai_config_to_save
                        action_taken = True
                except KeyboardInterrupt:
                    warning("AI configuration cancelled.")
                    raise typer.Exit(0)

        # Gemini configuration logic
        if force_configure_gemini:
            with section("Gemini API Configuration"):
                try:
                    api_key, model_name = configure_gemini_interactive()
                    actual_gemini_api_key_to_save = api_key
                    actual_gemini_model_to_save = model_name
                    action_taken = True
                except KeyboardInterrupt:
                    warning("Gemini configuration cancelled.")
                    raise typer.Exit(0)
        elif gemini_options_provided:
            with section("Gemini API Configuration"):
                info("Using provided Gemini API configuration.")
                action_taken = True

        # Azure OpenAI configuration logic
        if force_configure_azure:
            with section("Azure OpenAI Configuration"):
                try:
                    azure_config_to_save = configure_azure_interactive()
                    action_taken = True
                except KeyboardInterrupt:
                    warning("Azure OpenAI configuration cancelled.")
                    raise typer.Exit(0)
        elif azure_options_provided:
            with section("Azure OpenAI Configuration"):
                info("Using provided Azure OpenAI configuration.")
                azure_api_key = azure_api_key_opt or os.environ.get("AZURE_OPENAI_API_KEY")
                if not azure_api_key:
                    error("Azure OpenAI API key is required. Pass --azure-api-key or set AZURE_OPENAI_API_KEY env var.")
                    raise typer.Exit(1)
                if not azure_endpoint_opt:
                    error("--azure-endpoint is required when using Azure OpenAI.")
                    raise typer.Exit(1)
                if not azure_deployment_opt:
                    error("--azure-deployment is required when using Azure OpenAI.")
                    raise typer.Exit(1)
                azure_config_to_save = {
                    k: v for k, v in {
                        "AZURE_OPENAI_API_KEY": azure_api_key,
                        "AZURE_OPENAI_ENDPOINT": azure_endpoint_opt,
                        "AZURE_OPENAI_DEPLOYMENT": azure_deployment_opt,
                        "AZURE_OPENAI_API_VERSION": azure_api_version_opt or "2024-10-21",
                        "LLM_PROVIDER": llm_provider_opt or "azure",
                    }.items() if v is not None
                }
                action_taken = True

        # Local LLM configuration logic
        if force_configure_local:
            with section("Local LLM Configuration"):
                try:
                    local_config_to_save = configure_local_interactive()
                    action_taken = True
                except KeyboardInterrupt:
                    warning("Local LLM configuration cancelled.")
                    raise typer.Exit(0)
        elif local_options_provided:
            with section("Local LLM Configuration"):
                info("Using provided local GGUF LLM configuration.")
                local_config_to_save = {
                    k: v for k, v in {
                        "LOCAL_MODEL_PATH": local_model_path_opt,
                        "LOCAL_N_GPU_LAYERS": local_gpu_layers_opt,
                        "LOCAL_N_CTX": local_ctx_opt,
                        "LOCAL_N_THREADS": local_threads_opt,
                        "LLM_PROVIDER": llm_provider_opt or "local",
                    }.items() if v is not None
                }
                action_taken = True

        # Provider override logic
        if llm_provider_opt and not azure_config_to_save and not local_config_to_save and not gemini_options_provided:
            valid_provider = llm_provider_opt.lower()
            if valid_provider not in ("google", "azure", "local"):
                handle_error(
                    ValueError(f"Invalid LLM provider: {llm_provider_opt}"),
                    "Configuration",
                    suggest_action="Use 'google', 'azure', or 'local'"
                )
                raise typer.Exit(1)
            local_config_to_save = {"LLM_PROVIDER": valid_provider}
            action_taken = True

        # File Path Configuration
        if file_path_options_provided:
            with section("File Path Configuration"):
                info("Using provided file store path(s).")
                action_taken = True

        # If no configuration was made, show dashboard
        if not action_taken:
            display_config_dashboard()
            raise typer.Exit(0)

        # Save configuration if required
        if save:
            with section("Saving Configuration"):
                config_to_save = {}

                # Database
                if final_db_url_to_save:
                    config_to_save["DATABASE_URL"] = final_db_url_to_save

                # Gemini
                if force_configure_gemini or (force_configure_ai and actual_gemini_api_key_to_save) or gemini_options_provided:
                    if actual_gemini_api_key_to_save is not None:
                        config_to_save["GEMINI_API_KEY"] = actual_gemini_api_key_to_save
                    if actual_gemini_model_to_save is not None:
                        config_to_save["GEMINI_MODEL"] = actual_gemini_model_to_save
                    if not azure_config_to_save and not local_config_to_save:
                        config_to_save["LLM_PROVIDER"] = "google"

                # Azure OpenAI
                if azure_config_to_save:
                    config_to_save.update(azure_config_to_save)

                # Local LLM
                if local_config_to_save:
                    config_to_save.update(local_config_to_save)

                # Provider override
                if llm_provider_opt:
                    config_to_save["LLM_PROVIDER"] = llm_provider_opt.lower()

                # Output file path
                if output_file_path:
                    resolved_output_path = os.path.abspath(output_file_path)
                    os.makedirs(os.path.dirname(resolved_output_path) if os.path.splitext(resolved_output_path)[1] else resolved_output_path, exist_ok=True)
                    config_to_save["OUTPUT_PATH"] = resolved_output_path

                # File store path
                if file_store_path:
                    resolved_file_store_path = os.path.abspath(file_store_path)
                    os.makedirs(resolved_file_store_path, exist_ok=True)
                    config_to_save["FILE_STORE_PATH"] = resolved_file_store_path

                if config_to_save:
                    if save_config(config_to_save):
                        print_divider("Configuration Complete")
                        success("🎉 All configuration saved successfully!")
                        with indent_context():
                            tip("Run your TESH-Query commands to start using the configured settings.")
                    else:
                        error("Some configuration files could not be saved.")
                        raise typer.Exit(1)
                else:
                    warning("No new configuration to save.")

        else:
            with section("Configuration Preview"):
                warning("Configuration not saved (--no-save specified).")
                if final_db_url_to_save:
                    info("Database URL would be saved.")
                if actual_gemini_api_key_to_save:
                    info("Gemini API configuration would be saved.")
                if file_path_options_provided:
                    info("File paths would be saved.")
                if local_config_to_save:
                    info("Local GGUF LLM configuration would be saved.")

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        warning("\nOperation cancelled.")
        raise typer.Exit(0)
    except Exception as e:
        handle_error(
            e,
            "Configuration Setup",
            show_traceback="--debug" in sys.argv,
            suggest_action="Check your input values and try again",
        )
        raise typer.Exit(1)


@app.command(name="validate", help="Validate current configuration for production readiness")
def validate_config():
    """Validate the current configuration for production deployment."""
    try:
        with section("Configuration Validation"):
            info("Checking configuration for production readiness...")

            # Get current configuration
            config, sources = get_config_with_source()

            if not config:
                error("No configuration found")
                tip("Run 'teshq config --db' or 'teshq config --wizard' to set up configuration")
                raise typer.Exit(1)

            # Validate configuration
            config_errors = ConfigValidator.validate_config(config)

            if config_errors:
                error("Configuration validation failed:")
                with indent_context():
                    for err in config_errors:
                        error(f"• {err}")
                tip("Run 'teshq config --wizard' to fix configuration issues")
                raise typer.Exit(1)

            # Test database connection
            if "DATABASE_URL" in config:
                with section("Database Connection Test"):
                    info("Testing database connection...")
                    is_connected, message = ConfigValidator.validate_database_connection(config["DATABASE_URL"])
                    if is_connected:
                        success(f"✅ {message}")
                    else:
                        error(f"❌ {message}")
                        tip("Check your database server and connection details")
                        raise typer.Exit(1)

            # Production readiness check
            with section("Production Readiness Assessment"):
                info("Evaluating production readiness...")
                is_ready, issues = validate_production_readiness(config)

                if is_ready:
                    success("🎉 Configuration is production-ready!")
                else:
                    warning("Configuration has production readiness issues:")
                    with indent_context():
                        for issue in issues:
                            if issue.startswith("WARNING"):
                                warning(f"• {issue}")
                            else:
                                error(f"• {issue}")

                    if any(not issue.startswith("WARNING") for issue in issues):
                        error("Critical issues must be resolved before production deployment")
                        raise typer.Exit(1)
                    else:
                        warning("Consider addressing warnings for optimal production setup")

            success("✅ Configuration validation completed successfully")

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        warning("\nValidation cancelled.")
        raise typer.Exit(0)
    except Exception as e:
        handle_error(
            e, "Configuration Validation", show_traceback=True, suggest_action="Check your configuration and try again"
        )
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
