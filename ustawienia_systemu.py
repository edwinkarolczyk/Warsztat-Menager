from __future__ import annotations

"""Thin wrapper exposing :class:`SettingsPanel` from :mod:`gui_settings`.

The original module provided a large handcrafted settings UI.  In the
refactored version the interface is generated dynamically from
``settings_schema.json`` using :class:`gui_settings.SettingsPanel`.  This
module keeps backward compatible entry points used across the codebase and
in tests.
"""

from pathlib import Path
import tkinter as tk
from tkinter import ttk

from config_manager import ConfigManager
from gui_settings import SettingsPanel, messagebox
from utils.gui_helpers import clear_frame

# Path kept for tests that monkeypatch ``SCHEMA_PATH``.
SCHEMA_PATH = Path(__file__).with_name("settings_schema.json")


def apply_theme(*_args, **_kwargs) -> None:  # pragma: no cover - stub
    """Compatibility stub for the old theming helper."""
    pass


def _lines_from_text(widget: tk.Text) -> list[str]:
    """Return non-empty stripped lines from a ``tk.Text`` widget.

    This helper is retained for backward compatibility and is used in tests.
    """

    try:
        return [
            ln.strip()
            for ln in widget.get("1.0", "end").splitlines()
            if ln.strip()
        ]
    except tk.TclError:
        return []


def panel_ustawien(
    root: tk.Misc,
    frame: tk.Widget,
    login=None,
    rola=None,
    config_path: str | None = None,
    schema_path: str | None = None,
):
    """Create settings panel inside ``frame``.

    Parameters match the signature of the legacy implementation so that
    callers do not need to change.
    """

    clear_frame(frame)
    SettingsPanel(frame, config_path=config_path, schema_path=schema_path)
    return frame


def refresh_panel(
    root: tk.Misc,
    frame: tk.Widget,
    login=None,
    rola=None,
    config_path: str | None = None,
    schema_path: str | None = None,
):
    """Reload configuration and rebuild the settings panel."""

    ConfigManager.refresh(config_path=config_path, schema_path=schema_path)
    panel_ustawien(
        root,
        frame,
        login,
        rola,
        config_path=config_path,
        schema_path=schema_path,
    )
