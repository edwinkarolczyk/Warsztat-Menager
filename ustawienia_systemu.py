# WM-VERSION: 0.1
# version: 1.7
# Zmiany 1.7:
# - Domknięto integrację Ustawień: wspólny stan zmian i ukrycie martwej zakładki Zamówienia.
# Zmiany 1.6:
# - Podłączono porządkowanie Narzędzi, Zleceń, Użytkowników/Profilu i wspólny UX Ustawień.
# - Dodano wyszukiwarkę, domyślne dla sekcji, kalendarz daty rotacji i wspólny zapis Dyspozycji.
# - Poprawiono leniwe ładowanie Moduły → Magazyn oraz rozmieszczenie Backup/Aktualizacje.
# Zmiany 1.5:
# - Podłączono porządkowanie Ustawienia → Moduły → Maszyny.
# Zmiany 1.4:
# - Podłączono wybierany z Ustawień motyw Świąteczny z centralnego ui_theme.
# Zmiany 1.3:
# - Dodano zamykane podpowiedzi „?” przy trudniejszych pozycjach Ustawień.
# Zmiany 1.2:
# - Włączono porządkowanie Ustawień: Moduły → Główne, ukrycie Jarvisa,
#   rozdzielenie Wygląd/Logika w Dyspozycjach, wybór timeoutu i podgląd kolorów.
# Zmiany 1.1:
# - Włączono UI-only podgląd wyglądu oraz wybór kolorów z próbką i przywracaniem wartości domyślnej.
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
from christmas_theme_runtime import install_christmas_theme_runtime
from settings_color_preview_runtime import install_settings_color_preview_runtime
from settings_structure_runtime import install_settings_structure_runtime
from settings_machines_runtime import install_settings_machines_runtime
from settings_tools_runtime import install_settings_tools_runtime
from settings_orders_runtime import install_settings_orders_runtime
from settings_users_runtime import install_settings_users_runtime
from settings_common_runtime import install_settings_common_runtime
from settings_unused_runtime import install_settings_unused_runtime
from settings_help_runtime import install_settings_help_runtime
from utils.gui_helpers import clear_frame


def _wm_mark_settings_dirty(self) -> None:
    """Wspólne oznaczenie zmian używane przez nowe kontrolki Ustawień."""
    self._dirty = True
    self._unsaved = True
    marker = getattr(self, "_mark_save_dirty", None)
    if callable(marker):
        try:
            marker()
        except Exception:
            pass


# Stary SettingsPanel nie miał publicznego helpera o tej nazwie; runtime'y UI
# korzystają z niego, aby zachować identyczne zachowanie paska „Zapisz wszystko”.
if not hasattr(SettingsPanel, "_mark_dirty"):
    SettingsPanel._mark_dirty = _wm_mark_settings_dirty

# Kolejność ma znaczenie: najpierw podstawowa struktura i moduły, potem elementy
# wspólne, usunięcie martwych sekcji, a podpowiedzi „?” dopiero na gotowym układzie.
install_settings_color_preview_runtime(SettingsPanel)
install_settings_structure_runtime(SettingsPanel)
install_settings_machines_runtime(SettingsPanel)
install_settings_tools_runtime(SettingsPanel)
install_settings_orders_runtime(SettingsPanel)
install_settings_users_runtime(SettingsPanel)
install_settings_common_runtime(SettingsPanel)
install_settings_unused_runtime(SettingsPanel)
install_settings_help_runtime(SettingsPanel)
install_christmas_theme_runtime(SettingsPanel)

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
    ``tabs``.  The dynamic :class:`gui_settings.SettingsPanel` expects tab structures so the
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

    try:
        from gui_panel import wm_set_module_source

        detected_config_path = os.environ.get("WM_CONFIG_FILE")
        if not detected_config_path:
            try:
                from start import CONFIG_MANAGER

                detected_config_path = str(
                    getattr(CONFIG_MANAGER, "config_path", "") or ""
                )
            except Exception:
                detected_config_path = ""
        wm_set_module_source(root, "Ustawienia", detected_config_path)
    except Exception:
        pass

    clear_frame(frame)

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

    include_tab = any(
        tab.get("title") == "Produkty i materiały"
        for tab in schema.get("tabs", [])
    ) or panel.cfg.get("include_products_tab", False)
    if not include_tab:
        for tab_id in panel.nb.tabs():
            if panel.nb.tab(tab_id, "text") == "Produkty i materiały":
                panel.nb.forget(tab_id)
                break

    panel._dirty = False

    def _mark_dirty(*_args):
        panel._dirty = True

    for var in panel.vars.values():
        var.trace_add("write", _mark_dirty)

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
