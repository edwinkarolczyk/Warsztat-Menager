from __future__ import annotations

import copy
import json
import re
from pathlib import Path

GUI = Path("gui_settings.py")
SCHEMA = Path("settings_schema.json")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, got {count}")
    return text.replace(old, new, 1)


def regex_once(text: str, pattern: str, repl: str, label: str) -> str:
    out, count = re.subn(pattern, repl, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, got {count}")
    return out


# ---------------------------------------------------------------------------
# gui_settings.py — U1: porządek widoku bez usuwania kluczy z config.json
# ---------------------------------------------------------------------------
s = GUI.read_text(encoding="utf-8")

s = replace_once(
    s,
    "# version: 1.0.2\n# Moduł: gui_settings\n",
    "# version: 1.0.3\n# Moduł: gui_settings\n"
    "# Zmiany 1.0.3:\n"
    "# - U1: uproszczono główne Ustawienia do: Ogólne, Wygląd, Użytkownicy, Moduły, Backup, Zaawansowane.\n"
    "# - Narzędzia, Magazyn, Dyspozycje i Jarvis przeniesiono pod Moduły bez zmiany ich danych.\n"
    "# - Opinie, Statystyki, BOM i znak wodny ukryto z normalnego widoku Ustawień.\n"
    "# - Techniczne opcje aktualizacji/debug przeniesiono do Zaawansowanych.\n",
    "version header",
)

s = regex_once(
    s,
    r"        tabs_config = \[\n.*?\n        \]\n        if allow_users:\n            tabs_config\.insert\(3, \(self\.tab_users, \"Użytkownicy\", \"\"\)\)",
    "        tabs_config = [\n"
    "            (self.tab_ogolne, \"Ogólne\", \"\"),\n"
    "            (self.tab_ui, \"Wygląd\", \"\"),\n"
    "            (self.tab_modules, \"Moduły\", \"\"),\n"
    "            (self.tab_backup, \"Backup\", \"\"),\n"
    "            (self.tab_advanced, \"Zaawansowane\", \"\"),\n"
    "        ]\n"
    "        if allow_users:\n"
    "            tabs_config.insert(2, (self.tab_users, \"Użytkownicy\", \"\"))",
    "main settings tabs",
)

# Znak wodny pozostaje kompatybilny w kodzie/configu, ale nie jest pokazywany w Ustawieniach.
s = replace_once(
    s,
    "        watermark_box.pack(fill=\"x\", padx=8, pady=(8, 4))\n",
    "        # U1: kontrolka watermarku pozostaje kompatybilna, ale jest ukryta z UI.\n",
    "hide watermark box",
)

# Po utworzeniu notebooka Modułów podstawiamy kontenery ręcznych sekcji
# Dyspozycji i Jarvisa tak, aby nie były osobnymi głównymi zakładkami.
anchor = '''        self._modules_nb.bind(
            "<<NotebookTabChanged>>", self._on_modules_tab_change, add="+"
        )

        self._warehouse_nb = ttk.Notebook(self.tab_warehouse)
'''
replacement = '''        self._modules_nb.bind(
            "<<NotebookTabChanged>>", self._on_modules_tab_change, add="+"
        )

        # U1: ręczne sekcje modułowe trafiają do jednego notebooka „Moduły”.
        self._dispatches_module_frame = ttk.Frame(self._modules_nb)
        self._modules_nb.add(self._dispatches_module_frame, text="Dyspozycje")
        self._dispatches_container = ttk.LabelFrame(
            self._dispatches_module_frame,
            text="Dyspozycje — ustawienia",
        )
        self._dispatches_container.pack(fill="both", expand=True, padx=8, pady=8)

        self._jarvis_module_frame = ttk.Frame(self._modules_nb)
        self._modules_nb.add(self._jarvis_module_frame, text="Jarvis")
        self._jarvis_container = ttk.LabelFrame(
            self._jarvis_module_frame,
            text="Jarvis i powiadomienia",
        )
        self._jarvis_container.pack(fill="both", expand=True, padx=8, pady=8)

        self._warehouse_nb = ttk.Notebook(self.tab_warehouse)
'''
s = replace_once(s, anchor, replacement, "module manual containers")

# Opinie i Statystyki są ekranami danych, nie ustawieniami — U1 nie buduje ich tutaj.
s = replace_once(
    s,
    "        self._build_manual_config_fields()\n"
    "        self._build_dispatches_settings_tab()\n"
    "        self._build_feedback_settings_tab()\n"
    "        self._build_statistics_settings_tab()\n",
    "        self._build_manual_config_fields()\n"
    "        self._build_dispatches_settings_tab()\n"
    "        # U1: Opinie i Statystyki nie są już budowane w Ustawieniach.\n",
    "skip feedback/statistics settings",
)

# Produkty/BOM nie są ustawieniem; Dyspozycje są budowane ręcznie w jednym module.
needle = '''            if tab_id == "system":
                self._render_system_tab(tab, handlers)
                continue
            if tab_id == "narzedzia":
'''
repl = '''            if tab_id == "system":
                self._render_system_tab(tab, handlers)
                continue
            if tab_id == "produkty":
                print("[WM-DBG][SETTINGS] U1: pomijam Produkty/BOM w Ustawieniach")
                continue
            if tab_id == "dyspo":
                # U1: aktywna konfiguracja Dyspozycji jest w ręcznej sekcji Moduły.
                continue
            if tab_id == "narzedzia":
'''
s = replace_once(s, needle, repl, "skip products and duplicate dyspo")

# Narzędzia: ten sam handler, tylko jako podzakładka Modułów.
s = regex_once(
    s,
    r'''            if tab_id == "narzedzia":\n.*?                continue\n            if tab_id in warehouse_ids:''',
    '''            if tab_id == "narzedzia":
                frame = ttk.Frame(self._modules_nb)
                self._modules_nb.add(frame, text=title)
                self._register_nested_tab(
                    title, self.tab_modules, self._modules_nb, frame
                )
                path_key = (tab_id,)
                self._remember_tab_frame(path_key, frame)
                counts = self._handle_tools_tab(frame, tab, path_key)
                if counts:
                    self._log_tab_stats(title, *counts)
                continue
            if tab_id in warehouse_ids:''',
    "move tools under modules",
)

# Magazyn/Zamówienia: istniejący handler zachowujemy, zmieniamy tylko notebook docelowy.
s = replace_once(
    s,
    '''            if tab_id in warehouse_ids:
                frame = ttk.Frame(self._warehouse_nb)
                self._warehouse_nb.add(frame, text=title)
                self._register_nested_tab(
                    title, self.tab_warehouse, self._warehouse_nb, frame
                )
''',
    '''            if tab_id in warehouse_ids:
                frame = ttk.Frame(self._modules_nb)
                self._modules_nb.add(frame, text=title)
                self._register_nested_tab(
                    title, self.tab_modules, self._modules_nb, frame
                )
''',
    "move warehouse tabs under modules",
)

# Produkty nie trafiają do warehouse_ids; sam Magazyn i Zamówienia pozostają modułami.
s = replace_once(
    s,
    '''        warehouse_ids = {
            "magazyn",
            "zamowienia",
            "produkty",
        }
''',
    '''        warehouse_ids = {
            "magazyn",
            "zamowienia",
        }
''',
    "warehouse ids",
)

# Backup: normalny widok pokazuje tylko auto-update; ścieżki i ręczne operacje Git trafiają do Zaawansowanych.
s = regex_once(
    s,
    r'''            if tab_id == "aktualizacje":\n                frame = ttk\.LabelFrame\(self\._backup_container, text=title\)\n.*?                continue\n            if tab_id == "testy_audyt":''',
    '''            if tab_id == "aktualizacje":
                backup_tab = copy.deepcopy(tab)
                backup_groups = []
                for group in backup_tab.get("groups", []):
                    if str(group.get("title") or "") != "Automatyzacja":
                        continue
                    group = copy.deepcopy(group)
                    group["fields"] = [
                        field for field in group.get("fields", [])
                        if str(field.get("key") or "") != "backup.keep_last"
                    ]
                    backup_groups.append(group)
                backup_tab["groups"] = backup_groups

                if backup_groups:
                    frame = ttk.LabelFrame(self._backup_container, text=title)
                    frame.pack(fill="both", expand=True, padx=8, pady=6)
                    path_key = (tab_id, "u1_backup")
                    self._remember_tab_frame(path_key, frame)
                    counts = self._handle_generic_tab(frame, backup_tab, path_key)
                    if counts:
                        self._log_tab_stats(title, *counts)

                advanced_tab = copy.deepcopy(tab)
                advanced_tab["groups"] = [
                    copy.deepcopy(group)
                    for group in tab.get("groups", [])
                    if str(group.get("title") or "") in {"Ścieżki danych", "Operacje"}
                ]
                if advanced_tab["groups"]:
                    adv_frame = ttk.LabelFrame(
                        self._advanced_container,
                        text="Aktualizacje — techniczne",
                    )
                    adv_frame.pack(fill="both", expand=True, padx=8, pady=6)
                    adv_path = (tab_id, "u1_advanced")
                    self._remember_tab_frame(adv_path, adv_frame)
                    counts = self._handle_generic_tab(
                        adv_frame, advanced_tab, adv_path
                    )
                    if counts:
                        self._log_tab_stats("Aktualizacje — techniczne", *counts)
                continue
            if tab_id == "testy_audyt":''',
    "split backup and technical settings",
)

GUI.write_text(s, encoding="utf-8")


# ---------------------------------------------------------------------------
# settings_schema.json — tylko organizacja UI; definicje/klucze configu zostają.
# ---------------------------------------------------------------------------
schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
tabs = schema.get("tabs") or []


def tab_by_id(tab_id: str):
    for tab in tabs:
        if str(tab.get("id") or "") == tab_id:
            return tab
    return None


# Produkty/BOM jako ekran roboczy — nie jako główna sekcja Ustawień.
schema["tabs"] = [tab for tab in tabs if str(tab.get("id") or "") != "produkty"]
tabs = schema["tabs"]

# Magazyn: w U1 pokazujemy parametry magazynu, nie edytor/import BOM.
mag = tab_by_id("magazyn")
if mag:
    mag["subtabs"] = [
        sub for sub in (mag.get("subtabs") or [])
        if str(sub.get("id") or "") != "produkty_bom"
    ]

# System/Interfejs: watermark znika z UI; debug/log level przechodzą do Zaawansowanych.
moved_debug_fields = []
system_tab = tab_by_id("system")
if system_tab:
    for sub in system_tab.get("subtabs") or []:
        if str(sub.get("id") or "") != "interfejs":
            continue
        for group in sub.get("groups") or []:
            fields = group.get("fields") or []
            kept = []
            for field in fields:
                key = str(field.get("key") or "")
                if key == "ui.show_development_watermark":
                    continue
                if key in {"ui.debug_enabled", "ui.log_level"}:
                    moved_debug_fields.append(copy.deepcopy(field))
                    continue
                kept.append(field)
            group["fields"] = kept

# Zlecenia: techniczny kreator nie jest normalnym ustawieniem modułu.
moved_order_groups = []
orders_tab = tab_by_id("zlecenia")
if orders_tab:
    kept_subtabs = []
    for sub in orders_tab.get("subtabs") or []:
        if str(sub.get("id") or "") == "kreator":
            moved_order_groups.extend(copy.deepcopy(sub.get("groups") or []))
        else:
            kept_subtabs.append(sub)
    orders_tab["subtabs"] = kept_subtabs

# Dołączamy przeniesione pola do sekcji dev/Zaawansowane.
advanced_tab = tab_by_id("testy_audyt")
if advanced_tab:
    subtabs = advanced_tab.get("subtabs") or []
    target = None
    for sub in subtabs:
        if str(sub.get("id") or "") == "testy":
            target = sub
            break
    if target is None:
        target = {"id": "testy", "title": "Testy WM", "groups": []}
        subtabs.insert(0, target)
        advanced_tab["subtabs"] = subtabs
    groups = target.setdefault("groups", [])
    if moved_debug_fields:
        groups.append({
            "title": "Logowanie i debug",
            "fields": moved_debug_fields,
        })
    for group in moved_order_groups:
        group = copy.deepcopy(group)
        group["title"] = "Zlecenia — techniczne"
        groups.append(group)

SCHEMA.write_text(
    json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

# Sanity checks
assert "# version: 1.0.3" in GUI.read_text(encoding="utf-8")
parsed = json.loads(SCHEMA.read_text(encoding="utf-8"))
assert all(str(t.get("id") or "") != "produkty" for t in parsed.get("tabs", []))
print("U1 settings patch applied successfully")
