"""Example tests for gcp."""

from pdum import gcp


def test_version():
    """Test that the package has a version."""
    assert hasattr(gcp, "__version__")
    assert isinstance(gcp.__version__, str)
    assert len(gcp.__version__) > 0


def test_import():
    """Test that the package can be imported."""
    assert gcp is not None


