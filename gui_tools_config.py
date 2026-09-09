# version: 1.1
# Zmiany 1.1:
# - Edytor advanced pozwala wskazać dokładnie jeden status bazowy wizyty dla typu.
# - Status bazowy jest zapisywany jako visit_base=true; pozostałe tracą tę flagę.
# - Stare definicje bez flagi zachowują pierwszy status jako domyślny fallback.
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
    import tkinter as tk
    from tkinter import messagebox, ttk

    class ToolsConfigDialog(_AdvancedDialog):
        """Advanced editor extended with an explicit visit-base status selector."""

        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)

            self._visit_base_var = tk.StringVar(value="Status bazowy wizyty: —")
            base_frame = ttk.Frame(self)
            base_frame.pack(fill="x", padx=6, pady=(0, 6))
            ttk.Label(base_frame, textvariable=self._visit_base_var).pack(
                side="left", padx=(0, 10)
            )
            ttk.Button(
                base_frame,
                text="Ustaw jako bazowy",
                command=self._set_selected_visit_base,
            ).pack(side="left")
            ttk.Label(
                base_frame,
                text="  Bazowy → inny: start wizyty | inny → bazowy: koniec wizyty",
            ).pack(side="left", padx=(10, 0))
            self._update_visit_base_label()

        def _current_statuses(self) -> list[dict]:
            type_idx = self._selected_type_true_index()
            if type_idx is None:
                return []
            try:
                return self._get_statuses_for_current(type_idx)
            except Exception:
                return []

        @staticmethod
        def _base_index(statuses: list[dict]) -> int | None:
            if not statuses:
                return None
            for idx, status in enumerate(statuses):
                if bool(status.get("visit_base")):
                    return idx
            # Wsteczna kompatybilność: przed wprowadzeniem visit_base bazowy
            # był pierwszy status z listy.
            return 0

        def _ensure_visit_base_integrity(self) -> None:
            """Gwarantuj najwyżej jedną flagę visit_base w każdym typie."""

            collections = (self._data or {}).get("collections") or {}
            for coll in collections.values():
                if not isinstance(coll, dict):
                    continue
                for tool_type in coll.get("types") or []:
                    if not isinstance(tool_type, dict):
                        continue
                    statuses = tool_type.get("statuses") or []
                    if not isinstance(statuses, list) or not statuses:
                        continue
                    marked = [
                        idx
                        for idx, status in enumerate(statuses)
                        if isinstance(status, dict) and bool(status.get("visit_base"))
                    ]
                    if not marked:
                        # Nie zapisujemy automatycznie fallbacku przy samym otwarciu.
                        # Zostanie zapisany przy kolejnej zmianie / kliknięciu Zapisz.
                        marked = [0]
                    keep = marked[0]
                    for idx, status in enumerate(statuses):
                        if not isinstance(status, dict):
                            continue
                        if idx == keep:
                            status["visit_base"] = True
                        else:
                            status.pop("visit_base", None)

        def _update_visit_base_label(self) -> None:
            var = getattr(self, "_visit_base_var", None)
            if var is None:
                return
            statuses = self._current_statuses()
            base_idx = self._base_index(statuses)
            if base_idx is None:
                var.set("Status bazowy wizyty: —")
                return
            base = statuses[base_idx]
            label = str(base.get("name") or base.get("id") or "—")
            explicit = bool(base.get("visit_base"))
            suffix = "" if explicit else " (domyślny — pierwszy status)"
            var.set(f"Status bazowy wizyty: {label}{suffix}")

        def _refresh_statuses(self, preferred_idx=None) -> None:
            super()._refresh_statuses(preferred_idx)
            self._update_visit_base_label()

        def _save_now(self) -> bool:
            self._ensure_visit_base_integrity()
            result = super()._save_now()
            self._update_visit_base_label()
            return result

        def _set_selected_visit_base(self) -> None:
            type_idx = self._selected_type_true_index()
            status_idx = self._selected_status_index()
            if type_idx is None or status_idx is None:
                messagebox.showinfo(
                    "Status bazowy",
                    "Najpierw wybierz typ i status narzędzia.",
                    parent=self,
                )
                return

            statuses = self._get_statuses_for_current(type_idx)
            if not (0 <= status_idx < len(statuses)):
                return

            for idx, status in enumerate(statuses):
                if not isinstance(status, dict):
                    continue
                if idx == status_idx:
                    status["visit_base"] = True
                else:
                    status.pop("visit_base", None)

            if self._save_now():
                self._refresh_statuses(preferred_idx=status_idx)
                selected = statuses[status_idx]
                label = str(selected.get("name") or selected.get("id") or "")
                messagebox.showinfo(
                    "Status bazowy",
                    f"Ustawiono status bazowy wizyty: {label}",
                    parent=self,
                )

    print("[WM-DBG] gui_tools_config: używam wersji advanced + visit_base")
else:
    print("[WM-DBG] gui_tools_config: fallback na prosty edytor JSON")

    import json
    import tkinter as tk
    from tkinter import messagebox, ttk

    from tools_config_loader import load_config as load_tools_config

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
                raw = load_tools_config(self.path)
                data = json.loads(json.dumps(raw or {}))
            except Exception as exc:
                messagebox.showerror("Błąd", f"Nie udało się wczytać definicji: {exc}")
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
