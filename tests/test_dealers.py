"""Test dealer registry functionality."""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from app.dealers import (
    DealerAuthConfig,
    DealerSeeds,
    DealerConfig,
    load_dealers,
    find_dealer,
    _dealers_yaml_path,
)


def test_dealer_config_dataclasses():
    """Test that dealer dataclasses are properly frozen and structured."""
    auth = DealerAuthConfig(
        mode_env="TEST_MODE",
        username_env="TEST_USER",
        password_env="TEST_PASS",
        cookie_env="TEST_COOKIE",
    )
    assert auth.mode_env == "TEST_MODE"
    assert auth.username_env == "TEST_USER"

    # Test frozen behavior
    with pytest.raises(AttributeError):
        auth.mode_env = "CHANGED"

    seeds = DealerSeeds(
        urls=["http://test.com/page1", "http://test.com/page2"],
        sitemap="http://test.com/sitemap.xml",
    )
    assert len(seeds.urls) == 2
    assert seeds.sitemap == "http://test.com/sitemap.xml"

    config = DealerConfig(
        key="test",
        name="Test Dealer",
        type="web",
        base_url_env="TEST_BASE_URL",
        platform="custom",
        mapping="providers/test.yaml",
        policy_url="http://test.com/policy",
        auth=auth,
        seeds=seeds,
        login=None,
    )
    assert config.key == "test"
    assert config.name == "Test Dealer"
    assert config.auth.cookie_env == "TEST_COOKIE"


def test_load_dealers_from_yaml(tmp_path: Path):
    """Test loading dealers from a YAML file."""
    yaml_content = {
        "dealers": [
            {
                "key": "dealer1",
                "name": "Dealer One",
                "type": "web",
                "base_url_env": "DEALER1_URL",
                "platform": "woocommerce",
                "mapping": "providers/dealer1.yaml",
                "policy_url": "http://dealer1.com/shipping",
                "auth": {
                    "mode_env": "DEALER1_AUTH_MODE",
                    "username_env": "DEALER1_USER",
                    "password_env": "DEALER1_PASS",
                    "cookie_env": "DEALER1_COOKIE",
                },
                "seeds": {
                    "urls": ["http://dealer1.com/products"],
                    "sitemap": "http://dealer1.com/sitemap.xml",
                },
                "login": None,
            },
            {
                "key": "dealer2",
                "name": "Dealer Two",
                "type": "csv",
                "auth": {},
                "seeds": {},
                "login": None,
            },
        ]
    }

    yaml_file = tmp_path / "providers" / "dealers.yaml"
    yaml_file.parent.mkdir(parents=True)
    yaml_file.write_text(yaml.dump(yaml_content))

    with patch("app.dealers._dealers_yaml_path", return_value=yaml_file):
        dealers = load_dealers()

    assert len(dealers) == 2

    # Check first dealer
    d1 = dealers[0]
    assert d1.key == "dealer1"
    assert d1.name == "Dealer One"
    assert d1.type == "web"
    assert d1.platform == "woocommerce"
    assert d1.mapping == "providers/dealer1.yaml"
    assert d1.policy_url == "http://dealer1.com/shipping"
    assert d1.auth.mode_env == "DEALER1_AUTH_MODE"
    assert d1.auth.username_env == "DEALER1_USER"
    assert d1.seeds.urls == ["http://dealer1.com/products"]
    assert d1.seeds.sitemap == "http://dealer1.com/sitemap.xml"

    # Check second dealer with minimal config
    d2 = dealers[1]
    assert d2.key == "dealer2"
    assert d2.name == "Dealer Two"
    assert d2.type == "csv"
    assert d2.auth.mode_env is None
    assert d2.seeds.urls == []


def test_load_dealers_missing_file():
    """Test loading dealers when file doesn't exist."""
    with patch(
        "app.dealers._dealers_yaml_path", return_value=Path("/nonexistent/dealers.yaml")
    ):
        dealers = load_dealers()
        assert dealers == []


def test_load_dealers_invalid_yaml(tmp_path: Path):
    """Test error handling for invalid YAML structure."""
    yaml_file = tmp_path / "dealers.yaml"

    # Test non-dict root
    yaml_file.write_text("- item1\n- item2")
    with patch("app.dealers._dealers_yaml_path", return_value=yaml_file):
        with pytest.raises(ValueError, match="root must be a mapping"):
            load_dealers()

    # Test dealers not being a list
    yaml_file.write_text("dealers: not_a_list")
    with patch("app.dealers._dealers_yaml_path", return_value=yaml_file):
        with pytest.raises(ValueError, match="dealers must be a list"):
            load_dealers()


def test_find_dealer(tmp_path: Path):
    """Test finding dealers by key or name."""
    yaml_content = {
        "dealers": [
            {"key": "rms", "name": "RMS Italia"},
            {"key": "ciclo", "name": "CicloDiffusione"},
            {"key": "promo", "name": "CicloPromo"},
        ]
    }

    yaml_file = tmp_path / "dealers.yaml"
    yaml_file.write_text(yaml.dump(yaml_content))

    with patch("app.dealers._dealers_yaml_path", return_value=yaml_file):
        # Find by exact key
        dealer = find_dealer("rms")
        assert dealer is not None
        assert dealer.key == "rms"
        assert dealer.name == "RMS Italia"

        # Find by key case-insensitive
        dealer = find_dealer("RMS")
        assert dealer is not None
        assert dealer.key == "rms"

        # Find by name
        dealer = find_dealer("CicloDiffusione")
        assert dealer is not None
        assert dealer.key == "ciclo"

        # Find by name case-insensitive
        dealer = find_dealer("ciclodiffusione")
        assert dealer is not None
        assert dealer.key == "ciclo"

        # Not found
        dealer = find_dealer("nonexistent")
        assert dealer is None


def test_dealer_config_defaults(tmp_path: Path):
    """Test that missing fields get proper defaults."""
    yaml_content = {
        "dealers": [
            {
                "key": "minimal",
                # Everything else should get defaults
            }
        ]
    }

    yaml_file = tmp_path / "dealers.yaml"
    yaml_file.write_text(yaml.dump(yaml_content))

    with patch("app.dealers._dealers_yaml_path", return_value=yaml_file):
        dealers = load_dealers()
        assert len(dealers) == 1

        d = dealers[0]
        assert d.key == "minimal"
        assert d.name == "minimal"  # defaults to key
        assert d.type == "web"  # default type
        assert d.base_url_env is None
        assert d.platform is None
        assert d.mapping is None
        assert d.policy_url is None
        assert d.auth.mode_env is None
        assert d.auth.username_env is None
        assert d.auth.password_env is None
        assert d.auth.cookie_env is None
        assert d.seeds.urls == []
        assert d.seeds.sitemap is None


def test_dealer_seeds_urls_parsing(tmp_path: Path):
    """Test that seed URLs are properly parsed from various formats."""
    yaml_content = {
        "dealers": [
            {
                "key": "test",
                "seeds": {
                    "urls": [
                        "http://example.com/page1",
                        "http://example.com/page2",
                        123,  # Should be converted to string
                    ]
                },
            }
        ]
    }

    yaml_file = tmp_path / "dealers.yaml"
    yaml_file.write_text(yaml.dump(yaml_content))

    with patch("app.dealers._dealers_yaml_path", return_value=yaml_file):
        dealers = load_dealers()
        assert len(dealers[0].seeds.urls) == 3
        assert dealers[0].seeds.urls[2] == "123"


def test_actual_dealers_yaml_loads():
    """Test that the actual dealers.yaml file loads without errors."""
    # This test uses the real dealers.yaml file if it exists
    yaml_path = _dealers_yaml_path()
    if yaml_path.is_file():
        dealers = load_dealers()

        # Verify expected dealers are present
        keys = {d.key for d in dealers}
        assert "rms" in keys
        assert "ciclodiffusione" in keys
        assert "ciclopromo" in keys
        assert "bikeparts" in keys

        # Verify CicloPromo has seed URLs as expected
        ciclopromo = find_dealer("ciclopromo")
        assert ciclopromo is not None
        assert len(ciclopromo.seeds.urls) > 0
        assert ciclopromo.mapping == "providers/web-ciclopromo.yaml"
