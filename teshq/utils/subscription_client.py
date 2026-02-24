"""
TESHQ Subscription API Client
Handles communication with the subscription endpoint using Pydantic for validation
"""

import os
import platform
from enum import Enum
from typing import Optional

import requests
from pydantic import BaseModel, EmailStr, Field, field_validator
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class SubscriptionStatus(str, Enum):
    """Enumeration of possible subscription statuses"""

    SUCCESS = "SUCCESS"
    RESUBSCRIBED = "RESUBSCRIBED"
    ALREADY_SUBSCRIBED = "ALREADY_SUBSCRIBED"
    RATE_LIMITED = "RATE_LIMITED"
    INVALID_INPUT = "INVALID_INPUT"
    DISPOSABLE_EMAIL = "DISPOSABLE_EMAIL"
    PERMANENTLY_DELETED = "PERMANENTLY_DELETED"
    CLIENT_ERROR = "CLIENT_ERROR"
    SERVER_ERROR = "SERVER_ERROR"


class OSType(str, Enum):
    """Supported operating systems"""

    LINUX = "linux"
    DARWIN = "darwin"
    WINDOWS = "windows"


class SubscriptionRequest(BaseModel):
    """Request model for subscription"""

    name: str = Field(..., min_length=2, max_length=100, description="User's full name")
    email: EmailStr = Field(..., description="User's email address")
    cli_version: Optional[str] = Field(None, description="CLI version")
    os_type: Optional[OSType] = Field(None, description="Operating system type")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure name is properly trimmed and not empty"""
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Name must be at least 2 characters long")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Ensure email is lowercase and trimmed"""
        return v.strip().lower()

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"name": "Shashank Kumar", "email": "shashank@example.com", "cli_version": "1.0.0", "os_type": "linux"}
            ]
        }
    }


class SubscriptionResponse(BaseModel):
    """Response model for successful subscription"""

    status: Optional[str] = None
    message: str
    subscriber_id: Optional[str] = None


class ErrorResponse(BaseModel):
    """Response model for errors"""

    error: str
    details: Optional[dict] = None


class SubscriptionResult(BaseModel):
    """Result of a subscription attempt"""

    status: SubscriptionStatus
    message: str
    subscriber_id: Optional[str] = None
    details: Optional[dict] = None

    model_config = {"use_enum_values": True}


class SubscriberClient:
    """
    Client for interacting with the TESHQ subscription API.

    Environment Variables (Optional):
        TESHQ_SUPABASE_URL: Supabase project URL
        TESHQ_SUPABASE_ANON_KEY: Supabase anonymous key
    """

    DEFAULT_SUPABASE_URL = "https://jmaibzicjbwsydlvcrgy.supabase.co"
    DEFAULT_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImptYWliemljamJ3c3lkbHZjcmd5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjE0OTI0NTYsImV4cCI6MjA3NzA2ODQ1Nn0.F7CvWawQhlJUICYR6dxDii6PNX19tzwQ2_78yAFOijY"  # noqa:E501

    def __init__(self, cli_version: str = "1.0.0", timeout: int = 15):
        self.supabase_url = os.getenv("TESHQ_SUPABASE_URL", self.DEFAULT_SUPABASE_URL)
        self.supabase_anon_key = os.getenv("TESHQ_SUPABASE_ANON_KEY", self.DEFAULT_ANON_KEY)

        self.endpoint = f"{self.supabase_url}/functions/v1/subscribe"
        self.cli_version = cli_version
        self.os_type = self._detect_os()
        self.timeout = timeout
        self.session = self._create_resilient_session()

    def _detect_os(self) -> OSType:
        """Detect the operating system"""
        system = platform.system().lower()
        if system == "darwin":
            return OSType.DARWIN
        elif system == "windows":
            return OSType.WINDOWS
        else:
            return OSType.LINUX

    def _create_resilient_session(self) -> requests.Session:
        """Create a requests session with retry logic"""
        session = requests.Session()
        session.headers.update(
            {
                "apikey": self.supabase_anon_key,
                "Authorization": f"Bearer {self.supabase_anon_key}",
                "Content-Type": "application/json",
            }
        )

        # Retry logic for network resilience
        retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[502, 503, 504], allowed_methods=["POST"])
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("https://", adapter)

        return session

    def subscribe(self, name: str, email: str) -> SubscriptionResult:
        """
        Subscribe a user to TESHQ updates.

        Args:
            name: User's full name (2-100 characters)
            email: User's email address (must be valid and permanent)

        Returns:
            SubscriptionResult with status and details

        Raises:
            ValueError: If input validation fails
        """
        try:
            # Validate input using Pydantic
            request = SubscriptionRequest(name=name, email=email, cli_version=self.cli_version, os_type=self.os_type)
        except Exception as e:
            return SubscriptionResult(
                status=SubscriptionStatus.INVALID_INPUT,
                message=f"Invalid input: {str(e)}",
                details={"validation_error": str(e)},
            )

        try:
            # Send request
            response = self.session.post(self.endpoint, json=request.model_dump(exclude_none=True), timeout=self.timeout)

            # Parse response based on status code
            if response.status_code in [200, 201]:
                return self._handle_success_response(response)
            else:
                return self._handle_error_response(response)

        except requests.exceptions.Timeout:
            return SubscriptionResult(
                status=SubscriptionStatus.CLIENT_ERROR,
                message="Request timed out. Please check your internet connection and try again.",
            )

        except requests.exceptions.ConnectionError:
            return SubscriptionResult(
                status=SubscriptionStatus.CLIENT_ERROR,
                message="Could not connect to the subscription service. Please check your internet connection.",
            )

        except requests.exceptions.RequestException as e:
            return SubscriptionResult(status=SubscriptionStatus.CLIENT_ERROR, message=f"Network error: {str(e)}")

        except Exception as e:
            return SubscriptionResult(
                status=SubscriptionStatus.SERVER_ERROR, message=f"An unexpected error occurred: {str(e)}"
            )

    def _handle_success_response(self, response: requests.Response) -> SubscriptionResult:
        """Handle successful API responses"""
        try:
            data = response.json()

            # Parse using Pydantic model
            subscription_response = SubscriptionResponse(**data)

            # Map API status to our enum
            if response.status_code == 200:
                status = SubscriptionStatus.ALREADY_SUBSCRIBED
            elif subscription_response.status == "RESUBSCRIBED":
                status = SubscriptionStatus.RESUBSCRIBED
            else:
                status = SubscriptionStatus.SUCCESS

            return SubscriptionResult(
                status=status, message=subscription_response.message, subscriber_id=subscription_response.subscriber_id
            )
        except Exception as e:
            return SubscriptionResult(
                status=SubscriptionStatus.SERVER_ERROR, message=f"Failed to parse success response: {str(e)}"
            )

    def _handle_error_response(self, response: requests.Response) -> SubscriptionResult:
        """Handle error API responses"""
        try:
            data = response.json()
            error_response = ErrorResponse(**data)
            error_msg = error_response.error

            # Map HTTP status to our enum
            status_map = {
                400: self._determine_400_status(error_msg),
                410: SubscriptionStatus.PERMANENTLY_DELETED,
                429: SubscriptionStatus.RATE_LIMITED,
            }

            status = status_map.get(response.status_code, SubscriptionStatus.SERVER_ERROR)

            return SubscriptionResult(status=status, message=error_msg, details=error_response.details)
        except Exception:
            # Fallback if response isn't JSON or doesn't match schema
            return SubscriptionResult(
                status=SubscriptionStatus.SERVER_ERROR, message=f"HTTP {response.status_code}: {response.text[:100]}"
            )

    def _determine_400_status(self, error_msg: str) -> SubscriptionStatus:
        """Determine specific status for 400 errors based on message"""
        error_lower = error_msg.lower()
        if "disposable" in error_lower:
            return SubscriptionStatus.DISPOSABLE_EMAIL
        return SubscriptionStatus.INVALID_INPUT


# Convenience function for quick subscriptions
def subscribe_user(name: str, email: str, cli_version: str = "1.0.0") -> SubscriptionResult:
    """
    Convenience function to subscribe a user.

    Args:
        name: User's full name
        email: User's email address
        cli_version: Version of the CLI

    Returns:
        SubscriptionResult
    """
    client = SubscriberClient(cli_version=cli_version)
    return client.subscribe(name=name, email=email)
