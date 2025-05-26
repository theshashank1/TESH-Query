import json
import os
from getpass import getpass
from urllib.parse import quote_plus

import typer
from sqlalchemy.engine.url import make_url  # For safe display of DB URL

app = typer.Typer()
SUPPORTED_DBS = ["postgresql", "mysql", "sqlite"]
ENV_FILE = ".env"
JSON_CONFIG_FILE = "config.json"
DEFAULT_GEMINI_MODEL = "gemini-1.5-flash-latest"


def update_env_file(data_to_save: dict):
    """Reads existing .env, updates it with new data, and writes back."""
    env_vars = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
                # else: malformed line, skip or log

    # Update with new data, potentially overwriting existing keys
    for key, value in data_to_save.items():
        if value is not None:  # Only save/update if a value is provided
            env_vars[key] = str(value)
        elif key in env_vars:  # If new value is None, remove existing key
            del env_vars[key]

    with open(ENV_FILE, "w") as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")
    typer.echo(f"✅ Configuration updated in `{ENV_FILE}`")
    typer.secho(
        "🔒 Your configuration is saved locally on your system to ensure your data remains secure. ",
        fg=typer.colors.YELLOW,
    )


def update_json_config(data_to_save: dict):
    """Reads existing config.json, updates it, and writes back."""
    current_config = {}
    if os.path.exists(JSON_CONFIG_FILE):
        try:
            with open(JSON_CONFIG_FILE, "r") as f:
                current_config = json.load(f)
        except json.JSONDecodeError:
            typer.echo(f"⚠️ Warning: `{JSON_CONFIG_FILE}` was corrupted or not valid JSON and will be overwritten.")
        except FileNotFoundError:  # Should be caught by os.path.exists typically
            pass

    # Update with new data, potentially overwriting existing keys
    for key, value in data_to_save.items():
        if value is not None:
            current_config[key] = value
        elif key in current_config:  # If new value is None, remove key
            del current_config[key]

    with open(JSON_CONFIG_FILE, "w") as f:
        json.dump(current_config, f, indent=4)
    typer.echo(f"✅ Configuration updated in `{JSON_CONFIG_FILE}`")
    typer.secho(
        "🔒 Your configuration is saved locally on your system to ensure your data remains secure. ",
        fg=typer.colors.YELLOW,
    )


@app.command()
def config(
    # Database options
    db_url: str = typer.Option(
        None, "--db-url", help="Full database URL (e.g. postgresql://user:pass@host:port/dbname)", show_default=False
    ),
    db_type_opt: str = typer.Option(
        None, "--db-type", help=f"Database type ({', '.join(SUPPORTED_DBS)})", show_default=False, case_sensitive=False
    ),
    db_user_opt: str = typer.Option(None, "--db-user", help="Database username", show_default=False),
    db_password_opt: str = typer.Option(
        None, "--db-password", help="Database password (prompts if not set in interactive mode)", show_default=False
    ),
    db_host_opt: str = typer.Option(None, "--db-host", help="Database host (e.g. localhost or IP)", show_default=False),
    db_port_opt: int = typer.Option(
        None, "--db-port", help="Database port (e.g. 5432 for PostgreSQL, 3306 for MySQL)", show_default=False
    ),
    db_name_opt: str = typer.Option(None, "--db-name", help="Database name", show_default=False),
    # Gemini options
    gemini_api_key_opt: str = typer.Option(None, "--gemini-api-key", help="Your Google Gemini API Key", show_default=False),
    gemini_model_name_opt: str = typer.Option(
        DEFAULT_GEMINI_MODEL,
        "--gemini-model",
        # Default value set here, shows default in help message
        help="Name of the Gemini model to use",
        show_default=True,  # Shows default in help message
    ),
    # Control flags
    save: bool = typer.Option(True, "--save/--no-save", help="Save the config to .env and config.json files"),
    force_configure_db: bool = typer.Option(
        False, "--config-db", help="Interactively configure database settings, even if some options are provided."
    ),
    force_configure_gemini: bool = typer.Option(
        False, "--config-gemini", help="Interactively configure Gemini API settings, even if some options are provided."
    ),
):
    """
    Configures database connection and/or Gemini API settings.
    Provide settings via options (e.g., --db-url, --gemini-api-key).
    Use --configure-db or --configure-gemini for guided interactive prompts.
    If no options are given, current settings from .env will be displayed.
    """
    final_db_url_to_save = None
    actual_gemini_api_key_to_save = gemini_api_key_opt  # Start with option value
    actual_gemini_model_to_save = gemini_model_name_opt  # Start with option value (which has default)

    # Determine if any specific config option was passed or interactive mode forced
    db_options_provided = any(
        opt is not None for opt in [db_url, db_type_opt, db_user_opt, db_password_opt, db_host_opt, db_port_opt, db_name_opt]
    )
    gemini_options_provided = (
        any(opt is not None for opt in [gemini_api_key_opt]) or gemini_model_name_opt != DEFAULT_GEMINI_MODEL
    )

    # --- Database Configuration ---
    if db_url:
        typer.echo("🔗 Using provided DB URL.")
        final_db_url_to_save = db_url
    elif force_configure_db or db_options_provided:
        typer.echo("--- Database Configuration ---")
        current_db_type = db_type_opt
        if not current_db_type or force_configure_db:  # Prompt if not given or forcing
            current_db_type = typer.prompt(
                f"Database type ({', '.join(SUPPORTED_DBS)})", default=current_db_type or "", type=str
            ).lower()
        while current_db_type not in SUPPORTED_DBS:
            typer.echo(f"❌ Invalid DB type '{current_db_type}'.")
            current_db_type = typer.prompt(f"Choose from: {', '.join(SUPPORTED_DBS)}").lower()

        if current_db_type == "sqlite":
            current_db_name = db_name_opt
            if not current_db_name or force_configure_db:
                current_db_name = typer.prompt("SQLite DB file path", default=current_db_name or "sqlite.db")
            final_db_url_to_save = f"sqlite:///{current_db_name}"
        else:
            current_db_user = db_user_opt
            if not current_db_user or force_configure_db:
                current_db_user = typer.prompt("Database username", default=current_db_user or "")

            current_db_password = db_password_opt  # Use option if provided
            if current_db_password is None or (
                force_configure_db and typer.confirm("Re-enter DB password?", default=not bool(current_db_password))
            ):
                current_db_password = getpass("Database password: ")

            current_db_host = db_host_opt
            if not current_db_host or force_configure_db:
                current_db_host = typer.prompt("Database host", default=current_db_host or "localhost")

            default_port_val = 5432 if current_db_type == "postgresql" else 3306
            current_db_port = db_port_opt
            if not current_db_port or force_configure_db:
                current_db_port = typer.prompt("Database port", default=current_db_port or default_port_val, type=int)

            current_db_name = db_name_opt
            if not current_db_name or force_configure_db:
                current_db_name = typer.prompt("Database name", default=current_db_name or "")

            safe_password = quote_plus(current_db_password)
            final_db_url_to_save = f"{current_db_type}://{current_db_user}:{safe_password}@{current_db_host}:{current_db_port}/{current_db_name}"  # noqa: E501

        if final_db_url_to_save:
            try:
                url_obj = make_url(final_db_url_to_save)
                masked_url = str(url_obj._replace(password="********")) if url_obj.password else final_db_url_to_save
                typer.echo(f"🔧 Constructed DB URL: {masked_url}")
            except Exception:
                typer.echo(
                    "🔧 Constructed DB URL (unable to fully mask): "
                    f"{final_db_url_to_save[:final_db_url_to_save.find('://')+3]}"
                    "********"
                )

    # --- Gemini API Configuration ---
    if force_configure_gemini or gemini_options_provided:
        typer.echo("--- Gemini API Configuration ---")
        if force_configure_gemini or gemini_api_key_opt is None:  # Prompt if forcing or not given by option
            if (
                actual_gemini_api_key_to_save
                and force_configure_gemini
                and not typer.confirm("API key is already set/provided. Re-enter?", default=False)
            ):
                pass  # Keep existing actual_gemini_api_key_to_save
            else:
                prompt_message = "Gemini API Key"
                if not actual_gemini_api_key_to_save and not force_configure_gemini:  # First time, no option, no force
                    prompt_message += " (optional, press Enter to skip)"

                temp_key = typer.prompt(prompt_message, default="", hide_input=True, show_default=False)
                if temp_key:  # Only update if user entered something
                    actual_gemini_api_key_to_save = temp_key
                elif not temp_key and not actual_gemini_api_key_to_save:  # User pressed Enter and no key was previously set
                    actual_gemini_api_key_to_save = None

        if force_configure_gemini:  # Always offer to change model if forcing interactive
            if typer.confirm(f"Current Gemini model is '{actual_gemini_model_to_save}'. Change it?", default=False):
                actual_gemini_model_to_save = typer.prompt("Gemini Model Name", default=actual_gemini_model_to_save)

        if actual_gemini_api_key_to_save:
            typer.echo(f"🔑 Gemini API Key: {'Provided (will be saved to .env)'}")
        else:
            typer.echo("🔑 Gemini API Key: Not set/provided.")
        typer.echo(f"🤖 Gemini Model: {actual_gemini_model_to_save}")

    # --- Save or Display Current Config ---
    configs_to_write_env = {}
    configs_to_write_json = {}

    action_taken = False

    if final_db_url_to_save is not None:
        configs_to_write_env["DATABASE_URL"] = final_db_url_to_save  # Save to env for dotenv loading

        configs_to_write_json["DATABASE_URL"] = final_db_url_to_save  # Store real URL for programmatic access
        action_taken = True

    # Always try to save model name if it was configured or is default
    # Save API key only if it's set
    if gemini_options_provided or force_configure_gemini:
        action_taken = True  # Action was taken if we entered this block
        if actual_gemini_api_key_to_save:
            configs_to_write_env["GEMINI_API_KEY"] = actual_gemini_api_key_to_save
            configs_to_write_json["GEMINI_API_KEY_CONFIGURED"] = True
        else:  # Ensure API key is removed if set to None
            configs_to_write_env["GEMINI_API_KEY"] = None  # Will remove key in update_env_file
            configs_to_write_json["GEMINI_API_KEY_CONFIGURED"] = False

        configs_to_write_env["GEMINI_MODEL_NAME"] = actual_gemini_model_to_save
        configs_to_write_json["GEMINI_MODEL_NAME"] = actual_gemini_model_to_save

    if not action_taken:
        typer.echo("No new configuration options provided. Displaying current settings from .env (if any).")
        typer.echo("Use options or --configure-db/--configure-gemini to set values.")
        current_env_settings = {}  # type: ignore
        if os.path.exists(ENV_FILE):
            with open(ENV_FILE, "r") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        key, value = line.split("=", 1)
                        if key in ["DATABASE_URL", "GEMINI_API_KEY", "GEMINI_MODEL_NAME"]:
                            current_env_settings[key.strip()] = value.strip()
        if not current_env_settings:
            typer.echo("  No relevant configuration found in .env file.")
        else:
            typer.echo(
                "\nCurrent configuration from .env file:\n"
                "  (Note: This shows values from .env, not necessarily what was just passed as options)"
            )

            for key, value in current_env_settings.items():
                if key == "DATABASE_URL":
                    try:
                        url_obj = make_url(value)
                        typer.echo(f"  {key}: {str(url_obj._replace(password='********')) if url_obj.password else value}")
                    except Exception:
                        typer.echo(f"  {key}: (masked, unable to fully parse)")
                elif key == "GEMINI_API_KEY":
                    typer.echo(f"  {key}: {'*' * (len(value) if len(value) < 10 else 10) if value else 'Not set'}")
                else:
                    typer.echo(f"  {key}: {value}")
        raise typer.Exit()

    if save:
        if not configs_to_write_env and not configs_to_write_json:  # Check if any actual values are set to be written
            # Check if any of the dictionaries being passed actually have values set
            # (could be empty if no options were provided for that section)
            no_actual_values_to_save = True
            for val_list in [configs_to_write_env.values(), configs_to_write_json.values()]:
                if any(v is not None for v in val_list):
                    no_actual_values_to_save = False
                    break
            if no_actual_values_to_save:
                typer.echo("No new values to save.")
                raise typer.Exit()

        update_env_file(configs_to_write_env)
        update_json_config(configs_to_write_json)
    else:
        typer.echo("Configuration not saved as --no-save was specified.")


if __name__ == "__main__":
    app()
