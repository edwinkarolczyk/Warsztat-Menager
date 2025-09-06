"""Compatibility wrapper for the previous settings panel implementation.

This module re-exports all public symbols from :mod:`gui_settings` so that
legacy tests and code relying on the old module name continue to work.
"""

from gui_settings import *  # noqa: F401,F403

