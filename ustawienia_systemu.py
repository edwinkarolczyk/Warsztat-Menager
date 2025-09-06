from __future__ import annotations

"""Compatibility wrapper for the legacy settings panel.

Historic versions exposed a handcrafted settings UI through this module.
The current implementation builds the interface from
``settings_schema.json`` and makes it available via
:class:`gui_settings.SettingsWindow`.
Import and instantiate ``SettingsWindow`` directly; the helpers in this
module exist solely for backward compatibility with old imports and
tests.
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


def panel_ustawien(root: tk.Misc, frame: tk.Widget, login=None, rola=None):
    """Create settings panel inside ``frame``.

    Parameters match the signature of the legacy implementation so that
    callers do not need to change.
    """

    clear_frame(frame)
    SettingsPanel(frame)
    return frame


def refresh_panel(root: tk.Misc, frame: tk.Widget, login=None, rola=None):
    """Reload configuration and rebuild the settings panel."""

    ConfigManager.refresh()
    panel_ustawien(root, frame, login, rola)
