"""
Unit tests for TESHQ subscription client and CLI.
"""

from unittest.mock import MagicMock, patch
import pytest
import requests
from pydantic import ValidationError
from typer.testing import CliRunner

from teshq.cli.subscribe import app, handle_subscription_result
from teshq.subscriptions.client import (
    OSType,
    SubscriberClient,
    SubscriptionRequest,
    SubscriptionResponse,
    SubscriptionResult,
    SubscriptionStatus,
    subscribe_user,
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
            app,
            ["--name", "Alice Bob", "--email", "alice@example.com", "--yes"],
        )
        assert result.exit_code == 0
        assert "Subscription successful" in result.output
