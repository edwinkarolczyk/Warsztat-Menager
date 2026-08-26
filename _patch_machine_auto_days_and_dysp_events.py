from pathlib import Path

EXPECTED = {
    "gui_zlecenia.py": "349dbb47aa324792a6aeb1623d3371df65c036d3",
    "gui_settings.py": "de05747dde10d165229b0dc7dc98315b58e55e57",
    "maszyny_dyspozycje.py": "0d5afb6dbb91db49479ee78402f1231e98cc0503",
}


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, got {count}")
    return text.replace(old, new, 1)


def patch_gui_zlecenia() -> None:
    path = Path("gui_zlecenia.py")
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "# version: 1.9\n# Zmiany 1.9:\n",
        "# version: 1.10\n# Zmiany 1.10:\n"
        "# - Widok Dyspozycji odpina globalny event po zniszczeniu i nie odświeża nieistniejącego Treeview.\n"
        "# - Usunięto TclError 'invalid command name' po ponownym otwieraniu/przełączaniu Dyspozycji.\n"
        "# Zmiany 1.9:\n",
        "gui_zlecenia header",
    )

    text = replace_once(
        text,
        "        self._dysp_ui = _dysp_ui_config()\n"
        "        self._open_order_creator = _resolve_creator()\n"
        "        self._build_toolbar()\n",
        "        self._dysp_ui = _dysp_ui_config()\n"
        "        self._open_order_creator = _resolve_creator()\n"
        "        self._dysp_event_root: tk.Misc | None = None\n"
        "        self._dysp_event_bind_id: str | None = None\n"
        "        self._build_toolbar()\n",
        "gui_zlecenia init event refs",
    )

    old_bind = '''    def _bind_orders_event(self) -> None:\n        # kompatybilność wsteczna – jeśli gdzieś jeszcze leci OrdersUpdated\n        self.bind("<<OrdersUpdated>>", lambda _event: self._reload_orders(), add=True)\n        try:\n            root = self.winfo_toplevel()\n        except Exception:\n            root = None\n        if not root:\n            return\n        # nowy event dla Dyspozycji\n        root.bind(\n            "<<DyspozycjeUpdated>>",\n            lambda _event: self._reload_orders(),\n            add=True,\n        )\n\n'''
    new_bind = '''    def _view_is_alive(self) -> bool:\n        try:\n            return bool(self.winfo_exists() and self.tree.winfo_exists())\n        except Exception:\n            return False\n\n    def _on_dyspozycje_updated(self, _event: Any = None) -> None:\n        if not self._view_is_alive():\n            return\n        self._reload_orders()\n\n    def _bind_orders_event(self) -> None:\n        # kompatybilność wsteczna – lokalny bind znika razem z widokiem\n        self.bind("<<OrdersUpdated>>", self._on_dyspozycje_updated, add=True)\n        try:\n            root = self.winfo_toplevel()\n        except Exception:\n            root = None\n        if not root:\n            return\n        # Event jest emitowany na root, więc zapamiętujemy identyfikator binda\n        # i odpinamy dokładnie ten callback przy niszczeniu ZleceniaView.\n        try:\n            bind_id = root.bind(\n                "<<DyspozycjeUpdated>>",\n                self._on_dyspozycje_updated,\n                add="+",\n            )\n        except Exception:\n            bind_id = None\n        self._dysp_event_root = root\n        self._dysp_event_bind_id = str(bind_id) if bind_id else None\n\n'''
    text = replace_once(text, old_bind, new_bind, "gui_zlecenia bind cleanup")

    text = replace_once(
        text,
        "    def _reload_orders(self) -> None:\n"
        "        global _DYSP_TOOL_STATUS_CACHE, _DYSP_MACHINE_STATUS_CACHE\n",
        "    def _reload_orders(self) -> None:\n"
        "        if not self._view_is_alive():\n"
        "            return\n"
        "        global _DYSP_TOOL_STATUS_CACHE, _DYSP_MACHINE_STATUS_CACHE\n",
        "gui_zlecenia reload guard",
    )

    text = replace_once(
        text,
        "    def _on_destroy(self, _event: Any) -> None:\n"
        "        self._after.cancel_all()\n",
        "    def _on_destroy(self, event: Any) -> None:\n"
        "        if getattr(event, \"widget\", None) is not self:\n"
        "            return\n"
        "        self._after.cancel_all()\n"
        "        root = self._dysp_event_root\n"
        "        bind_id = self._dysp_event_bind_id\n"
        "        self._dysp_event_root = None\n"
        "        self._dysp_event_bind_id = None\n"
        "        if root is not None and bind_id:\n"
        "            try:\n"
        "                root.unbind(\"<<DyspozycjeUpdated>>\", bind_id)\n"
        "            except Exception:\n"
        "                pass\n",
        "gui_zlecenia destroy unbind",
    )

    path.write_text(text, encoding="utf-8")


def patch_gui_settings() -> None:
    path = Path("gui_settings.py")
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "# version: 1.0.3\n# Moduł: gui_settings\n# Zmiany 1.0.3:\n",
        "# version: 1.0.4\n# Moduł: gui_settings\n# Zmiany 1.0.4:\n"
        "# - Ustawienia → Moduły → Dyspozycje pozwalają ustawić liczbę dni przed cyklicznym przeglądem maszyny, kiedy ma powstać automatyczna Dyspozycja.\n"
        "# Zmiany 1.0.3:\n",
        "gui_settings header",
    )

    text = replace_once(
        text,
        "        blink = ttk.LabelFrame(parent, text=\"Miganie\")\n"
        "        blink.pack(fill=\"x\", padx=8, pady=8)\n"
        "        blink.columnconfigure(1, weight=1)\n\n"
        "        values = {\n",
        "        blink = ttk.LabelFrame(parent, text=\"Miganie\")\n"
        "        blink.pack(fill=\"x\", padx=8, pady=8)\n"
        "        blink.columnconfigure(1, weight=1)\n\n"
        "        automation = ttk.LabelFrame(parent, text=\"Automatyzacja przeglądów maszyn\")\n"
        "        automation.pack(fill=\"x\", padx=8, pady=8)\n"
        "        automation.columnconfigure(1, weight=1)\n\n"
        "        values = {\n",
        "gui_settings automation frame",
    )

    text = replace_once(
        text,
        "        blink_enabled = tk.BooleanVar(\n"
        "            value=bool(_cfg_get(\"dyspozycje.ui.blink_enabled\", True))\n"
        "        )\n\n"
        "        def _row(parent_widget, row: int, label: str, key: str):\n",
        "        blink_enabled = tk.BooleanVar(\n"
        "            value=bool(_cfg_get(\"dyspozycje.ui.blink_enabled\", True))\n"
        "        )\n"
        "        machine_cycle_days_before = tk.StringVar(\n"
        "            value=str(_cfg_get(\"dyspozycje.machine_cycle.days_before\", 7))\n"
        "        )\n\n"
        "        def _row(parent_widget, row: int, label: str, key: str):\n",
        "gui_settings automation var",
    )

    text = replace_once(
        text,
        "        _row(blink, 1, \"Miganie nowych [ms]:\", \"dyspozycje.ui.new_blink_ms\")\n"
        "        _row(blink, 2, \"Miganie po terminie [ms]:\", \"dyspozycje.ui.overdue_blink_ms\")\n\n"
        "        ttk.Label(\n"
        "            parent,\n",
        "        _row(blink, 1, \"Miganie nowych [ms]:\", \"dyspozycje.ui.new_blink_ms\")\n"
        "        _row(blink, 2, \"Miganie po terminie [ms]:\", \"dyspozycje.ui.overdue_blink_ms\")\n\n"
        "        ttk.Label(automation, text=\"Dodaj automatyczną Dyspozycję [dni przed terminem]:\").grid(\n"
        "            row=0, column=0, sticky=\"w\", padx=8, pady=4\n"
        "        )\n"
        "        ttk.Spinbox(\n"
        "            automation,\n"
        "            from_=0,\n"
        "            to=365,\n"
        "            textvariable=machine_cycle_days_before,\n"
        "            width=8,\n"
        "        ).grid(row=0, column=1, sticky=\"w\", padx=8, pady=4)\n"
        "        ttk.Label(\n"
        "            automation,\n"
        "            text=\"0 = w dniu przeglądu. Domyślnie: 7 dni. Zakres: 0–365.\",\n"
        "        ).grid(row=1, column=0, columnspan=2, sticky=\"w\", padx=8, pady=(0, 6))\n\n"
        "        ttk.Label(\n"
        "            parent,\n",
        "gui_settings automation widgets",
    )

    text = replace_once(
        text,
        "            try:\n"
        "                _cfg_set(\"dyspozycje.ui.blink_enabled\", bool(blink_enabled.get()))\n"
        "                for key, var in values.items():\n",
        "            try:\n"
        "                _cfg_set(\"dyspozycje.ui.blink_enabled\", bool(blink_enabled.get()))\n"
        "                _cfg_set(\n"
        "                    \"dyspozycje.machine_cycle.days_before\",\n"
        "                    _safe_int(machine_cycle_days_before.get(), 7, 0, 365),\n"
        "                )\n"
        "                for key, var in values.items():\n",
        "gui_settings save automation",
    )

    path.write_text(text, encoding="utf-8")


def patch_maszyny_dyspozycje() -> None:
    path = Path("maszyny_dyspozycje.py")
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "# version: 1.1\n# Zmiany 1.1:\n",
        "# version: 1.2\n# Zmiany 1.2:\n"
        "# - Liczba dni przed terminem dla automatycznej Dyspozycji jest pobierana z config.json (domyślnie 7, zakres 0–365).\n"
        "# Zmiany 1.1:\n",
        "maszyny_dyspozycje header",
    )

    text = replace_once(
        text,
        "from typing import Any, Iterable\n\n"
        "from dyspozycje_store import (\n",
        "from typing import Any, Iterable\n\n"
        "from config_manager import ConfigManager\n"
        "from dyspozycje_store import (\n",
        "maszyny_dyspozycje ConfigManager import",
    )

    text = replace_once(
        text,
        "AUTO_SOURCE = \"machine_cycle_review\"\nAUTO_WINDOW_DAYS = 7\n\n_MONTH_NAMES = {\n",
        "AUTO_SOURCE = \"machine_cycle_review\"\n"
        "AUTO_WINDOW_DAYS = 7\n"
        "AUTO_WINDOW_CONFIG_KEY = \"dyspozycje.machine_cycle.days_before\"\n\n"
        "def _configured_auto_window_days(default: int = AUTO_WINDOW_DAYS) -> int:\n"
        "    try:\n"
        "        value = ConfigManager().get(AUTO_WINDOW_CONFIG_KEY, default)\n"
        "        parsed = int(value)\n"
        "    except Exception:\n"
        "        parsed = int(default)\n"
        "    return max(0, min(365, parsed))\n\n\n"
        "_MONTH_NAMES = {\n",
        "maszyny_dyspozycje config helper",
    )

    text = replace_once(
        text,
        "def ensure_due_machine_cycle_dyspozycje(\n"
        "    *,\n"
        "    today: dt.date | None = None,\n"
        "    window_days: int = AUTO_WINDOW_DAYS,\n"
        ") -> list[dict[str, Any]]:\n"
        "    \"\"\"Dodaje brakujące cykliczne Dyspozycje i zwraca tylko nowo utworzone rekordy.\"\"\"\n",
        "def ensure_due_machine_cycle_dyspozycje(\n"
        "    *,\n"
        "    today: dt.date | None = None,\n"
        "    window_days: int | None = None,\n"
        ") -> list[dict[str, Any]]:\n"
        "    \"\"\"Dodaje brakujące cykliczne Dyspozycje i zwraca tylko nowo utworzone rekordy.\"\"\"\n"
        "    if window_days is None:\n"
        "        window_days = _configured_auto_window_days()\n",
        "maszyny_dyspozycje configured window",
    )

    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    patch_gui_zlecenia()
    patch_gui_settings()
    patch_maszyny_dyspozycje()
