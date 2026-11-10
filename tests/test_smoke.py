"""Smoke test: the package is installed and importable from the src layout."""

import agora


def test_package_exposes_version() -> None:
    assert agora.__version__ == "0.1.0"
