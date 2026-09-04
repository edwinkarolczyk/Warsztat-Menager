"""Globalny znak wodny WM: PROGRAM W TRAKCIE ROZWOJU.
# Plik: wm_watermark.py
# Wersja: 1.0.4 SAFE
# Zmiany 1.0.4:
# - Hook po zbudowaniu panelu dopina izolowany przycisk „Samouczek” pod modułami.
# Zmiany 1.0.3:
# - Bezpieczny hook po zbudowaniu panelu uruchamia centralną kartę logowania,
#   gdy panel działa jako Gość. Sam znak wodny pozostaje wyłączony.
# Zmiany 1.0.2:
# - Tymczasowo wyłączono warstwę Toplevel odpowiedzialną za znak wodny.
# - Powód: na części stanowisk Windows warstwa zasłaniała cały WM lub pokazywała czarny ekran.
# - Zachowano odczyt i zapis ustawienia ui.show_development_watermark.
# - install() pozostaje kompatybilne z gui_panel.py, ale nie tworzy żadnego okna ani timera.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

KEY = "ui.show_development_watermark"
DEFAULT_ENABLED = True
TEXT = "PROGRAM W TRAKCIE ROZWOJU"


def _config_path() -> Path:
    env = os.environ.get("WM_CONFIG_FILE")
    return Path(env).expanduser() if env else Path("config.json")


def _read_enabled() -> bool:
    try:
        path = _config_path()
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        value = (data.get("ui") or {}).get(KEY.split(".", 1)[1], DEFAULT_ENABLED)
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)
    except Exception:
        return DEFAULT_ENABLED


def set_enabled(enabled: bool) -> bool:
    """Zapisz ustawienie znaku wodnego bez tworzenia warstwy GUI."""
    try:
        path = _config_path()
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        if not isinstance(data, dict):
            data = {}
        ui = data.setdefault("ui", {})
        if not isinstance(ui, dict):
            ui = {}
            data["ui"] = ui
        ui[KEY.split(".", 1)[1]] = bool(enabled)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return True
    except Exception:
        return False


class DevelopmentWatermark:
    """Bezpieczny placeholder do czasu wdrożenia znaku wodnego bez Toplevel."""

    def __init__(self, root):
        self.root = root
        self.enabled = _read_enabled()

    def refresh(self) -> None:
        self.enabled = _read_enabled()

    def destroy(self) -> None:
        return None


def _install_guest_login(root) -> None:
    """Uruchom integralną kartę logowania wyłącznie dla panelu Gościa."""
    try:
        from panel_guest_login_runtime import install_guest_login_card

        install_guest_login_card(root)
    except Exception:
        # Logowanie w prawym górnym rogu pozostaje wtedy dostępne,
        # więc ten dodatek nie może zablokować panelu.
        pass


def _install_tutorial_entry(root) -> None:
    """Dopnij niezależny przycisk samouczka po zbudowaniu głównego panelu."""
    try:
        from panel_tutorial_runtime import install_tutorial_button

        install_tutorial_button(root)
    except Exception:
        # Samouczek jest dodatkiem; jego błąd nie może blokować startu WM.
        pass


def install(root) -> DevelopmentWatermark:
    """Zachowaj zgodność API bez tworzenia warstwy znaku wodnego."""
    existing = getattr(root, "_wm_development_watermark", None)
    if existing is not None:
        try:
            existing.refresh()
        except Exception:
            pass
        _install_guest_login(root)
        _install_tutorial_entry(root)
        return existing

    overlay = DevelopmentWatermark(root)
    try:
        setattr(root, "_wm_development_watermark", overlay)
    except Exception:
        pass
    _install_guest_login(root)
    _install_tutorial_entry(root)
    return overlay
