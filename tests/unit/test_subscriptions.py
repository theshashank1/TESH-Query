"""
Unit tests for TESHQ subscription client and CLI.
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
