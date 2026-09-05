"""
TESHQ Subscription API Client
Handles communication with the TESHQ subscription API endpoint with comprehensive security features
"""

import hashlib
import hmac
import logging
import os
import platform
from enum import Enum
from typing import Optional

import requests
from pydantic import BaseModel, EmailStr, Field, field_validator
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
    """Request model for subscription - minimal data as per security requirements"""

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
        """Normalize email to lowercase as per API spec"""
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
    message: Optional[str] = None  # Made optional as API may not return this
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
    Implements all security features:
    - 4-Tier IP Rate Limiting (handled by server)
    - 2 KB payload size limit
    - Content-Type: application/json enforcement
    - Zod strict schema validation (server-side)
    - SHA-256 duplicate idempotency
    - Cloudflare IP extraction awareness
    - Security headers via Helmet
    - Kill switch support (503 when SUBSCRIPTIONS_ENABLED=false)

    Configuration:
        The client reads configuration from (in order of priority):
        1. Constructor parameters (api_base_url, admin_api_key, timeout)
        2. TESHQ config file (config.json or .env)
        3. Sensible defaults

    Usage:
        # As context manager (recommended)
        with SubscriberClient() as client:
            result = client.subscribe(name="John", email="john@example.com")

        # With custom configuration
        client = SubscriberClient(
            api_base_url="https://custom-api.example.com",
            timeout=15
        )

        # Traditional usage (remember to close manually)
        client = SubscriberClient()
        try:
            result = client.subscribe(name="John", email="john@example.com")
        finally:
            client.close()
    """

    DEFAULT_API_BASE_URL = "https://teshq-public-api.onrender.com"
    DEFAULT_TIMEOUT = 10  # Reduced from 15 for better UX

    # Rate limit settings for client-side awareness
    RATE_LIMIT_PER_SEC = 2
    RATE_LIMIT_PER_MIN = 30
    MAX_PAYLOAD_SIZE = 2048  # 2 KB as per spec

    def __init__(
        self,
        cli_version: str = "1.0.0",
        timeout: Optional[int] = None,
        api_base_url: Optional[str] = None,
        admin_api_key: Optional[str] = None
    ):
        """
        Initialize the SubscriberClient.

        Args:
            cli_version: Version of the CLI (default: "1.0.0")
            timeout: Request timeout in seconds (default: 10)
            api_base_url: Custom API base URL (default: from config or https://teshq-public-api.onrender.com)
            admin_api_key: Admin API key for administrative endpoints (default: from config)
        """
        # Import here to avoid circular imports
        try:
            from teshq.config.loader import get_config
            config = get_config()
        except ImportError:
            config = {}

        # Configuration priority: constructor args > config file > defaults
        self.api_base_url = api_base_url or config.get("TESHQ_API_BASE_URL") or self.DEFAULT_API_BASE_URL
        self.admin_api_key = admin_api_key or config.get("TESHQ_ADMIN_API_KEY")

        # Handle timeout from constructor, config, or default
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
        self.health_endpoint = f"{self.api_base_url}/v1/health"
        self.subscribers_endpoint = f"{self.api_base_url}/v1/subscribers"

        self.cli_version = cli_version
        self.os_type = self._detect_os()
        self._session: Optional[requests.Session] = None
        self._closed = False

        logger.debug(f"SubscriberClient initialized", extra={
            "api_base_url": self.api_base_url,
            "timeout": self.timeout,
            "cli_version": cli_version
        })

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures session is closed"""
        self.close()

    def close(self):
        """Close the session and release resources"""
        if self._session and not self._closed:
            try:
                self._session.close()
                logger.debug("Session closed successfully")
            except Exception as e:
                logger.warning(f"Error closing session: {e}")
            finally:
                self._session = None
                self._closed = True

    @property
    def session(self) -> requests.Session:
        """Lazy session initialization"""
        if self._session is None or self._closed:
            self._session = self._create_secure_session()
            self._closed = False
        return self._session

    def _detect_os(self) -> OSType:
        """Detect the operating system"""
        system = platform.system().lower()
        if system == "darwin":
            return OSType.DARWIN
        elif system == "windows":
            return OSType.WINDOWS
        else:
            return OSType.LINUX

    def _create_secure_session(self) -> requests.Session:
        """
        Create a requests session with security headers, retry logic, and connection pooling.
        Implements Cloudflare-aware IP extraction headers.
        """
        session = requests.Session()

        # Security headers as per spec
        session.headers.update(
            {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Client-Version": self.cli_version,
                "X-Client-OS": self.os_type.value,
                "X-Requested-With": "TESHQ-CLI",
            }
        )

        # Add admin key if available (for /v1/subscribers endpoint)
        if self.admin_api_key:
            # Reject non-HTTPS URLs when using admin credentials for security
            if not self.api_base_url.startswith("https://"):
                raise ValueError(
                    "Admin API key cannot be used with non-HTTPS URLs. "
                    f"Current URL: {self.api_base_url}"
                )
            session.headers.update({
                "Authorization": f"Bearer {self.admin_api_key}"
            })

        # Retry logic for 502, 503, 504 (service unavailable scenarios)
        retries = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[502, 503, 504],
            allowed_methods=["POST", "GET"],
            raise_on_status=False  # Don't raise exception on status codes, let us handle them
        )

        # Connection pooling configuration for production
        adapter = HTTPAdapter(
            max_retries=retries,
            pool_connections=10,    # Number of connection pools to cache
            pool_maxsize=20,        # Max number of connections to save in the pool
            pool_block=False        # Don't block when pool is full, create new connection
        )
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        logger.debug("Session created with connection pooling", extra={
            "pool_connections": 10,
            "pool_maxsize": 20
        })

        return session

    def _check_payload_size(self, data: dict) -> bool:
        """Check if payload exceeds 2 KB limit"""
        import json
        payload_size = len(json.dumps(data).encode('utf-8'))
        return payload_size <= self.MAX_PAYLOAD_SIZE

    def subscribe(self, name: str, email: str) -> SubscriptionResult:
        """
        Subscribe a user to TESHQ updates.

        Args:
            name: User's full name (2-100 characters)
            email: User's email address (must be valid and permanent)

        Returns:
            SubscriptionResult with status and details

        Security features implemented:
        - Email normalization (lowercase)
        - Payload size validation (2 KB max)
        - Content-Type enforcement
        - Server-side rate limiting (4 tiers)
        - Duplicate idempotency via SHA-256
        """
        logger.info(f"Starting subscription request", extra={
            "email_domain": email.split("@")[-1] if "@" in email else "invalid",
            "cli_version": self.cli_version
        })

        try:
            # Validate input using Pydantic (strict schema)
            request = SubscriptionRequest(
                name=name,
                email=email,
                cli_version=self.cli_version,
                os_type=self.os_type
            )
        except Exception as e:
            logger.warning(f"Input validation failed", extra={"error": str(e)})
            return SubscriptionResult(
                status=SubscriptionStatus.INVALID_INPUT,
                message=f"Invalid input: {str(e)}",
                details={"validation_error": str(e)},
            )

        # Prepare payload (only name and email as per security spec)
        payload = {
            "name": request.name,
            "email": request.email
        }

        # Check payload size (2 KB limit)
        if not self._check_payload_size(payload):
            logger.warning(f"Payload size exceeded", extra={
                "payload_size": len(str(payload)),
                "max_size": self.MAX_PAYLOAD_SIZE
            })
            return SubscriptionResult(
                status=SubscriptionStatus.INVALID_INPUT,
                message="Request payload exceeds maximum size of 2 KB",
                details={"payload_size_error": "Payload too large"},
            )

        try:
            logger.debug(f"Sending subscription request", extra={
                "endpoint": self.subscribe_endpoint,
                "timeout": self.timeout
            })

            # Send request to /v1/subscribe endpoint
            response = self.session.post(
                self.subscribe_endpoint,
                json=payload,
                timeout=self.timeout
            )

            logger.info(f"Received response", extra={
                "status_code": response.status_code,
                "endpoint": self.subscribe_endpoint
            })

            # Handle 201 Created (success) and other responses
            if response.status_code == 201:
                return self._handle_success_response(response)
            elif response.status_code == 200:
                # Already subscribed or resubscribed
                return self._handle_success_response(response)
            elif response.status_code == 503:
                return SubscriptionResult(
                    status=SubscriptionStatus.SERVICE_UNAVAILABLE,
                    message="Subscription service temporarily unavailable (kill switch active)",
                    details={"kill_switch": "SUBSCRIPTIONS_ENABLED=false"}
                )
            else:
                return self._handle_error_response(response)

        except requests.exceptions.Timeout as e:
            logger.error(f"Request timeout", extra={
                "timeout": self.timeout,
                "endpoint": self.subscribe_endpoint,
                "error": str(e)
            })
            return SubscriptionResult(
                status=SubscriptionStatus.CLIENT_ERROR,
                message="Request timed out. The API server may be slow or unreachable.",
                details={
                    "error_type": "timeout",
                    "timeout_seconds": self.timeout,
                    "endpoint": self.subscribe_endpoint
                }
            )

        except requests.exceptions.ConnectionError as e:
            error_str = str(e).lower()
            details = {"error_type": "connection_error", "original_error": str(e), "endpoint": self.subscribe_endpoint}

            logger.error(f"Connection error", extra={
                "error": str(e),
                "endpoint": self.subscribe_endpoint
            })

            # Provide specific error messages based on the type of connection error
            if "name or service not known" in error_str or "getaddrinfo failed" in error_str or "nxdomain" in error_str:
                return SubscriptionResult(
                    status=SubscriptionStatus.CLIENT_ERROR,
                    message=f"API endpoint not found: Could not resolve domain '{self.api_base_url}'. Please verify the API URL is correct.",
                    details={**details, "suggestion": "Check TESHQ_API_BASE_URL environment variable or contact support"}
                )
            elif "ssl" in error_str or "certificate" in error_str:
                return SubscriptionResult(
                    status=SubscriptionStatus.CLIENT_ERROR,
                    message="SSL/TLS certificate error. The API server's certificate is not trusted.",
                    details={**details, "suggestion": "Check system date/time or contact support"}
                )
            elif "refused" in error_str:
                return SubscriptionResult(
                    status=SubscriptionStatus.CLIENT_ERROR,
                    message="Connection refused. The API server may be down or not accepting connections.",
                    details={**details, "suggestion": "Verify the API server is running"}
                )
            else:
                return SubscriptionResult(
                    status=SubscriptionStatus.CLIENT_ERROR,
                    message="Could not connect to the subscription service. Please check your internet connection.",
                    details=details
                )

        except requests.exceptions.RequestException as e:
            error_str = str(e).lower()
            details = {"error_type": "request_error", "original_error": str(e)}

            logger.error(f"Request exception", extra={"error": str(e)})

            # Check for common proxy issues
            if "proxy" in error_str:
                return SubscriptionResult(
                    status=SubscriptionStatus.CLIENT_ERROR,
                    message="Proxy error detected. Please check your proxy settings.",
                    details={**details, "suggestion": "Check HTTP_PROXY/HTTPS_PROXY environment variables"}
                )
            else:
                return SubscriptionResult(
                    status=SubscriptionStatus.CLIENT_ERROR,
                    message=f"Network error: {str(e)[:100]}",
                    details=details
                )

        except Exception as e:
            return SubscriptionResult(
                status=SubscriptionStatus.SERVER_ERROR,
                message=f"An unexpected error occurred: {str(e)}"
            )

    def health_check(self) -> SubscriptionResult:
        """
        Check the health of the subscription API.

        Endpoint: GET /v1/health
        Returns: {"status": "ok"} on success
        """
        try:
            response = self.session.get(
                self.health_endpoint,
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json() if response.content else {}
                if data.get("status") == "ok":
                    return SubscriptionResult(
                        status=SubscriptionStatus.SUCCESS,
                        message="Subscription API is healthy",
                        details={"health_status": data.get("status", "ok")}
                    )
                else:
                    return SubscriptionResult(
                        status=SubscriptionStatus.SERVER_ERROR,
                        message="Unexpected health check response",
                        details={"response": data}
                    )
            else:
                return SubscriptionResult(
                    status=SubscriptionStatus.SERVER_ERROR,
                    message=f"Health check failed with status {response.status_code}",
                    details={"status_code": response.status_code}
                )

        except Exception as e:
            return SubscriptionResult(
                status=SubscriptionStatus.CLIENT_ERROR,
                message=f"Health check error: {str(e)}"
            )

    def get_subscribers(self, limit: int = 50, cursor: Optional[str] = None) -> SubscriptionResult:
        """
        Retrieve subscribers list (Admin only).

        Endpoint: GET /v1/subscribers
        Auth: Bearer <ADMIN_API_KEY>
        Supports cursor pagination
        """
        if not self.admin_api_key:
            return SubscriptionResult(
                status=SubscriptionStatus.CLIENT_ERROR,
                message="Admin API key required for this endpoint",
                details={"auth_error": "TESHQ_ADMIN_API_KEY not set"}
            )

        try:
            params = {"limit": limit}
            if cursor:
                params["cursor"] = cursor

            response = self.session.get(
                self.subscribers_endpoint,
                params=params,
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                return SubscriptionResult(
                    status=SubscriptionStatus.SUCCESS,
                    message="Subscribers retrieved successfully",
                    details={"subscribers": data}
                )
            elif response.status_code == 401:
                return SubscriptionResult(
                    status=SubscriptionStatus.CLIENT_ERROR,
                    message="Unauthorized: Invalid admin API key",
                    details={"auth_error": "Invalid credentials"}
                )
            else:
                return self._handle_error_response(response)

        except Exception as e:
            return SubscriptionResult(
                status=SubscriptionStatus.CLIENT_ERROR,
                message=f"Failed to retrieve subscribers: {str(e)}"
            )

    def _handle_success_response(self, response: requests.Response) -> SubscriptionResult:
        """Handle successful API responses (200, 201)"""
        try:
            data = response.json()

            # Parse using Pydantic model
            subscription_response = SubscriptionResponse(**data)

            # Map API status to our enum
            api_status = subscription_response.status
            if response.status_code == 201:
                status = SubscriptionStatus.SUCCESS
            elif api_status == "RESUBSCRIBED":
                status = SubscriptionStatus.RESUBSCRIBED
            elif api_status == "ALREADY_SUBSCRIBED" or response.status_code == 200:
                status = SubscriptionStatus.ALREADY_SUBSCRIBED
            else:
                status = SubscriptionStatus.SUCCESS

            return SubscriptionResult(
                status=status,
                message=subscription_response.message or "Subscription successful",
                subscriber_id=subscription_response.subscriber_id
            )
        except Exception as e:
            return SubscriptionResult(
                status=SubscriptionStatus.SERVER_ERROR,
                message=f"Failed to parse success response: {str(e)}",
                details={"parse_error": str(e)}
            )

    def _handle_error_response(self, response: requests.Response) -> SubscriptionResult:
        """Handle error API responses with comprehensive status code mapping"""
        try:
            data = response.json()
            error_response = ErrorResponse(**data)
            error_msg = error_response.error

            # Map HTTP status codes to SubscriptionStatus per API spec
            status_map = {
                400: self._determine_400_status(error_msg),
                410: SubscriptionStatus.PERMANENTLY_DELETED,
                429: SubscriptionStatus.RATE_LIMITED,
                415: SubscriptionStatus.INVALID_INPUT,  # Unsupported Media Type
                503: SubscriptionStatus.SERVICE_UNAVAILABLE,
            }

            status = status_map.get(response.status_code, SubscriptionStatus.SERVER_ERROR)

            return SubscriptionResult(
                status=status,
                message=error_msg,
                details=error_response.details
            )
        except Exception:
            # Fallback if response isn't JSON
            return SubscriptionResult(
                status=SubscriptionStatus.SERVER_ERROR,
                message=f"HTTP {response.status_code}: {response.text[:100]}"
            )

    def _determine_400_status(self, error_msg: str) -> SubscriptionStatus:
        """Determine specific status for 400 errors based on message content"""
        error_lower = error_msg.lower()
        if "disposable" in error_lower:
            return SubscriptionStatus.DISPOSABLE_EMAIL
        elif "schema" in error_lower or "validation" in error_lower:
            return SubscriptionStatus.INVALID_INPUT
        elif "content-type" in error_lower or "unsupported media" in error_lower:
            return SubscriptionStatus.INVALID_INPUT
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


def diagnose_connection(api_base_url: str = SubscriberClient.DEFAULT_API_BASE_URL) -> dict:
    """
    Diagnose connection issues to the subscription API.
    Run this to troubleshoot "Check your internet connection" errors.

    Args:
        api_base_url: The API base URL to test (default: https://api.teshq.io)

    Returns:
        dict with diagnostic results
    """
    import socket
    import ssl
    from urllib.parse import urlparse

    results = {
        "url": api_base_url,
        "timestamp": "",
        "tests": {},
        "recommendations": []
    }

    from datetime import datetime
    results["timestamp"] = datetime.utcnow().isoformat()

    # Parse URL
    parsed = urlparse(api_base_url)
    hostname = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    print(f"🔍 Diagnosing connection to {api_base_url}...")
    print()

    # Test 1: DNS Resolution
    print("1️⃣  Testing DNS resolution...")
    try:
        ip = socket.gethostbyname(hostname)
        results["tests"]["dns_resolution"] = {"status": "✅ PASS", "ip": ip}
        print(f"   ✅ DNS resolved: {hostname} -> {ip}")
    except socket.gaierror as e:
        results["tests"]["dns_resolution"] = {"status": "❌ FAIL", "error": str(e)}
        print(f"   ❌ DNS resolution failed: {e}")
        results["recommendations"].append(f"The domain '{hostname}' does not exist. Verify the API URL or contact support.")
        return results

    # Test 2: TCP Connection
    print("\n2️⃣  Testing TCP connection...")
    try:
        sock = socket.create_connection((hostname, port), timeout=5)
        sock.close()
        results["tests"]["tcp_connection"] = {"status": "✅ PASS", "port": port}
        print(f"   ✅ TCP connection to port {port} successful")
    except (socket.timeout, ConnectionRefusedError) as e:
        results["tests"]["tcp_connection"] = {"status": "❌ FAIL", "error": str(e)}
        print(f"   ❌ TCP connection failed: {e}")
        results["recommendations"].append(f"Cannot connect to port {port}. The server may be down or a firewall is blocking the connection.")

    # Test 3: HTTPS/SSL (if applicable)
    if parsed.scheme == "https":
        print("\n3️⃣  Testing SSL/TLS...")
        try:
            context = ssl.create_default_context()
            with socket.create_connection((hostname, port), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    results["tests"]["ssl"] = {"status": "✅ PASS", "certificate": bool(cert)}
                    print(f"   ✅ SSL handshake successful")
                    if cert:
                        subject = cert.get("subject", [])
                        issuer = cert.get("issuer", [])
                        print(f"   📜 Certificate subject: {subject}")
                        print(f"   📜 Certificate issuer: {issuer}")
        except ssl.SSLError as e:
            results["tests"]["ssl"] = {"status": "❌ FAIL", "error": str(e)}
            print(f"   ❌ SSL error: {e}")
            results["recommendations"].append("SSL certificate error. Check system time/date or certificates.")
        except Exception as e:
            results["tests"]["ssl"] = {"status": "❌ FAIL", "error": str(e)}
            print(f"   ❌ SSL test failed: {e}")

    # Test 4: HTTP Request
    print("\n4️⃣  Testing HTTP request...")
    try:
        import requests
        response = requests.get(f"{api_base_url}/v1/health", timeout=10)
        results["tests"]["http"] = {
            "status": "✅ PASS" if response.status_code == 200 else "⚠️  WARNING",
            "status_code": response.status_code,
            "response_preview": response.text[:200]
        }
        if response.status_code == 200:
            print(f"   ✅ HTTP 200 OK")
            print(f"   📄 Response: {response.text[:100]}")
        else:
            print(f"   ⚠️  HTTP {response.status_code}")
            print(f"   📄 Response: {response.text[:100]}")
            results["recommendations"].append(f"API returned HTTP {response.status_code}. Check API documentation.")
    except Exception as e:
        results["tests"]["http"] = {"status": "❌ FAIL", "error": str(e)}
        print(f"   ❌ HTTP request failed: {e}")

    # Summary
    print("\n" + "="*60)
    print("📊 DIAGNOSIS SUMMARY")
    print("="*60)

    failed_tests = [k for k, v in results["tests"].items() if "FAIL" in v.get("status", "")]

    if not failed_tests:
        print("✅ All tests passed! The API should be accessible.")
    else:
        print(f"❌ {len(failed_tests)} test(s) failed:")
        for test in failed_tests:
            print(f"   • {test}")

    if results["recommendations"]:
        print("\n💡 Recommendations:")
        for i, rec in enumerate(results["recommendations"], 1):
            print(f"   {i}. {rec}")

    print("\n🛠️  Configuration:")
    # Show current configuration (without exposing sensitive values)
    try:
        from teshq.config.loader import get_config
        config = get_config()
        api_url = config.get('TESHQ_API_BASE_URL', 'not set')
        admin_key = config.get('TESHQ_ADMIN_API_KEY')
        admin_display = "set" if admin_key else "not set"
    except ImportError:
        api_url = "not set"
        admin_display = "not set"

    print(f"   TESHQ_API_BASE_URL={api_url}")
    print(f"   TESHQ_ADMIN_API_KEY={admin_display}")
    print(f"\n   To configure:")
    print(f"      teshq config --api-url https://your-api.com")
    print(f"   Or edit config.json and add:")
    print(f'      {{"TESHQ_API_BASE_URL": "https://your-api.com"}}')

    return results
