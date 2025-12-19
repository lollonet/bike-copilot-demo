def test_app_imports():
    """Verify core app modules can be imported."""
    try:
        from app import models
    except ImportError:
        assert False, "Failed to import app.models"
    assert models is not None
