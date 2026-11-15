"""Smoke tests: the package installs, imports and reports its version."""

from importlib.metadata import version

import mia


def test_package_imports() -> None:
    assert mia.__name__ == "mia"


def test_version_matches_pyproject() -> None:
    assert mia.__version__ == "0.1.0"
    assert mia.__version__ == version("mia")
