"""
TESHQ Subscribe Command
Allows users to subscribe to updates via CLI using ModernUI
"""

from typing import Optional

import typer
from pydantic import ValidationError

from teshq.utils.config import get_config, save_config
from teshq.utils.subscription_client import SubscriberClient, SubscriptionRequest, SubscriptionStatus
from teshq.utils.ui import confirm, error, handle_error, info, print_header, print_markdown, prompt, space
from teshq.utils.ui import status as ui_status
from teshq.utils.ui import success, tip, warning

try:
    from importlib.metadata import PackageNotFoundError, version

    try:
        __version__ = version("teshq")
    except PackageNotFoundError:
        __version__ = "1.0.0"
except ImportError:
    __version__ = "1.0.0"


app = typer.Typer(name="subscribe", help="Subscribe to TESHQ updates and announcements.", invoke_without_command=True)


def display_welcome():
    """Display welcome message and benefits"""
    space()
    print_header("Subscribe to TESHQ Updates", "Stay informed about new features and improvements")
    space()

    benefits = """
By subscribing, you'll receive:

✨ **New feature announcements**
🐛 **Important bug fixes and updates**
📚 **Tips and best practices**
🚀 **Early access to beta features**

We respect your privacy and will never spam you or share your email.
You can unsubscribe at any time.
    """

    print_markdown(benefits)
    space()


def get_validated_name() -> str:
    """Get and validate user name"""
    while True:
        name = prompt("Enter your name", default="")
        if len(name.strip()) >= 2:
            return name.strip()
        warning("Name must be at least 2 characters long")


def get_validated_email() -> str:
    """Get and validate email with Pydantic"""
    while True:
        email = prompt("Enter your email", default="")
        try:
            SubscriptionRequest(name="Test User", email=email, cli_version=__version__)
            return email.strip()
        except ValidationError as e:
            errors = e.errors()
            email_errors = [err for err in errors if "email" in str(err.get("loc", []))]
            if email_errors:
                warning(f"{email_errors[0]['msg']}")
            else:
                warning("Please enter a valid email address")


def display_confirmation(name: str, email: str) -> bool:
    """Display confirmation dialog"""
    space()
    info(f"Name:  {name}")
    info(f"Email: {email}")
    info(f"CLI Version: {__version__}")
    space()
    return confirm("Proceed with subscription?", default=True)


def handle_subscription_result(result, email: str) -> int:
    """Handle and display subscription result."""
    space()
    if result.status == SubscriptionStatus.SUCCESS:
        success("🎉 Subscription successful! Welcome to TESHQ.")
        if result.subscriber_id:
            info(f"Subscriber ID: {result.subscriber_id}", dim=True)
            config = get_config()
            config["SUBSCRIBER_EMAIL"] = email
            config["SUBSCRIBER_ID"] = result.subscriber_id
            save_config(config)
        space()
        tip("Check your email for a confirmation message")
        return 0
    elif result.status == SubscriptionStatus.RESUBSCRIBED:
        success("🎉 Welcome back! You have been re-subscribed.")
        if result.subscriber_id:
            info(f"Subscriber ID: {result.subscriber_id}", dim=True)
            config = get_config()
            config["SUBSCRIBER_EMAIL"] = email
            config["SUBSCRIBER_ID"] = result.subscriber_id
            save_config(config)
        return 0
    elif result.status == SubscriptionStatus.ALREADY_SUBSCRIBED:
        info("You are already subscribed. Thank you!")
        if result.subscriber_id:
            info(f"Subscriber ID: {result.subscriber_id}", dim=True)
        return 0
    elif result.status == SubscriptionStatus.DISPOSABLE_EMAIL:
        error(result.message)
        space()
        warning("Please use a permanent email address such as:")
        info("  • Gmail, Outlook, Yahoo", indent=1)
        info("  • Your work or school email", indent=1)
        info("  • Your personal domain", indent=1)
        return 1
    elif result.status == SubscriptionStatus.INVALID_INPUT:
        error(result.message)
        if result.details:
            space()
            warning("Validation Details:")
            for key, value in result.details.items():
                info(f"  • {key}: {value}", indent=1)
        return 1
    elif result.status == SubscriptionStatus.RATE_LIMITED:
        warning(f"⏳ {result.message}")
        space()
        info("This is a temporary limit to prevent abuse.", dim=True)
        tip("Please try again in an hour")
        return 1
    elif result.status == SubscriptionStatus.PERMANENTLY_DELETED:
        error(f"🚫 {result.message}")
        space()
        info("This email address cannot be used for subscriptions.", dim=True)
        return 1
    elif result.status == SubscriptionStatus.CLIENT_ERROR:
        error(f"🌐 {result.message}")
        space()
        tip("Check your internet connection and try again")
        return 1
    else:
        error(result.message)
        space()
        tip("If this issue persists, please report it at:\nhttps://github.com/theshashank1/TESH-Query/issues")
        return 1


@app.callback()
def subscribe(
    ctx: typer.Context,
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Your full name (2-100 characters)"),
    email: Optional[str] = typer.Option(None, "--email", "-e", help="Your email address"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompts"),
):
    """
    Subscribe to TESHQ updates and announcements.

    Examples:
        
        # Interactive mode (recommended)
        $ teshq subscribe
        
        # With arguments
        $ teshq subscribe --name "Shashank Kumar" --email "shashank@example.com"
        
        # Skip confirmation
        $ teshq subscribe -n "John Doe" -e "john@example.com" -y
    """
    exit_code = 1  # Default to error
    try:
        if not (name and email):
            display_welcome()

        if not name:
            name = get_validated_name()

        if not email:
            email = get_validated_email()

        if not yes:
            if not display_confirmation(name, email):
                raise typer.Abort()

        space()
        with ui_status("Submitting subscription", "Subscription submitted successfully"):
            client = SubscriberClient(cli_version=__version__)
            result = client.subscribe(name=name, email=email)

        exit_code = handle_subscription_result(result, email)

    except typer.Abort:
        space()
        warning("Subscription cancelled by user")
        exit_code = 0
    except KeyboardInterrupt:
        space()
        warning("Subscription interrupted by user")
        exit_code = 130
    except Exception as e:
        space()
        handle_error(e, "Subscription", suggest_action="Check your internet connection and try again")
        exit_code = 1
    finally:
        space()
        raise typer.Exit(code=exit_code)


if __name__ == "__main__":
    app()
