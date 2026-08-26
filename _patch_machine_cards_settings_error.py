from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly 1 match, got {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# gui_maszyny.py: version/changelog + central runtime path for generated cards.
replace_once(
    "gui_maszyny.py",
    "# version: 1.5\n# Zmiany 1.5:\n",
    "# version: 1.6\n# Zmiany 1.6:\n"
    "# - Karty/PDF maszyn zapisują się w centralnym ROOT WM: <root>/wydruki/karty, niezależnie od katalogu uruchomienia.\n"
    "# Zmiany 1.5:\n",
)
replace_once(
    "gui_maszyny.py",
    '''    def _cards_output_dir() -> Path:\n        base = Path.cwd() / "wydruki" / "karty"\n        base.mkdir(parents=True, exist_ok=True)\n        return base\n''',
    '''    def _cards_output_dir() -> Path:\n        try:\n            from config_manager import ConfigManager\n\n            base = Path(ConfigManager().path_root("wydruki", "karty"))\n        except Exception:\n            root = str(os.environ.get("WM_ROOT") or "").strip()\n            base = (Path(root) if root else Path.cwd()) / "wydruki" / "karty"\n        base.mkdir(parents=True, exist_ok=True)\n        return base\n''',
)

# gui_settings.py: version/changelog + valid dialog parent in embedded SettingsPanel.
replace_once(
    "gui_settings.py",
    "# version: 1.0.4\n# Moduł: gui_settings\n# Zmiany 1.0.4:\n",
    "# version: 1.0.5\n# Moduł: gui_settings\n# Zmiany 1.0.5:\n"
    "# - Naprawiono zapis ustawień Dyspozycji w osadzonym panelu: komunikaty używają istniejącego okna nadrzędnego zamiast nieistniejącego self.win.\n"
    "# Zmiany 1.0.4:\n",
)
replace_once(
    "gui_settings.py",
    '''                messagebox.showinfo(\n                    "Dyspozycje",\n                    "Zapisano ustawienia wyglądu dyspozycji.",\n                    parent=self.win,\n                )\n            except Exception as exc:\n                logger.exception(\n                    "[SETTINGS][DYSP] Nie udało się zapisać ustawień dyspozycji"\n                )\n                messagebox.showerror(\n                    "Dyspozycje",\n                    f"Nie udało się zapisać ustawień: {exc}",\n                    parent=self.win,\n                )\n''',
    '''                messagebox.showinfo(\n                    "Dyspozycje",\n                    "Zapisano ustawienia wyglądu dyspozycji.",\n                    parent=parent.winfo_toplevel(),\n                )\n            except Exception as exc:\n                logger.exception(\n                    "[SETTINGS][DYSP] Nie udało się zapisać ustawień dyspozycji"\n                )\n                messagebox.showerror(\n                    "Dyspozycje",\n                    f"Nie udało się zapisać ustawień: {exc}",\n                    parent=parent.winfo_toplevel(),\n                )\n''',
)

print("patch applied")
