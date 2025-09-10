from __future__ import annotations

"""Thin wrapper exposing :class:`SettingsPanel` from :mod:`gui_settings`.

The original module provided a large handcrafted settings UI.  In the
refactored version the interface is generated dynamically from
``settings_schema.json`` using :class:`gui_settings.SettingsPanel`.  This
module keeps backward compatible entry points used across the codebase and
in tests.
"""

from pathlib import Path
import json
import os
import tempfile
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


def _normalize_schema(schema: dict) -> dict:
    """Return schema with options wrapped into a default tab.

    Older schema formats exposed a flat ``options`` list without top-level
    ``tabs``.  The dynamic :class:`SettingsPanel` expects tab structures so the
    helper wraps such legacy definitions into a single tab with one group of
    fields.
    """

    if "tabs" not in schema and schema.get("options"):
        opts = schema.pop("options")
        schema["tabs"] = [
            {
                "id": "main",
                "title": "Ogólne",
                "groups": [{"label": "", "fields": opts}],
            }
        ]
    return schema


def panel_ustawien(
    root: tk.Misc,
    frame: tk.Widget,
    login=None,
    rola=None,
    config_path: str | None = None,
    schema_path: str | None = None,
):
    """Create settings panel inside ``frame``.

    The function mirrors the old signature but now normalizes the schema and
    wires variable traces so callers using legacy APIs continue to work.
    """

    clear_frame(frame)

    # ------------------------------------------------------------------
    # Load and normalize schema.  ``SettingsPanel`` expects a path so the
    # normalized content is written to a temporary file.
    schema_file = Path(schema_path or SCHEMA_PATH)
    with open(schema_file, encoding="utf-8") as f:
        schema = json.load(f)
    schema = _normalize_schema(schema)
    tmp = tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8")
    try:
        json.dump(schema, tmp, ensure_ascii=False, indent=2)
        tmp.close()
        panel = SettingsPanel(
            frame, config_path=config_path, schema_path=tmp.name
        )
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    # ``ProductsMaterialsTab`` is always appended by ``SettingsPanel``.  Remove
    # it unless explicitly requested either via schema tabs or config flag.
    include_tab = any(
        tab.get("title") == "Produkty i materiały"
        for tab in schema.get("tabs", [])
    ) or panel.cfg.get("include_products_tab", False)
    if not include_tab:
        for tab_id in panel.nb.tabs():
            if panel.nb.tab(tab_id, "text") == "Produkty i materiały":
                panel.nb.forget(tab_id)
                break

    # Track dirty state using variable traces.
    panel._dirty = False

    def _mark_dirty(*_args):
        panel._dirty = True

    for var in panel.vars.values():
        var.trace_add("write", _mark_dirty)

    # Intercept tab changes and window close to warn about unsaved changes.
    prev_tab = {"id": panel.nb.select()}

    def _on_tab_changed(event):
        if panel._dirty and not messagebox.askyesno(
            "Niezapisane zmiany",
            "Masz niezapisane zmiany. Kontynuować?",
            parent=panel.master,
        ):
            panel.nb.select(prev_tab["id"])
            return
        prev_tab["id"] = panel.nb.select()
        if hasattr(panel, "_on_tab_change"):
            panel._on_tab_change(event)

    panel.nb.bind("<<NotebookTabChanged>>", _on_tab_changed, add="+")

    orig_close = getattr(panel, "on_close", lambda: None)

    def _on_close():
        if panel._dirty and not messagebox.askyesno(
            "Niezapisane zmiany",
            "Masz niezapisane zmiany. Zamknąć bez zapisu?",
            parent=panel.master,
        ):
            return
        orig_close()

    panel.master.winfo_toplevel().protocol("WM_DELETE_WINDOW", _on_close)
    panel.on_close = _on_close

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
