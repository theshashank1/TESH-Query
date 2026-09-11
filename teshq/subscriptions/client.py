"""
TESHQ Subscription API Client
Handles communication with the TESHQ subscription API endpoint.
"""

import json
import logging
import platform
from enum import Enum
from typing import Optional

import requests
from pydantic import AliasChoices, BaseModel, EmailStr, Field, field_validator
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Set up module-level logger
logger = logging.getLogger(__name__)


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
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


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
        """Normalize email to lowercase and trim whitespace"""
        return v.strip().lower()

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"name": "Shashank Kumar", "email": "shashank@example.com"}
            ]
        }
    }


class SubscriptionResponse(BaseModel):
    """Response model for successful subscription"""

    status: Optional[str] = None
    message: Optional[str] = None
    subscriber_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("subscriber_id", "subscriberId", "id"),
    )


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

    Features:
    - Connection pooling & automated retries for transient HTTP errors
    - Input validation via Pydantic
    - Context manager support for deterministic resource cleanup
    - Configuration fallback priority: constructor -> ~/.teshq/config.yaml -> defaults
    """

    DEFAULT_API_BASE_URL = "https://teshq-public-api.onrender.com"
    DEFAULT_TIMEOUT = 10
    MAX_PAYLOAD_SIZE = 2048  # 2 KB

    def __init__(
        self,
        cli_version: str = "1.0.0",
        timeout: Optional[int] = None,
        api_base_url: Optional[str] = None,
    ):
        """
        Initialize the SubscriberClient.

        Args:
            cli_version: Version of the CLI (default: "1.0.0")
            timeout: Request timeout in seconds (default: 10)
            api_base_url: Custom API base URL (default: from config or production endpoint)
        """
        try:
            from teshq.config.loader import get_config
            config = get_config()
        except ImportError:
            config = {}

        self.api_base_url = (api_base_url or config.get("TESHQ_API_BASE_URL") or self.DEFAULT_API_BASE_URL).rstrip("/")

        if timeout is not None:
            self.timeout = timeout
        elif config.get("TESHQ_API_TIMEOUT"):
            try:
                self.timeout = int(config["TESHQ_API_TIMEOUT"])
            except (ValueError, TypeError):
                self.timeout = self.DEFAULT_TIMEOUT
        else:
            self.timeout = self.DEFAULT_TIMEOUT

        self.subscribe_endpoint = f"{self.api_base_url}/v1/subscribe"
        self.cli_version = cli_version
        self.os_type = self._detect_os()
        self._session: Optional[requests.Session] = None
        self._closed = False

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures session is closed"""
        self.close()

    def close(self):
        """Close the HTTP session and release resources"""
        if self._session and not self._closed:
            try:
                self._session.close()
            except Exception as e:
                logger.warning(f"Error closing session: {e}")
            finally:
                self._session = None
                self._closed = True

    @property
    def session(self) -> requests.Session:
        """Lazy session initialization with pooling and retry configuration"""
        if self._session is None or self._closed:
            self._session = self._create_session()
            self._closed = False
        return self._session

    def _detect_os(self) -> OSType:
        """Detect the host operating system"""
        system = platform.system().lower()
        if system == "darwin":
            return OSType.DARWIN
        elif system == "windows":
            return OSType.WINDOWS
        else:
            return OSType.LINUX

    def _create_session(self) -> requests.Session:
        """Create a requests session with headers, retry logic, and connection pooling"""
        session = requests.Session()

        session.headers.update(
            {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Client-Version": self.cli_version,
                "X-Client-OS": self.os_type.value,
                "X-Requested-With": "TESHQ-CLI",
            }
        )

        retries = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[502, 503, 504],
            allowed_methods=["POST"],
            raise_on_status=False,
        )

        adapter = HTTPAdapter(
            max_retries=retries,
            pool_connections=5,
            pool_maxsize=10,
            pool_block=False,
        )
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        return session

    def _check_payload_size(self, data: dict) -> bool:
        """Check if payload size is within maximum limit"""
        payload_size = len(json.dumps(data).encode("utf-8"))
        return payload_size <= self.MAX_PAYLOAD_SIZE

    def subscribe(self, name: str, email: str) -> SubscriptionResult:
        """
        Subscribe a user to TESHQ updates.

        Args:
            name: User's full name (2-100 characters)
            email: User's email address

        Returns:
            SubscriptionResult with status and details
        """
        try:
            request = SubscriptionRequest(
                name=name,
                email=email,
                cli_version=self.cli_version,
                os_type=self.os_type,
            )
        except Exception as e:
            return SubscriptionResult(
                status=SubscriptionStatus.INVALID_INPUT,
                message=f"Invalid input: {str(e)}",
                details={"validation_error": str(e)},
            )

        payload = {
            "name": request.name,
            "email": request.email,
        }

        if not self._check_payload_size(payload):
            return SubscriptionResult(
                status=SubscriptionStatus.INVALID_INPUT,
                message="Request payload exceeds maximum size of 2 KB",
                details={"payload_size_error": "Payload too large"},
            )

        try:
            response = self.session.post(
                self.subscribe_endpoint,
                json=payload,
                timeout=self.timeout,
            )

            if response.status_code == 201:
                return self._handle_success_response(response, is_created=True)
            elif response.status_code == 200:
                return self._handle_success_response(response, is_created=False)
            elif response.status_code == 503:
                return SubscriptionResult(
                    status=SubscriptionStatus.SERVICE_UNAVAILABLE,
                    message="Subscription service is temporarily unavailable. Please try again later.",
                )
            else:
                return self._handle_error_response(response)

        except requests.exceptions.Timeout:
            return SubscriptionResult(
                status=SubscriptionStatus.CLIENT_ERROR,
                message="Request timed out. The subscription service may be temporarily unreachable.",
            )

        except requests.exceptions.ConnectionError:
            return SubscriptionResult(
                status=SubscriptionStatus.CLIENT_ERROR,
                message="Could not connect to the subscription service. Please check your internet connection.",
            )

        except requests.exceptions.RequestException as e:
            return SubscriptionResult(
                status=SubscriptionStatus.CLIENT_ERROR,
                message=f"Network error occurred: {str(e)[:100]}",
            )

        except Exception as e:
            return SubscriptionResult(
                status=SubscriptionStatus.SERVER_ERROR,
                message=f"An unexpected error occurred: {str(e)}",
            )

    def _handle_success_response(self, response: requests.Response, is_created: bool = False) -> SubscriptionResult:
        """Handle successful API responses (200, 201)"""
        try:
            data = response.json() if response.content else {}
            subscription_response = SubscriptionResponse(**data)

            raw_status = (subscription_response.status or "").upper()
            if is_created:
                status = SubscriptionStatus.SUCCESS
                default_msg = "Subscription successful"
            elif raw_status in ("RESUBSCRIBED", "RE_SUBSCRIBED"):
                status = SubscriptionStatus.RESUBSCRIBED
                default_msg = "Welcome back! You have been re-subscribed."
            elif raw_status in ("ALREADY_SUBSCRIBED", "ALREADY_REGISTERED") or response.status_code == 200:
                status = SubscriptionStatus.ALREADY_SUBSCRIBED
                default_msg = "You are already subscribed to updates."
            else:
                status = SubscriptionStatus.SUCCESS
                default_msg = "Subscription successful"

            return SubscriptionResult(
                status=status,
                message=subscription_response.message or default_msg,
                subscriber_id=subscription_response.subscriber_id,
            )
        except Exception as e:
            return SubscriptionResult(
                status=SubscriptionStatus.SERVER_ERROR,
                message=f"Failed to parse response: {str(e)}",
                details={"parse_error": str(e)},
            )

    def _handle_error_response(self, response: requests.Response) -> SubscriptionResult:
        """Handle error API responses with appropriate status code mapping"""
        try:
            data = response.json()
            error_response = ErrorResponse(**data)
            error_msg = error_response.error

            status_map = {
                400: self._determine_400_status(error_msg),
                410: SubscriptionStatus.PERMANENTLY_DELETED,
                415: SubscriptionStatus.INVALID_INPUT,
                429: SubscriptionStatus.RATE_LIMITED,
                503: SubscriptionStatus.SERVICE_UNAVAILABLE,
            }

            status = status_map.get(response.status_code, SubscriptionStatus.SERVER_ERROR)

            return SubscriptionResult(
                status=status,
                message=error_msg,
                details=error_response.details,
            )
        except Exception:
            return SubscriptionResult(
                status=SubscriptionStatus.SERVER_ERROR,
                message=f"HTTP {response.status_code}: {response.text[:100]}",
            )

    def _determine_400_status(self, error_msg: str) -> SubscriptionStatus:
        """Determine specific status for 400 errors based on error message"""
        error_lower = error_msg.lower()
        if "disposable" in error_lower:
            return SubscriptionStatus.DISPOSABLE_EMAIL
        return SubscriptionStatus.INVALID_INPUT


def subscribe_user(name: str, email: str, cli_version: str = "1.0.0") -> SubscriptionResult:
    """Convenience helper to subscribe a user"""
    with SubscriberClient(cli_version=cli_version) as client:
        return client.subscribe(name=name, email=email)
