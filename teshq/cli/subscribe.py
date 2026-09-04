"""
TESHQ Subscribe Command
Allows users to subscribe to updates via CLI using ModernUI
"""

from typing import Optional

import typer
from pydantic import ValidationError

from teshq.config.loader import get_config, save_config
from teshq.subscriptions.client import SubscriberClient, SubscriptionRequest, SubscriptionStatus, diagnose_connection
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
            # Save only subscriber-specific fields, not full config with secrets
            save_config({
                "SUBSCRIBER_EMAIL": email,
                "SUBSCRIBER_ID": result.subscriber_id,
            })
        space()
        tip("Check your email for a confirmation message")
        return 0
    elif result.status == SubscriptionStatus.RESUBSCRIBED:
        success("🎉 Welcome back! You have been re-subscribed.")
        if result.subscriber_id:
            info(f"Subscriber ID: {result.subscriber_id}", dim=True)
            # Save only subscriber-specific fields, not full config with secrets
            save_config({
                "SUBSCRIBER_EMAIL": email,
                "SUBSCRIBER_ID": result.subscriber_id,
            })
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
        info("Rate limiting tiers:", dim=True)
        info("  • Per-second: 2 requests max", indent=1)
        info("  • Per-minute: 30 requests max", indent=1)
        info("  • Global: 100 requests/minute", indent=1)
        tip("Please try again in an hour")
        return 1
    elif result.status == SubscriptionStatus.SERVICE_UNAVAILABLE:
        error(f"🔧 {result.message}")
        space()
        info("The subscription service is temporarily disabled.", dim=True)
        tip("Please try again later")
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


@app.command("health")
def check_api_health():
    """
    Check the health of the subscription API.

    Example:
        $ teshq subscribe health
    """
    try:
        space()
        print_header("Subscription API Health Check", "Checking API status...")
        space()

        with ui_status("Checking API health", "Health check completed"):
            client = SubscriberClient(cli_version=__version__)
            result = client.health_check()

        if result.status == SubscriptionStatus.SUCCESS:
            success("✅ Subscription API is healthy and operational")
            if result.details:
                info(f"Status: {result.details.get('health_status', 'ok')}")
            space()
            raise typer.Exit(code=0)
        else:
            error(f"❌ API health check failed: {result.message}")
            raise typer.Exit(code=1)

    except Exception as e:
        handle_error(e, "Health check", suggest_action="Check your internet connection")
        raise typer.Exit(code=1)


@app.command("list")
def list_subscribers(
    limit: int = typer.Option(50, "--limit", "-l", help="Number of subscribers to retrieve"),
    cursor: Optional[str] = typer.Option(None, "--cursor", "-c", help="Cursor for pagination"),
):
    """
    List subscribers (Admin only).

    Requires TESHQ_ADMIN_API_KEY environment variable.

    Example:
        $ teshq subscribe list
        $ teshq subscribe list --limit 100
        $ teshq subscribe list --limit 50 --cursor <cursor_value>
    """
    try:
        space()
        print_header("Subscriber List (Admin)", "Retrieving subscriber data...")
        space()

        with ui_status("Fetching subscribers", "Subscribers retrieved"):
            client = SubscriberClient(cli_version=__version__)
            result = client.get_subscribers(limit=limit, cursor=cursor)

        if result.status == SubscriptionStatus.SUCCESS:
            subscribers = result.details.get("subscribers", {})
            data = subscribers.get("data", [])

            success(f"✅ Retrieved {len(data)} subscribers")
            space()

            if data:
                from rich.table import Table
                from rich.console import Console

                console = Console()
                table = Table(title="Subscribers", show_header=True, header_style="bold magenta")
                table.add_column("ID", style="dim")
                table.add_column("Name")
                table.add_column("Email")
                table.add_column("Created At", style="dim")

                for sub in data:
                    table.add_row(
                        str(sub.get("id") or "N/A")[:12] + "...",
                        sub.get("name", "N/A"),
                        sub.get("email", "N/A"),
                        sub.get("createdAt", "N/A")
                    )

                console.print(table)

                # Show pagination info
                if subscribers.get("nextCursor"):
                    space()
                    info(f"Next cursor: {subscribers['nextCursor']}", dim=True)
                    tip(f"To see more: teshq subscribe list --cursor {subscribers['nextCursor']}")
            else:
                info("No subscribers found", dim=True)
        else:
            if "Admin API key required" in result.message:
                error("❌ Admin authentication required")
                space()
                info("Configure the admin API key using:", dim=True)
                info("  teshq config --admin-api-key", indent=1)
                space()
                info("Or edit config.json and add:", dim=True)
                info('  {"TESHQ_ADMIN_API_KEY": "your_admin_key"}', indent=1)
            else:
                error(f"❌ Failed to retrieve subscribers: {result.message}")
            raise typer.Exit(code=1)

        space()
        raise typer.Exit(code=0)

    except Exception as e:
        handle_error(e, "List subscribers", suggest_action="Check your admin credentials")
        raise typer.Exit(code=1)


@app.command("diagnose")
def diagnose(
    api_url: Optional[str] = typer.Option(None, "--api-url", "-u", help="Custom API URL to test"),
):
    """
    Diagnose connection issues with the subscription API.

    This command runs comprehensive tests to identify why you might be getting
    "Check your internet connection" errors.

    Example:
        $ teshq subscribe diagnose
        $ teshq subscribe diagnose --api-url https://custom-api.example.com
    """
    try:
        space()
        print_header("Subscription API Connection Diagnostics", "Running comprehensive tests...")
        space()

        # Determine API URL to test
        from teshq.config.loader import get_config
        config = get_config()
        env_url = config.get("TESHQ_API_BASE_URL")

        if api_url:
            test_url = api_url
            info(f"Testing custom URL: {test_url}")
        elif env_url:
            test_url = env_url
            info(f"Testing configured URL: {test_url}")
        else:
            test_url = "https://api.teshq.io"
            info(f"Testing default URL: {test_url}")

        space()

        # Run diagnosis
        results = diagnose_connection(api_base_url=test_url)

        space()

        # Provide next steps
        if any("FAIL" in str(v.get("status", "")) for v in results["tests"].values()):
            warning("⚠️  Some tests failed. Here are your options:")
            space()
            info("1. If you have a custom API endpoint, configure it:")
            info("   teshq config --api-url https://your-api.com", indent=1)
            space()
            info("   Or edit config.json and add:")
            info('   {"TESHQ_API_BASE_URL": "https://your-api.com"}', indent=1)
            space()
            info("2. Check if you're behind a corporate proxy:")
            info("   Configure proxy in your shell or network settings", indent=1)
            space()
            info("3. Test with curl:")
            info(f"   curl -v {test_url}/v1/health", indent=1)
            space()
            info("4. Check DNS resolution:")
            info(f"   nslookup {test_url.replace('https://', '').replace('http://', '').split('/')[0]}", indent=1)
            raise typer.Exit(code=1)
        else:
            success("✅ All diagnostics passed! The API should be working.")
            raise typer.Exit(code=0)

    except Exception as e:
        handle_error(e, "Diagnosis", suggest_action="Check your Python installation")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
