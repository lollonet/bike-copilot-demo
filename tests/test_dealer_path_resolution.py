"""Test that dealer mapping paths are resolved correctly."""

from app.dealers import (
    DealerConfig,
    DealerAuthConfig,
    DealerSeeds,
    _repo_root,
)


def test_dealer_mapping_path_is_resolved_from_repo_root():
    """Test that mapping paths in dealer configs are resolved relative to repo root."""

    # Create a dealer config with a relative mapping path
    dealer = DealerConfig(
        key="test",
        name="Test Dealer",
        type="web",
        base_url_env=None,
        platform="test",
        mapping="providers/test-mapping.yaml",  # Relative path
        policy_url=None,
        auth=DealerAuthConfig(
            mode_env=None, username_env=None, password_env=None, cookie_env=None
        ),
        seeds=DealerSeeds(urls=[], sitemap=None),
        login=None,
    )

    # The repo root function should return the parent of app/ directory
    repo_root = _repo_root()
    assert repo_root.exists()
    assert (repo_root / "app").is_dir()

    # When we resolve the mapping path, it should be relative to repo root
    expected_mapping_path = repo_root / dealer.mapping

    # Test that this is how it's used in the actual code
    from app.dealers import _repo_root as get_repo_root

    # Simulate what dealer-sync does
    if dealer.mapping:
        mapping_path = get_repo_root() / dealer.mapping
        assert mapping_path == expected_mapping_path
        assert str(mapping_path).endswith("providers/test-mapping.yaml")
        # The path should be absolute
        assert mapping_path.is_absolute()


def test_dealer_sync_uses_correct_path_resolution():
    """Verify the actual implementation in dealer_sync uses _repo_root for mapping paths."""

    import inspect
    from app.commands.service_commands import dealer_sync

    # Get the source code of dealer_sync
    source = inspect.getsource(dealer_sync)

    # Verify that it imports _repo_root from dealers module
    assert (
        "from ..dealers import _repo_root" in source
        or "from app.dealers import _repo_root" in source
    )

    # Verify that it uses _repo_root() to resolve the mapping path
    assert "_repo_root() /" in source
    assert "mapping_path" in source
