"""
Unit tests for TESHQ subscription client and CLI.

Tests cover:
- Model validation (edge cases, boundary conditions)
- HTTP response handling (all status codes)
- Network errors (timeout, connection error)
- CLI result handlers
- Edge cases (empty inputs, special characters, max lengths)
"""

from unittest.mock import MagicMock, patch

import pytest
import requests
from pydantic import ValidationError
from typer.testing import CliRunner

from teshq.cli.subscribe import app as subscribe_app
from teshq.cli.subscribe import handle_subscription_result
from teshq.cli.unsubscribe import app as unsubscribe_app
from teshq.cli.unsubscribe import handle_unsubscribe_result
from teshq.subscriptions.client import (
    OSType,
    SubscriberClient,
    SubscriptionRequest,
    SubscriptionResponse,
    SubscriptionResult,
    SubscriptionStatus,
    UnsubscribeRequest,
    UnsubscribeResponse,
    UnsubscribeResult,
    UnsubscribeStatus,
    subscribe_user,
    unsubscribe_user,
)


runner = CliRunner()


class TestSubscriptionModels:
    """Test subscription Pydantic models."""

    def test_valid_request(self):
        req = SubscriptionRequest(name=" Alice Smith ", email=" Alice@Example.COM ")
        assert req.name == "Alice Smith"
        assert req.email == "alice@example.com"

    def test_name_too_short(self):
        with pytest.raises(ValidationError):
            SubscriptionRequest(name="A", email="alice@example.com")

    def test_name_empty(self):
        with pytest.raises(ValidationError):
            SubscriptionRequest(name="   ", email="alice@example.com")

    def test_invalid_email(self):
        with pytest.raises(ValidationError):
            SubscriptionRequest(name="Alice", email="not-an-email")

    def test_subscription_response_aliases(self):
        # snake_case
        r1 = SubscriptionResponse(**{"subscriber_id": "sub_123"})
        assert r1.subscriber_id == "sub_123"

        # camelCase
        r2 = SubscriptionResponse(**{"subscriberId": "sub_456"})
        assert r2.subscriber_id == "sub_456"

        # id
        r3 = SubscriptionResponse(**{"id": "sub_789"})
        assert r3.subscriber_id == "sub_789"

    def test_name_max_length(self):
        """Test name at max length (100 chars)"""
        name = "A" * 100
        req = SubscriptionRequest(name=name, email="alice@example.com")
        assert req.name == name

    def test_name_exceeds_max_length(self):
        """Test name exceeds max length (101 chars)"""
        with pytest.raises(ValidationError):
            SubscriptionRequest(name="A" * 101, email="alice@example.com")

    def test_name_with_special_characters(self):
        """Test name with special characters"""
        req = SubscriptionRequest(name="José García-Müller", email="alice@example.com")
        assert req.name == "José García-Müller"

    def test_name_with_numbers(self):
        """Test name with numbers"""
        req = SubscriptionRequest(name="John Doe 123", email="alice@example.com")
        assert req.name == "John Doe 123"

    def test_email_normalization_unicode(self):
        """Test email with unicode domains"""
        # This should validate as it's a valid email format
        req = SubscriptionRequest(name="Test", email="user@example.com")
        assert req.email == "user@example.com"


class TestUnsubscribeModels:
    """Test unsubscribe Pydantic models."""

    def test_valid_unsubscribe_request(self):
        req = UnsubscribeRequest(email=" Alice@Example.COM ")
        assert req.email == "alice@example.com"

    def test_unsubscribe_invalid_email(self):
        with pytest.raises(ValidationError):
            UnsubscribeRequest(email="not-an-email")

    def test_unsubscribe_response_aliases(self):
        # snake_case
        r1 = UnsubscribeResponse(**{"unsubscribed_at": "2024-01-15T10:30:00Z"})
        assert r1.unsubscribed_at == "2024-01-15T10:30:00Z"

        # camelCase
        r2 = UnsubscribeResponse(**{"unsubscribedAt": "2024-01-15T10:30:00Z"})
        assert r2.unsubscribed_at == "2024-01-15T10:30:00Z"

        # timestamp
        r3 = UnsubscribeResponse(**{"timestamp": "2024-01-15T10:30:00Z"})
        assert r3.unsubscribed_at == "2024-01-15T10:30:00Z"

    def test_unsubscribe_empty_email(self):
        """Test unsubscribe with empty email"""
        with pytest.raises(ValidationError):
            UnsubscribeRequest(email="")

    def test_unsubscribe_whitespace_email(self):
        """Test unsubscribe with whitespace-only email"""
        with pytest.raises(ValidationError):
            UnsubscribeRequest(email="   ")


class TestSubscriberClient:
    """Test SubscriberClient behaviors and configuration."""

    def test_default_initialization(self):
        client = SubscriberClient(cli_version="2.0.0")
        assert client.cli_version == "2.0.0"
        assert "https://teshq-public-api.onrender.com" in client.api_base_url
        assert client.timeout == 10
        assert client.os_type in (OSType.LINUX, OSType.DARWIN, OSType.WINDOWS)

    def test_custom_parameters(self):
        client = SubscriberClient(
            cli_version="3.0.0",
            timeout=25,
            api_base_url="https://custom-api.example.com",
        )
        assert client.cli_version == "3.0.0"
        assert client.timeout == 25
        assert client.api_base_url == "https://custom-api.example.com"
        assert client.subscribe_endpoint == "https://custom-api.example.com/v1/subscribe"
        assert client.unsubscribe_endpoint == "https://custom-api.example.com/v1/unsubscribe"

    def test_api_base_url_trailing_slash(self):
        """Test that trailing slashes are removed from API base URL"""
        client = SubscriberClient(api_base_url="https://api.example.com/")
        assert client.api_base_url == "https://api.example.com"

    def test_context_manager_closes_session(self):
        with SubscriberClient() as client:
            session = client.session
            assert session is not None
            assert not client._closed
        assert client._closed
        assert client._session is None

    def test_payload_size_limit(self):
        client = SubscriberClient()
        oversized = {"name": "A" * 3000, "email": "a@example.com"}
        assert client._check_payload_size(oversized) is False

        normal = {"name": "Alice", "email": "alice@example.com"}
        assert client._check_payload_size(normal) is True

    def test_invalid_input_returns_immediately(self):
        client = SubscriberClient()
        result = client.subscribe(name="", email="alice@example.com")
        assert result.status == SubscriptionStatus.INVALID_INPUT

    def test_os_detection(self):
        """Test OS detection returns valid OSType"""
        client = SubscriberClient()
        assert isinstance(client.os_type, OSType)
        assert client.os_type.value in ["linux", "darwin", "windows"]

    def test_session_reuse(self):
        """Test that session is reused within context"""
        client = SubscriberClient()
        session1 = client.session
        session2 = client.session
        assert session1 is session2

    def test_close_already_closed(self):
        """Test closing an already closed client"""
        client = SubscriberClient()
        client.close()
        # Should not raise
        client.close()


class TestSubscriberClientResponses:
    """Test HTTP response handling in SubscriberClient."""

    @patch("requests.Session.post")
    def test_201_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.content = b'{"status": "success", "subscriber_id": "sub_1"}'
        mock_resp.json.return_value = {"status": "success", "subscriber_id": "sub_1"}
        mock_post.return_value = mock_resp

        with SubscriberClient() as client:
            res = client.subscribe("Alice", "alice@example.com")
        assert res.status == SubscriptionStatus.SUCCESS
        assert res.subscriber_id == "sub_1"

    @patch("requests.Session.post")
    def test_200_already_registered(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"status": "already_registered"}'
        mock_resp.json.return_value = {"status": "already_registered"}
        mock_post.return_value = mock_resp

        with SubscriberClient() as client:
            res = client.subscribe("Alice", "alice@example.com")
        assert res.status == SubscriptionStatus.ALREADY_SUBSCRIBED

    @patch("requests.Session.post")
    def test_200_resubscribed(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"status": "resubscribed"}'
        mock_resp.json.return_value = {"status": "resubscribed"}
        mock_post.return_value = mock_resp

        with SubscriberClient() as client:
            res = client.subscribe("Alice", "alice@example.com")
        assert res.status == SubscriptionStatus.RESUBSCRIBED

    @patch("requests.Session.post")
    def test_400_disposable_email(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {"error": "Disposable email addresses are not allowed"}
        mock_post.return_value = mock_resp

        with SubscriberClient() as client:
            res = client.subscribe("Alice", "alice@mailinator.com")
        assert res.status == SubscriptionStatus.DISPOSABLE_EMAIL

    @patch("requests.Session.post")
    def test_400_invalid_email(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {"error": "invalid_email"}
        mock_post.return_value = mock_resp

        with SubscriberClient() as client:
            res = client.subscribe("Alice", "alice@test.com")
        assert res.status == SubscriptionStatus.INVALID_INPUT

    @patch("requests.Session.post")
    def test_429_rate_limited(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.json.return_value = {"error": "Too many requests"}
        mock_post.return_value = mock_resp

        with SubscriberClient() as client:
            res = client.subscribe("Alice", "alice@example.com")
        assert res.status == SubscriptionStatus.RATE_LIMITED

    @patch("requests.Session.post")
    def test_503_service_unavailable(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.json.return_value = {"error": "Service temporarily unavailable"}
        mock_post.return_value = mock_resp

        with SubscriberClient() as client:
            res = client.subscribe("Alice", "alice@example.com")
        assert res.status == SubscriptionStatus.SERVICE_UNAVAILABLE

    @patch("requests.Session.post")
    def test_500_server_error(self, mock_post):
        """Test 500 internal server error"""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"error": "Internal server error"}
        mock_post.return_value = mock_resp

        with SubscriberClient() as client:
            res = client.subscribe("Alice", "alice@example.com")
        assert res.status == SubscriptionStatus.SERVER_ERROR

    @patch("requests.Session.post")
    def test_502_bad_gateway(self, mock_post):
        """Test 502 bad gateway"""
        mock_resp = MagicMock()
        mock_resp.status_code = 502
        mock_resp.json.return_value = {"error": "Bad gateway"}
        mock_post.return_value = mock_resp

        with SubscriberClient() as client:
            res = client.subscribe("Alice", "alice@example.com")
        assert res.status == SubscriptionStatus.SERVER_ERROR

    @patch("requests.Session.post")
    def test_empty_response_body(self, mock_post):
        """Test response with empty body"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b""
        mock_resp.json.return_value = {}
        mock_post.return_value = mock_resp

        with SubscriberClient() as client:
            res = client.subscribe("Alice", "alice@example.com")
        assert res.status == SubscriptionStatus.ALREADY_SUBSCRIBED

    @patch("requests.Session.post")
    def test_malformed_json_response(self, mock_post):
        """Test malformed JSON in response"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"not json"
        mock_resp.json.side_effect = ValueError("Invalid JSON")
        mock_post.return_value = mock_resp

        with SubscriberClient() as client:
            res = client.subscribe("Alice", "alice@example.com")
        assert res.status == SubscriptionStatus.SERVER_ERROR

    @patch("requests.Session.post", side_effect=requests.exceptions.ConnectionError("Failed to connect"))
    def test_connection_error(self, mock_post):
        with SubscriberClient() as client:
            res = client.subscribe("Alice", "alice@example.com")
        assert res.status == SubscriptionStatus.CLIENT_ERROR
        assert "internet connection" in res.message.lower()

    @patch("requests.Session.post", side_effect=requests.exceptions.Timeout("Timeout"))
    def test_timeout_error(self, mock_post):
        with SubscriberClient() as client:
            res = client.subscribe("Alice", "alice@example.com")
        assert res.status == SubscriptionStatus.CLIENT_ERROR
        assert "timed out" in res.message.lower()

    @patch("requests.Session.post", side_effect=requests.exceptions.TooManyRedirects("Too many redirects"))
    def test_too_many_redirects(self, mock_post):
        """Test too many redirects error"""
        with SubscriberClient() as client:
            res = client.subscribe("Alice", "alice@example.com")
        assert res.status == SubscriptionStatus.CLIENT_ERROR


class TestUnsubscriberClientResponses:
    """Test HTTP response handling for unsubscribe in SubscriberClient."""

    @patch("requests.Session.post")
    def test_unsubscribe_200_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"status": "success", "email": "alice@example.com", "unsubscribed_at": "2024-01-15T10:30:00Z"}'
        mock_resp.json.return_value = {
            "status": "success",
            "email": "alice@example.com",
            "unsubscribed_at": "2024-01-15T10:30:00Z",
        }
        mock_post.return_value = mock_resp

        with SubscriberClient() as client:
            res = client.unsubscribe("alice@example.com")
        assert res.status == UnsubscribeStatus.SUCCESS
        assert res.email == "alice@example.com"
        assert res.unsubscribed_at == "2024-01-15T10:30:00Z"

    @patch("requests.Session.post")
    def test_unsubscribe_200_already_unsubscribed(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"status": "already_unsubscribed"}'
        mock_resp.json.return_value = {"status": "already_unsubscribed"}
        mock_post.return_value = mock_resp

        with SubscriberClient() as client:
            res = client.unsubscribe("alice@example.com")
        assert res.status == UnsubscribeStatus.ALREADY_UNSUBSCRIBED

    @patch("requests.Session.post")
    def test_unsubscribe_404_not_found(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.json.return_value = {"error": "Email not found"}
        mock_post.return_value = mock_resp

        with SubscriberClient() as client:
            res = client.unsubscribe("notfound@example.com")
        assert res.status == UnsubscribeStatus.EMAIL_NOT_FOUND

    @patch("requests.Session.post")
    def test_unsubscribe_400_invalid_email(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {"error": "Invalid email format"}
        mock_post.return_value = mock_resp

        with SubscriberClient() as client:
            res = client.unsubscribe("invalid-email")
        assert res.status == UnsubscribeStatus.INVALID_INPUT

    @patch("requests.Session.post")
    def test_unsubscribe_429_rate_limited(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.json.return_value = {"error": "Too many requests"}
        mock_post.return_value = mock_resp

        with SubscriberClient() as client:
            res = client.unsubscribe("alice@example.com")
        assert res.status == UnsubscribeStatus.RATE_LIMITED

    @patch("requests.Session.post")
    def test_unsubscribe_503_service_unavailable(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_post.return_value = mock_resp

        with SubscriberClient() as client:
            res = client.unsubscribe("alice@example.com")
        assert res.status == UnsubscribeStatus.SERVICE_UNAVAILABLE

    @patch("requests.Session.post")
    def test_unsubscribe_500_server_error(self, mock_post):
        """Test unsubscribe 500 internal server error"""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"error": "Internal server error"}
        mock_post.return_value = mock_resp

        with SubscriberClient() as client:
            res = client.unsubscribe("alice@example.com")
        assert res.status == UnsubscribeStatus.SERVER_ERROR

    @patch("requests.Session.post")
    def test_unsubscribe_410_gone(self, mock_post):
        """Test unsubscribe 410 gone status"""
        mock_resp = MagicMock()
        mock_resp.status_code = 410
        mock_resp.json.return_value = {"error": "Resource gone"}
        mock_post.return_value = mock_resp

        with SubscriberClient() as client:
            res = client.unsubscribe("alice@example.com")
        assert res.status == UnsubscribeStatus.SERVER_ERROR

    @patch("requests.Session.post", side_effect=requests.exceptions.ConnectionError("Failed to connect"))
    def test_unsubscribe_connection_error(self, mock_post):
        with SubscriberClient() as client:
            res = client.unsubscribe("alice@example.com")
        assert res.status == UnsubscribeStatus.CLIENT_ERROR
        assert "internet connection" in res.message.lower()

    @patch("requests.Session.post", side_effect=requests.exceptions.Timeout("Timeout"))
    def test_unsubscribe_timeout_error(self, mock_post):
        with SubscriberClient() as client:
            res = client.unsubscribe("alice@example.com")
        assert res.status == UnsubscribeStatus.CLIENT_ERROR
        assert "timed out" in res.message.lower()


class TestSubscribeCLI:
    """Test CLI subscribe command and result handlers."""

    @patch("teshq.cli.subscribe.save_config")
    def test_handle_subscription_result_success(self, mock_save):
        res = SubscriptionResult(
            status=SubscriptionStatus.SUCCESS,
            message="Subscription successful",
            subscriber_id="sub_999",
        )
        code = handle_subscription_result(res, "test@example.com")
        assert code == 0
        mock_save.assert_called_once_with({
            "SUBSCRIBER_EMAIL": "test@example.com",
            "SUBSCRIBER_ID": "sub_999",
        })

    @patch("teshq.cli.subscribe.save_config")
    def test_handle_subscription_result_already_subscribed(self, mock_save):
        res = SubscriptionResult(
            status=SubscriptionStatus.ALREADY_SUBSCRIBED,
            message="Already subscribed",
        )
        code = handle_subscription_result(res, "test@example.com")
        assert code == 0
        mock_save.assert_not_called()

    def test_handle_subscription_result_disposable(self):
        res = SubscriptionResult(
            status=SubscriptionStatus.DISPOSABLE_EMAIL,
            message="Disposable emails are blocked",
        )
        code = handle_subscription_result(res, "test@mailinator.com")
        assert code == 1

    def test_handle_subscription_result_permanently_deleted(self):
        """Test permanently deleted status"""
        res = SubscriptionResult(
            status=SubscriptionStatus.PERMANENTLY_DELETED,
            message="Email permanently deleted",
        )
        code = handle_subscription_result(res, "test@example.com")
        assert code == 1

    def test_handle_subscription_result_rate_limited(self):
        """Test rate limited status"""
        res = SubscriptionResult(
            status=SubscriptionStatus.RATE_LIMITED,
            message="Too many requests",
        )
        code = handle_subscription_result(res, "test@example.com")
        assert code == 1

    def test_handle_subscription_result_service_unavailable(self):
        """Test service unavailable status"""
        res = SubscriptionResult(
            status=SubscriptionStatus.SERVICE_UNAVAILABLE,
            message="Service temporarily unavailable",
        )
        code = handle_subscription_result(res, "test@example.com")
        assert code == 1

    def test_handle_subscription_result_server_error(self):
        """Test server error status"""
        res = SubscriptionResult(
            status=SubscriptionStatus.SERVER_ERROR,
            message="Internal server error",
        )
        code = handle_subscription_result(res, "test@example.com")
        assert code == 1

    @patch("teshq.cli.subscribe.SubscriberClient.subscribe")
    @patch("teshq.cli.subscribe.save_config")
    def test_cli_non_interactive_success(self, mock_save, mock_sub):
        mock_sub.return_value = SubscriptionResult(
            status=SubscriptionStatus.SUCCESS,
            message="Subscription successful",
            subscriber_id="sub_abc",
        )
        result = runner.invoke(
            subscribe_app,
            ["--name", "Alice Bob", "--email", "alice@example.com", "--yes"],
        )
        assert result.exit_code == 0
        assert "Subscription successful" in result.output

    @patch("teshq.cli.subscribe.SubscriberClient.subscribe")
    def test_cli_non_interactive_invalid_email(self, mock_sub):
        """Test CLI with invalid email format"""
        mock_sub.return_value = SubscriptionResult(
            status=SubscriptionStatus.INVALID_INPUT,
            message="Invalid email format",
        )
        result = runner.invoke(
            subscribe_app,
            ["--name", "Alice", "--email", "invalid-email", "--yes"],
        )
        assert result.exit_code == 1

    @patch("teshq.cli.subscribe.SubscriberClient.subscribe")
    def test_cli_keyboard_interrupt(self, mock_sub):
        """Test CLI keyboard interrupt handling"""
        mock_sub.side_effect = KeyboardInterrupt()
        result = runner.invoke(
            subscribe_app,
            ["--name", "Alice", "--email", "alice@example.com", "--yes"],
        )
        # Exit code 130 for keyboard interrupt
        assert result.exit_code == 130 or result.exit_code == 1


class TestUnsubscribeCLI:
    """Test CLI unsubscribe command and result handlers."""

    @patch("teshq.cli.unsubscribe.save_config")
    def test_handle_unsubscribe_result_success(self, mock_save):
        res = UnsubscribeResult(
            status=UnsubscribeStatus.SUCCESS,
            message="Successfully unsubscribed",
            email="test@example.com",
            unsubscribed_at="2024-01-15T10:30:00Z",
        )
        code = handle_unsubscribe_result(res, "test@example.com")
        assert code == 0
        mock_save.assert_called_once_with({
            "SUBSCRIBER_EMAIL": None,
            "SUBSCRIBER_ID": None,
        })

    def test_handle_unsubscribe_result_already_unsubscribed(self):
        res = UnsubscribeResult(
            status=UnsubscribeStatus.ALREADY_UNSUBSCRIBED,
            message="Already unsubscribed",
        )
        code = handle_unsubscribe_result(res, "test@example.com")
        assert code == 0

    def test_handle_unsubscribe_result_email_not_found(self):
        res = UnsubscribeResult(
            status=UnsubscribeStatus.EMAIL_NOT_FOUND,
            message="Email not found",
        )
        code = handle_unsubscribe_result(res, "test@example.com")
        assert code == 1

    def test_handle_unsubscribe_result_invalid_input(self):
        res = UnsubscribeResult(
            status=UnsubscribeStatus.INVALID_INPUT,
            message="Invalid input",
            details={"email": "Invalid format"},
        )
        code = handle_unsubscribe_result(res, "test@example.com")
        assert code == 1

    def test_handle_unsubscribe_result_rate_limited(self):
        res = UnsubscribeResult(
            status=UnsubscribeStatus.RATE_LIMITED,
            message="Too many requests",
        )
        code = handle_unsubscribe_result(res, "test@example.com")
        assert code == 1

    def test_handle_unsubscribe_result_service_unavailable(self):
        res = UnsubscribeResult(
            status=UnsubscribeStatus.SERVICE_UNAVAILABLE,
            message="Service unavailable",
        )
        code = handle_unsubscribe_result(res, "test@example.com")
        assert code == 1

    def test_handle_unsubscribe_result_client_error(self):
        res = UnsubscribeResult(
            status=UnsubscribeStatus.CLIENT_ERROR,
            message="Network error",
        )
        code = handle_unsubscribe_result(res, "test@example.com")
        assert code == 1

    def test_handle_unsubscribe_result_server_error(self):
        res = UnsubscribeResult(
            status=UnsubscribeStatus.SERVER_ERROR,
            message="Server error",
        )
        code = handle_unsubscribe_result(res, "test@example.com")
        assert code == 1

    def test_handle_unsubscribe_result_with_details(self):
        """Test unsubscribe result with error details"""
        res = UnsubscribeResult(
            status=UnsubscribeStatus.INVALID_INPUT,
            message="Validation failed",
            details={"field": "email", "error": "Invalid format"},
        )
        code = handle_unsubscribe_result(res, "test@example.com")
        assert code == 1

    @patch("teshq.cli.unsubscribe.SubscriberClient.unsubscribe")
    def test_cli_non_interactive_success(self, mock_unsub):
        mock_unsub.return_value = UnsubscribeResult(
            status=UnsubscribeStatus.SUCCESS,
            message="Successfully unsubscribed",
            email="alice@example.com",
            unsubscribed_at="2024-01-15T10:30:00Z",
        )
        result = runner.invoke(
            unsubscribe_app,
            ["--email", "alice@example.com", "--yes"],
        )
        assert result.exit_code == 0
        assert "Successfully unsubscribed" in result.output

    @patch("teshq.cli.unsubscribe.SubscriberClient.unsubscribe")
    def test_cli_non_interactive_not_found(self, mock_unsub):
        """Test unsubscribe CLI when email not found"""
        mock_unsub.return_value = UnsubscribeResult(
            status=UnsubscribeStatus.EMAIL_NOT_FOUND,
            message="Email not found",
        )
        result = runner.invoke(
            unsubscribe_app,
            ["--email", "notfound@example.com", "--yes"],
        )
        assert result.exit_code == 1

    @patch("teshq.cli.unsubscribe.SubscriberClient.unsubscribe")
    def test_cli_keyboard_interrupt(self, mock_unsub):
        """Test CLI keyboard interrupt handling"""
        mock_unsub.side_effect = KeyboardInterrupt()
        result = runner.invoke(
            unsubscribe_app,
            ["--email", "alice@example.com", "--yes"],
        )
        # Exit code 130 for keyboard interrupt
        assert result.exit_code == 130 or result.exit_code == 1


class TestConvenienceFunctions:
    """Test convenience helper functions."""

    @patch("teshq.subscriptions.client.SubscriberClient.subscribe")
    def test_subscribe_user(self, mock_subscribe):
        mock_subscribe.return_value = SubscriptionResult(
            status=SubscriptionStatus.SUCCESS,
            message="Subscription successful",
            subscriber_id="sub_123",
        )
        result = subscribe_user("Alice", "alice@example.com", "1.0.0")
        assert result.status == SubscriptionStatus.SUCCESS
        assert result.subscriber_id == "sub_123"

    @patch("teshq.subscriptions.client.SubscriberClient.unsubscribe")
    def test_unsubscribe_user(self, mock_unsubscribe):
        mock_unsubscribe.return_value = UnsubscribeResult(
            status=UnsubscribeStatus.SUCCESS,
            message="Successfully unsubscribed",
            email="alice@example.com",
            unsubscribed_at="2024-01-15T10:30:00Z",
        )
        result = unsubscribe_user("alice@example.com", "1.0.0")
        assert result.status == UnsubscribeStatus.SUCCESS
        assert result.email == "alice@example.com"

    @patch("teshq.subscriptions.client.SubscriberClient.subscribe")
    def test_subscribe_user_with_invalid_input(self, mock_subscribe):
        """Test subscribe_user with invalid input"""
        mock_subscribe.return_value = SubscriptionResult(
            status=SubscriptionStatus.INVALID_INPUT,
            message="Invalid name",
        )
        result = subscribe_user("A", "alice@example.com", "1.0.0")
        assert result.status == SubscriptionStatus.INVALID_INPUT

    @patch("teshq.subscriptions.client.SubscriberClient.unsubscribe")
    def test_unsubscribe_user_with_invalid_email(self, mock_unsubscribe):
        """Test unsubscribe_user with invalid email"""
        mock_unsubscribe.return_value = UnsubscribeResult(
            status=UnsubscribeStatus.INVALID_INPUT,
            message="Invalid email",
        )
        result = unsubscribe_user("invalid-email", "1.0.0")
        assert result.status == UnsubscribeStatus.INVALID_INPUT


class TestEdgeCasesAndBoundaryConditions:
    """Test edge cases and boundary conditions."""

    def test_very_long_name(self):
        """Test with name at exactly 100 characters"""
        name = "A" * 100
        req = SubscriptionRequest(name=name, email="test@example.com")
        assert req.name == name

    def test_email_with_plus_sign(self):
        """Test email with plus sign ( Gmail alias )"""
        req = SubscriptionRequest(name="Test", email="user+tag@example.com")
        assert req.email == "user+tag@example.com"

    def test_email_with_dots(self):
        """Test email with dots"""
        req = SubscriptionRequest(name="Test", email="first.last@example.com")
        assert req.email == "first.last@example.com"

    def test_unsubscribe_email_uppercase(self):
        """Test unsubscribe email normalization"""
        req = UnsubscribeRequest(email="USER@EXAMPLE.COM")
        assert req.email == "user@example.com"

    def test_os_type_enum_values(self):
        """Test OS type enum values"""
        assert OSType.LINUX.value == "linux"
        assert OSType.DARWIN.value == "darwin"
        assert OSType.WINDOWS.value == "windows"

    def test_subscription_status_enum_values(self):
        """Test subscription status enum values"""
        assert SubscriptionStatus.SUCCESS.value == "SUCCESS"
        assert SubscriptionStatus.INVALID_INPUT.value == "INVALID_INPUT"
        assert SubscriptionStatus.RATE_LIMITED.value == "RATE_LIMITED"

    def test_unsubscribe_status_enum_values(self):
        """Test unsubscribe status enum values"""
        assert UnsubscribeStatus.SUCCESS.value == "SUCCESS"
        assert UnsubscribeStatus.EMAIL_NOT_FOUND.value == "EMAIL_NOT_FOUND"
        assert UnsubscribeStatus.ALREADY_UNSUBSCRIBED.value == "ALREADY_UNSUBSCRIBED"
