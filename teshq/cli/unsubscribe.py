"""
TESHQ Unsubscribe Command
Allows users to unsubscribe from TESHQ updates via CLI.

Production-grade features:
- Interactive and non-interactive modes
- Pydantic email validation
- Comprehensive error handling
- Clean UX with Rich formatting
- Configuration cleanup on success
- Keyboard interrupt handling
"""

from typing import Optional

import typer
from pydantic import ValidationError

from teshq.config.loader import get_config, save_config
from teshq.subscriptions.client import (
    SubscriberClient,
    UnsubscribeRequest,
    UnsubscribeResult,
    UnsubscribeStatus,
)
from teshq.utils.ui import (
    confirm,
    error,
    handle_error,
    info,
    print_header,
    print_markdown,
    prompt,
    space,
    status as ui_status,
    success,
    tip,
    warning,
)

try:
    from importlib.metadata import PackageNotFoundError, version

    try:
        __version__ = version("teshq")
    except PackageNotFoundError:
        __version__ = "1.0.0"
except ImportError:
    __version__ = "1.0.0"


app = typer.Typer(
    name="unsubscribe",
    help="Unsubscribe from TESHQ updates and announcements.",
    invoke_without_command=True,
)


def display_welcome():
    """Display welcome message and information about unsubscribing"""
    space()
    print_header(
        "Unsubscribe from TESHQ Updates",
        "We're sorry to see you go"
    )
    space()

    info_text = """
You are about to unsubscribe from:

✉️  Product updates and announcements
🔧  Important bug fix notifications
📚  Tips and best practices
🚀  Early access opportunities

You can always re-subscribe later using `teshq subscribe`.
    """

    print_markdown(info_text)
    space()


def get_validated_email() -> str:
    """Get and validate email with Pydantic"""
    while True:
        email = prompt("Enter your email address")
        try:
            UnsubscribeRequest(email=email, cli_version=__version__)
            return email.strip().lower()
        except ValidationError as e:
            errors = e.errors()
            email_errors = [err for err in errors if "email" in str(err.get("loc", []))]
            if email_errors:
                warning(f"{email_errors[0]['msg']}")
            else:
                warning("Please enter a valid email address")


def get_email_from_config() -> Optional[str]:
    """Try to get email from saved configuration"""
    try:
        config = get_config()
        return config.get("SUBSCRIBER_EMAIL")
    except Exception:
        return None


def display_confirmation(email: str) -> bool:
    """Display confirmation dialog"""
    space()
    info(f"Email: {email}")
    space()
    return confirm("Proceed with unsubscription?", default=True)


def handle_unsubscribe_result(result: UnsubscribeResult, email: str) -> int:
    """Handle and display unsubscription result."""
    space()
    if result.status == UnsubscribeStatus.SUCCESS:
        success("👋 Successfully unsubscribed from TESHQ updates.")
        space()
        info("You will no longer receive:", dim=True)
        info("  • Product updates and announcements", indent=1)
        info("  • Bug fix notifications", indent=1)
        info("  • Tips and best practices", indent=1)
        space()
        tip("You can re-subscribe anytime using: teshq subscribe")
        space()
        info("We're sorry to see you go. Thanks for using TESHQ!", dim=True)

        # Clean up saved subscription config
        try:
            save_config({"SUBSCRIBER_EMAIL": None, "SUBSCRIBER_ID": None})
        except Exception:
            pass  # Config cleanup is non-critical

        return 0

    elif result.status == UnsubscribeStatus.ALREADY_UNSUBSCRIBED:
        info("You are already unsubscribed from our updates.")
        space()
        tip("Want to re-subscribe? Use: teshq subscribe")
        return 0

    elif result.status == UnsubscribeStatus.EMAIL_NOT_FOUND:
        error("Email address not found in our subscription list.")
        space()
        info("This email may not be subscribed, or it was already removed.", dim=True)
        tip("To check your subscription status, try: teshq subscribe")
        return 1

    elif result.status == UnsubscribeStatus.INVALID_INPUT:
        error(result.message)
        if result.details:
            space()
            warning("Validation Details:")
            for key, value in result.details.items():
                info(f"  • {key}: {value}", indent=1)
        return 1

    elif result.status == UnsubscribeStatus.RATE_LIMITED:
        warning(f"⏳ {result.message}")
        space()
        info("This is a temporary rate limit to prevent abuse.", dim=True)
        tip("Please try again later")
        return 1

    elif result.status == UnsubscribeStatus.SERVICE_UNAVAILABLE:
        error(f"🔧 {result.message}")
        space()
        tip("Please try again later")
        return 1

    elif result.status == UnsubscribeStatus.CLIENT_ERROR:
        error(f"🌐 {result.message}")
        space()
        tip("Check your internet connection and try again")
        return 1

    else:
        error(result.message)
        space()
        tip("If this issue persists, please report it at:\nhttps://github.com/theshashank1/TESH-Query/issues")
        return 1


@app.callback(invoke_without_command=True)
def unsubscribe(
    ctx: typer.Context,
    email: Optional[str] = typer.Option(
        None, "--email", "-e", help="Your email address to unsubscribe"
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip confirmation prompts"
    ),
):
    """
    Unsubscribe from TESHQ updates and announcements.

    Examples:

        # Interactive mode (recommended)
        $ teshq unsubscribe

        # Non-interactive mode
        $ teshq unsubscribe --email "shashank@example.com" -y
    """
    if ctx.invoked_subcommand is not None:
        return

    exit_code = 1
    try:
        if not email:
            display_welcome()

        # Try to get email from config if not provided
        if not email:
            saved_email = get_email_from_config()
            if saved_email:
                space()
                if confirm(f"Use saved email '{saved_email}'?", default=True):
                    email = saved_email
                else:
                    email = get_validated_email()
            else:
                email = get_validated_email()

        if not email:
            error("Email is required")
            raise typer.Exit(code=1)

        if not yes:
            if not display_confirmation(email):
                raise typer.Abort()

        space()
        with ui_status("Processing unsubscription request", "Unsubscription processed"):
            with SubscriberClient(cli_version=__version__) as client:
                result = client.unsubscribe(email=email)

        exit_code = handle_unsubscribe_result(result, email)

    except typer.Abort:
        space()
        warning("Unsubscription cancelled by user")
        exit_code = 0
    except KeyboardInterrupt:
        space()
        warning("Unsubscription interrupted by user")
        exit_code = 130
    except Exception as e:
        space()
        handle_error(
            e,
            "Unsubscription",
            suggest_action="Check your internet connection and try again",
        )
        exit_code = 1
    finally:
        space()
        raise typer.Exit(code=exit_code)


if __name__ == "__main__":
    app()
