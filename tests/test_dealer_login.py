"""Test dealer login functionality to ensure no undefined variables."""

from unittest.mock import Mock, patch
import pytest
import typer

from app.dealers import (
    DealerConfig,
    DealerAuthConfig,
    DealerSeeds,
    DealerLoginConfig,
)


def test_form_login_get_method_uses_query_params():
    """Test that GET form login correctly builds query parameters."""
    from app.cli import _build_dealer_session

    dealer = DealerConfig(
        key="test",
        name="Test Dealer",
        type="web",
        base_url_env=None,
        platform="test",
        mapping=None,
        policy_url=None,
        auth=DealerAuthConfig(
            mode_env="DEALER_TEST_AUTH_MODE",
            username_env="DEALER_TEST_USER",
            password_env="DEALER_TEST_PASS",
            cookie_env=None,
        ),
        seeds=DealerSeeds(urls=[], sitemap=None),
        login=DealerLoginConfig(
            mode="form",
            url="https://example.com/login",
            method="GET",
            username_field="user",
            password_field="pass",
            extra_fields={"remember": "1", "redirect": "/dashboard"},
        ),
    )

    # Mock environment variables
    with patch("app.cli.os.getenv") as mock_getenv:
        mock_getenv.side_effect = lambda key, default="": {
            "DEALER_TEST_AUTH_MODE": "form",
            "DEALER_TEST_USER": "testuser",
            "DEALER_TEST_PASS": "testpass",
        }.get(key, default)

        # Mock httpx.Client to verify the correct params are passed
        with patch("app.cli.httpx.Client") as mock_client_class:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response
            mock_client.post.return_value = mock_response
            mock_client.headers = {}
            mock_client_class.return_value = mock_client

            # Build the session - this should not raise NameError
            _build_dealer_session(dealer)

            # Verify GET was called with correct params
            mock_client.get.assert_called_once()
            call_args = mock_client.get.call_args

            # Check that params were passed correctly
            expected_params = {
                "remember": "1",
                "redirect": "/dashboard",
                "user": "testuser",
                "pass": "testpass",
            }
            assert call_args[0][0] == "https://example.com/login"
            assert call_args[1]["params"] == expected_params


def test_form_login_post_method_uses_form_data():
    """Test that POST form login correctly builds form data."""
    from app.cli import _build_dealer_session

    dealer = DealerConfig(
        key="test",
        name="Test Dealer",
        type="web",
        base_url_env=None,
        platform="test",
        mapping=None,
        policy_url=None,
        auth=DealerAuthConfig(
            mode_env="DEALER_TEST_AUTH_MODE",
            username_env="DEALER_TEST_USER",
            password_env="DEALER_TEST_PASS",
            cookie_env=None,
        ),
        seeds=DealerSeeds(urls=[], sitemap=None),
        login=DealerLoginConfig(
            mode="form",
            url="https://example.com/login",
            method="POST",
            username_field="username",
            password_field="password",
            extra_fields={"csrf_token": "abc123"},
        ),
    )

    with patch("app.cli.os.getenv") as mock_getenv:
        mock_getenv.side_effect = lambda key, default="": {
            "DEALER_TEST_AUTH_MODE": "form",
            "DEALER_TEST_USER": "testuser",
            "DEALER_TEST_PASS": "testpass",
        }.get(key, default)

        with patch("app.cli.httpx.Client") as mock_client_class:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.post.return_value = mock_response
            mock_client.headers = {}
            mock_client_class.return_value = mock_client

            # Build the session
            _build_dealer_session(dealer)

            # Verify POST was called with form data
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args

            assert call_args[0][0] == "https://example.com/login"
            # Form data is passed as 'data' parameter
            assert "data" in call_args[1]


def test_unsupported_login_method_raises_error():
    """Test that unsupported login methods raise appropriate errors."""
    from app.cli import _build_dealer_session

    dealer = DealerConfig(
        key="test",
        name="Test Dealer",
        type="web",
        base_url_env=None,
        platform="test",
        mapping=None,
        policy_url=None,
        auth=DealerAuthConfig(
            mode_env="DEALER_TEST_AUTH_MODE",
            username_env="DEALER_TEST_USER",
            password_env="DEALER_TEST_PASS",
            cookie_env=None,
        ),
        seeds=DealerSeeds(urls=[], sitemap=None),
        login=DealerLoginConfig(
            mode="form",
            url="https://example.com/login",
            method="PUT",  # Unsupported method
            username_field="user",
            password_field="pass",
            extra_fields={},
        ),
    )

    with patch("app.cli.os.getenv") as mock_getenv:
        mock_getenv.side_effect = lambda key, default="": {
            "DEALER_TEST_AUTH_MODE": "form",
            "DEALER_TEST_USER": "testuser",
            "DEALER_TEST_PASS": "testpass",
        }.get(key, default)

        with patch("app.cli.httpx.Client") as mock_client_class:
            mock_client = Mock()
            mock_client.headers = {}
            mock_client_class.return_value = mock_client

            with pytest.raises(typer.BadParameter) as exc_info:
                _build_dealer_session(dealer)

            assert "PUT non supportato" in str(exc_info.value)
