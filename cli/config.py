import json
from getpass import getpass
from urllib.parse import quote_plus

import typer

app = typer.Typer()
SUPPORTED_DBS = ["postgresql", "mysql", "sqlite"]


def save_to_env_file(db_url: str):
    with open(".env", "w") as f:
        f.write(f"DATABASE_URL={db_url}\n")
    typer.echo("✅ Configuration saved to `.env`")


def save_to_json_config(config: dict):
    with open("config.json", "w") as f:
        json.dump(config, f, indent=4)
    typer.echo("✅ Configuration saved to `config.json`")


@app.command()
def config(
    db_url: str = typer.Option(
        None,
        "--db-url",
        help="Full database URL (e.g. postgresql://user:pass@host:port/dbname)",
    ),
    db_type: str = typer.Option(
        None, "--db-type", help=f"Database type ({', '.join(SUPPORTED_DBS)})"
    ),
    db_user: str = typer.Option(None, "--db-user", help="Database username"),
    db_password: str = typer.Option(None, "--db-password", help="Database password"),
    db_host: str = typer.Option(
        None, "--db-host", help="Database host (e.g. localhost or IP)"
    ),
    db_port: int = typer.Option(
        None,
        "--db-port",
        help="Database port (e.g. 5432 for PostgreSQL, 3306 for MySQL)",
    ),
    db_name: str = typer.Option(None, "--db-name", help="Database name"),
    save: bool = typer.Option(
        True,
        "--save/--no-save",
        help="Save the config to a file (.env and config.json)",
    ),
):
    if db_url:
        typer.echo(f"🔗 Using provided DB URL:\n{db_url}")
        final_url = db_url
    else:
        if not db_type:
            db_type = typer.prompt(
                f"Enter database type ({', '.join(SUPPORTED_DBS)})", type=str
            ).lower()
        while db_type not in SUPPORTED_DBS:
            db_type = typer.prompt(
                f"❌ Invalid type. Choose from: {', '.join(SUPPORTED_DBS)}"
            ).lower()

        if db_type == "sqlite":
            db_name = db_name or typer.prompt(
                "Enter SQLite DB file path", default="sqlite.db"
            )
            final_url = f"sqlite:///{db_name}"
        else:
            db_user = db_user or typer.prompt("Enter database username")
            db_password = db_password or getpass("Enter database password: ")
            db_host = db_host or typer.prompt(
                "Enter database host", default="localhost"
            )
            db_port = db_port or int(
                typer.prompt(
                    "Enter database port",
                    default="5432" if db_type == "postgresql" else "3306",
                )
            )
            db_name = db_name or typer.prompt("Enter database name")
            safe_password = quote_plus(db_password)
            final_url = (
                f"{db_type}://{db_user}:{safe_password}@{db_host}:{db_port}/{db_name}"
            )

        masked_url = (
            final_url.replace(safe_password, "*" * len(db_password))
            if db_type != "sqlite"
            else final_url
        )
        typer.echo(f"🔧 Constructed DB URL:\n{masked_url}")

    if save:
        save_to_env_file(final_url)
        save_to_json_config({"DATABASE_URL": final_url})


if __name__ == "__main__":
    app()
