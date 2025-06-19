import json
import os
from getpass import getpass
from urllib.parse import quote_plus

import typer
from sqlalchemy.engine.url import make_url

from teshq.utils.ui import (
    clear_screen,
    confirm,
    error,
    handle_error,
    indent_context,
    info,
    print_config,
    print_divider,
    print_header,
    prompt,
    section,
    space,
    success,
    tip,
    warning,
)

app = typer.Typer()
SUPPORTED_DBS = ["postgresql", "mysql", "sqlite"]
ENV_FILE = ".env"
JSON_CONFIG_FILE = "config.json"
DEFAULT_GEMINI_MODEL = "gemini-1.5-flash-latest"


def update_env_file(data_to_save: dict):
    """Reads existing .env, updates it with new data, and writes back."""
    env_vars = {}

    if os.path.exists(ENV_FILE):
        try:
            with open(ENV_FILE, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, value = line.split("=", 1)
                        env_vars[key.strip()] = value.strip()
        except Exception as e:
            handle_error(e, "Reading .env file", suggest_action="Check file permissions and format")
            return False

    # Update with new data
    for key, value in data_to_save.items():
        if value is not None:
            env_vars[key] = str(value)
        elif key in env_vars:
            del env_vars[key]

    try:
        with open(ENV_FILE, "w") as f:
            for key, value in env_vars.items():
                f.write(f"{key}={value}\n")

        success(f"Configuration updated in {ENV_FILE}")
        with indent_context():
            tip("Your configuration is saved locally to ensure data security")
        return True
    except Exception as e:
        handle_error(e, "Writing .env file", suggest_action="Check file permissions")
        return False


def update_json_config(data_to_save: dict):
    """Reads existing config.json, updates it, and writes back."""
    current_config = {}

    if os.path.exists(JSON_CONFIG_FILE):
        try:
            with open(JSON_CONFIG_FILE, "r") as f:
                current_config = json.load(f)
        except json.JSONDecodeError:
            warning(f"{JSON_CONFIG_FILE} contains invalid JSON - will be overwritten")
        except Exception as e:
            handle_error(e, f"Reading {JSON_CONFIG_FILE}")
            return False

    # Update with new data
    for key, value in data_to_save.items():
        if value is not None:
            current_config[key] = value
        elif key in current_config:
            del current_config[key]

    try:
        with open(JSON_CONFIG_FILE, "w") as f:
            json.dump(current_config, f, indent=4)

        success(f"Configuration updated in {JSON_CONFIG_FILE}")
        return True
    except Exception as e:
        handle_error(e, f"Writing {JSON_CONFIG_FILE}", suggest_action="Check file permissions")
        return False


def display_current_config():
    """Display current configuration from .env file with proper formatting."""
    current_env_settings = {}

    if not os.path.exists(ENV_FILE):
        warning("No .env file found")
        with indent_context():
            tip("Use --config-db or --config-gemini to create initial configuration")
        return

    try:
        with open(ENV_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    if key.strip() in ["DATABASE_URL", "GEMINI_API_KEY", "GEMINI_MODEL_NAME"]:
                        current_env_settings[key.strip()] = value.strip()
    except Exception as e:
        handle_error(e, "Reading configuration", suggest_action="Check .env file format")
        return

    if not current_env_settings:
        warning("No TeshQ configuration found in .env file")
        return

    # Format configuration for display
    display_config = {}
    for key, value in current_env_settings.items():
        if key == "DATABASE_URL" and value:
            try:
                url_obj = make_url(value)
                display_config[key] = str(url_obj._replace(password="********")) if url_obj.password else value
            except Exception:
                display_config[key] = "configured (unable to parse)"
        elif key == "GEMINI_API_KEY" and value:
            display_config[key] = f"{'*' * min(len(value), 20)}..." if len(value) > 20 else "*" * len(value)
        else:
            display_config[key] = value

    print_config(display_config, "Current Configuration", mask_keys=["GEMINI_API_KEY"])


def configure_database_interactive():
    """Interactive database configuration with improved UX."""
    info("Setting up database connection...")
    space()

    # Database type selection
    db_type = prompt("Database type", choices=SUPPORTED_DBS, default="postgresql").lower()

    if db_type == "sqlite":
        db_name = prompt("SQLite database file path", default="sqlite.db")
        return f"sqlite:///{db_name}"

    # Non-SQLite databases
    info(f"Configuring {db_type.upper()} connection...")

    db_user = prompt("Database username")

    # Password with confirmation for new setups
    while True:
        db_password = getpass("Database password: ")
        if not db_password:
            if not confirm("Empty password - is this correct?"):
                continue
        break

    db_host = prompt("Database host", default="localhost")

    default_port = 5432 if db_type == "postgresql" else 3306
    db_port = prompt("Database port", default=default_port, expected_type=int, validate=lambda p: 1 <= p <= 65535)

    db_name = prompt("Database name")

    # Construct URL
    safe_password = quote_plus(db_password)
    db_url = f"{db_type}://{db_user}:{safe_password}@{db_host}:{db_port}/{db_name}"

    # Display masked URL for confirmation
    try:
        url_obj = make_url(db_url)
        masked_url = str(url_obj._replace(password="********")) if url_obj.password else db_url
        info(f"Database URL: {masked_url}")
    except Exception:
        info("Database URL configured successfully")

    return db_url


def configure_gemini_interactive():
    """Interactive Gemini API configuration."""
    info("Setting up Gemini API configuration...")
    space()

    # API Key
    api_key = None
    while True:
        temp_key = getpass("Gemini API Key (press Enter to skip): ")
        if temp_key:
            api_key = temp_key
            break
        elif confirm("Skip Gemini API configuration?", default=True):
            break
        else:
            warning("API key is required for Gemini functionality")

    # Model selection
    model_name = prompt("Gemini model name", default=DEFAULT_GEMINI_MODEL)

    return api_key, model_name


@app.command()
def config(
    # Database options
    db_url: str = typer.Option(None, "--db-url", help="Full database URL (e.g. postgresql://user:pass@host:port/dbname)"),
    db_type_opt: str = typer.Option(
        None, "--db-type", help=f"Database type ({', '.join(SUPPORTED_DBS)})", case_sensitive=False
    ),
    db_user_opt: str = typer.Option(None, "--db-user", help="Database username"),
    db_password_opt: str = typer.Option(
        None, "--db-password", help="Database password (prompts if not set in interactive mode)"
    ),
    db_host_opt: str = typer.Option(None, "--db-host", help="Database host"),
    db_port_opt: int = typer.Option(None, "--db-port", help="Database port"),
    db_name_opt: str = typer.Option(None, "--db-name", help="Database name"),
    # Gemini options
    gemini_api_key_opt: str = typer.Option(None, "--gemini-api-key", help="Google Gemini API Key"),
    gemini_model_name_opt: str = typer.Option(
        DEFAULT_GEMINI_MODEL, "--gemini-model", help="Gemini model to use", show_default=True
    ),
    # Control flags
    save: bool = typer.Option(True, "--save/--no-save", help="Save configuration to files"),
    force_configure_db: bool = typer.Option(False, "--config-db", "-db", help="Interactive database configuration"),
    force_configure_gemini: bool = typer.Option(
        False, "--config-gemini", "-gemini", help="Interactive Gemini API configuration"
    ),
):
    """
    Configure TeshQ database and Gemini API settings.

    Use command-line options for non-interactive setup, or use --config-db/--config-gemini
    for guided interactive configuration.
    """

    # Initialize UI
    clear_screen()
    print_header("🔧 TeshQ Configuration", "Database & AI API Setup")

    final_db_url_to_save = None
    actual_gemini_api_key_to_save = gemini_api_key_opt
    actual_gemini_model_to_save = gemini_model_name_opt

    # Check what options were provided
    db_options_provided = any([db_url, db_type_opt, db_user_opt, db_password_opt, db_host_opt, db_port_opt, db_name_opt])
    gemini_options_provided = gemini_api_key_opt is not None or gemini_model_name_opt != DEFAULT_GEMINI_MODEL

    action_taken = False

    # Database Configuration
    if db_url:
        with section("Database Configuration"):
            info("Using provided database URL")
            final_db_url_to_save = db_url
            action_taken = True

    elif force_configure_db:
        with section("Database Configuration"):
            try:
                final_db_url_to_save = configure_database_interactive()
                action_taken = True
            except KeyboardInterrupt:
                warning("Database configuration cancelled")

    elif db_options_provided:
        with section("Database Configuration"):
            info("Building database URL from provided options...")

            # Validate required options
            if not db_type_opt:
                error("--db-type is required when using individual database options")
                raise typer.Exit(1)

            db_type = db_type_opt.lower()
            if db_type not in SUPPORTED_DBS:
                error(f"Unsupported database type: {db_type}")
                with indent_context():
                    info(f"Supported types: {', '.join(SUPPORTED_DBS)}")
                raise typer.Exit(1)

            if db_type == "sqlite":
                if not db_name_opt:
                    error("--db-name is required for SQLite")
                    raise typer.Exit(1)
                final_db_url_to_save = f"sqlite:///{db_name_opt}"
            else:
                # Validate required options for non-SQLite
                required_opts = [db_user_opt, db_host_opt, db_name_opt]
                if not all(required_opts):
                    error("--db-user, --db-host, and --db-name are required for non-SQLite databases")
                    raise typer.Exit(1)

                # Get password if not provided
                password = db_password_opt
                if not password:
                    password = getpass("Database password: ")

                # Use defaults for optional values
                host = db_host_opt or "localhost"
                port = db_port_opt or (5432 if db_type == "postgresql" else 3306)

                safe_password = quote_plus(password)
                final_db_url_to_save = f"{db_type}://{db_user_opt}:{safe_password}@{host}:{port}/{db_name_opt}"

            success("Database URL constructed successfully")
            action_taken = True

    # Gemini Configuration
    if force_configure_gemini:
        with section("Gemini API Configuration"):
            try:
                api_key, model_name = configure_gemini_interactive()
                actual_gemini_api_key_to_save = api_key
                actual_gemini_model_to_save = model_name
                action_taken = True
            except KeyboardInterrupt:
                warning("Gemini configuration cancelled")

    elif gemini_options_provided:
        with section("Gemini API Configuration"):
            if actual_gemini_api_key_to_save:
                success("Gemini API key provided")
            info(f"Using model: {actual_gemini_model_to_save}")
            action_taken = True

    # Display current config if no actions taken
    if not action_taken:
        with section("Current Configuration"):
            display_current_config()
            space()
            tip("Use --config-db or --config-gemini for interactive setup")
            tip("Use command-line options for automated configuration")
        raise typer.Exit()

    # Save configuration
    if save:
        with section("Saving Configuration"):
            configs_to_write_env = {}
            configs_to_write_json = {}

            # Prepare database config
            if final_db_url_to_save:
                configs_to_write_env["DATABASE_URL"] = final_db_url_to_save
                configs_to_write_json["DATABASE_URL"] = final_db_url_to_save

            # Prepare Gemini config
            if force_configure_gemini or gemini_options_provided:
                if actual_gemini_api_key_to_save:
                    configs_to_write_env["GEMINI_API_KEY"] = actual_gemini_api_key_to_save
                    configs_to_write_json["GEMINI_API_KEY_CONFIGURED"] = True
                else:
                    configs_to_write_env["GEMINI_API_KEY"] = None
                    configs_to_write_json["GEMINI_API_KEY_CONFIGURED"] = False

                configs_to_write_env["GEMINI_MODEL_NAME"] = actual_gemini_model_to_save
                configs_to_write_json["GEMINI_MODEL_NAME"] = actual_gemini_model_to_save

            # Save files
            env_success = update_env_file(configs_to_write_env)
            json_success = update_json_config(configs_to_write_json)

            if env_success and json_success:
                print_divider("Configuration Complete")
                success("🎉 All configuration saved successfully!")
                with indent_context():
                    tip("Run your TeshQ commands to start using the configured settings")
            else:
                error("Some configuration files could not be saved")
                raise typer.Exit(1)
    else:
        with section("Configuration Preview"):
            warning("Configuration not saved (--no-save specified)")
            if final_db_url_to_save:
                info("Database URL would be saved")
            if actual_gemini_api_key_to_save:
                info("Gemini API configuration would be saved")


if __name__ == "__main__":
    app()
