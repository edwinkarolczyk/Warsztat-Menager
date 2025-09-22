"""Compatibility shim exposing helpers from the tests package."""

from tests.test_config_manager import make_manager  # noqa: F401

__all__ = ["make_manager"]
