"""Alias do edytora zaawansowanego Narzędzi (fallback na prosty edytor JSON)."""

from __future__ import annotations

from ui_theme import ensure_theme_applied


def _can_use_advanced_dialog() -> bool:
    """Sprawdź, czy środowisko pozwala na użycie wersji zaawansowanej."""

    try:
        import tkinter as _tk  # lokalny import: zależy od środowiska testowego
    except Exception:
        return False

    default_root = getattr(_tk, "_default_root", None)
    if default_root is not None:
        return True

    try:
        root = _tk.Tk()
    except Exception:
        return False

    try:
        root.withdraw()
        root.destroy()
    except Exception:
        return False
    return True


_AdvancedDialog = None
try:
    from gui_tools_config_advanced import ToolsConfigDialog as _AdvancedDialog  # type: ignore
except Exception:
    _AdvancedDialog = None

if _AdvancedDialog is not None and _can_use_advanced_dialog():
    ToolsConfigDialog = _AdvancedDialog
    print("[WM-DBG] gui_tools_config: używam wersji advanced")
else:
    print("[WM-DBG] gui_tools_config: fallback na prosty edytor JSON")

    import json
    import tkinter as tk
    from tkinter import messagebox, ttk

    class ToolsConfigDialog(tk.Toplevel):
        """Minimalne okno do edycji pliku ``zadania_narzedzia.json``."""

        def __init__(self, master: tk.Widget | None = None, *, path: str, on_save=None) -> None:
            super().__init__(master)
            ensure_theme_applied(self)
            self.title("Konfiguracja zadań narzędzi")
            self.resizable(True, True)
            self.path = path
            self.on_save = on_save

            self.text = tk.Text(self, width=80, height=25)
            self.text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

            buttons = ttk.Frame(self)
            buttons.pack(fill=tk.X, padx=4, pady=(0, 4))
            ttk.Button(buttons, text="Zapisz", command=self._save).pack(side=tk.LEFT)
            ttk.Button(buttons, text="Anuluj", command=self.destroy).pack(side=tk.LEFT)

            try:
                with open(self.path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except FileNotFoundError:
                data = {"collections": {}}
            self.text.insert("1.0", json.dumps(data, ensure_ascii=False, indent=2))

        def _save(self) -> None:
            """Zapisz plik i wywołaj ``on_save`` po sukcesie."""

            raw = self.text.get("1.0", tk.END).strip()
            try:
                json.loads(raw)
            except json.JSONDecodeError as exc:
                messagebox.showerror("Błąd", f"Niepoprawny JSON: {exc}")
                return

            with open(self.path, "w", encoding="utf-8") as fh:
                fh.write(raw + ("\n" if not raw.endswith("\n") else ""))

            try:
                from logika_zadan import invalidate_cache
            except Exception:
                invalidate_cache = None  # pragma: no cover
            if callable(invalidate_cache):
                invalidate_cache()

            if callable(self.on_save):
                self.on_save()
            self.destroy()
