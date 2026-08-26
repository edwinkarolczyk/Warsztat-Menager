from pathlib import Path

path = Path("gui_zlecenia.py")
text = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly 1 match, got {count}")
    text = text.replace(old, new, 1)


replace_once(
    "# version: 1.6\n# Zmiany 1.6:\n",
    "# version: 1.7\n"
    "# Zmiany 1.7:\n"
    "# - Dyspozycje automatycznie dodają zadanie dla cyklicznego przeglądu maszyny do 7 dni przed terminem.\n"
    "# - Automatyczny wpis zachowuje typ Maszyna, konkretną maszynę, opis źródła oraz roczny klucz bez duplikatów.\n"
    "# Zmiany 1.6:\n",
    "version header",
)

replace_once(
    "from dyspozycje_sources import load_machine_choices, load_tool_choices\n",
    "from dyspozycje_sources import load_machine_choices, load_tool_choices\n"
    "from maszyny_dyspozycje import ensure_due_machine_cycle_dyspozycje\n",
    "machine cycle bridge import",
)

replace_once(
    """        try:\n            rows = _load_orders_rows()\n            try:\n                from gui_panel import wm_set_module_source\n""",
    """        try:\n            try:\n                ensure_due_machine_cycle_dyspozycje(today=_dt.date.today())\n            except Exception as exc:\n                logger.exception(\n                    \"[DYSP][MASZYNY] Nie udało się zsynchronizować cyklicznych przeglądów: %s\",\n                    exc,\n                )\n            rows = _load_orders_rows()\n            try:\n                from gui_panel import wm_set_module_source\n""",
    "refresh cycle sync",
)

path.write_text(text, encoding="utf-8")
