import sys
from pathlib import Path

import pytest

# Ensure repo root is on sys.path for `import app`
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add --run-integration option to pytest."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests (requires network and credentials)",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip integration tests unless --run-integration is passed."""
    if config.getoption("--run-integration"):
        # Run all tests including integration
        return

    skip_integration = pytest.mark.skip(
        reason="Need --run-integration option to run"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
