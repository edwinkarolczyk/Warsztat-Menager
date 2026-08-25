from pathlib import Path

path = Path("gui_settings.py")
text = path.read_text(encoding="utf-8")

old_header = "# version: 1.0\n# Moduł: gui_settings\n"
new_header = (
    "# version: 1.0.1\n"
    "# Moduł: gui_settings\n"
    "# Zmiany 1.0.1:\n"
    "# - refresh_panel sprawdza schema_path i używa settings_schema.json z katalogu programu, gdy ścieżka jest nieprawidłowa.\n"
)
if text.count(old_header) != 1:
    raise SystemExit(f"header match count={text.count(old_header)}")
text = text.replace(old_header, new_header, 1)

old = '''    def refresh_panel(self) -> None:\n        \"\"\"Reload configuration and rebuild widgets.\"\"\"\n\n        self.cfg = ConfigManager.refresh(\n            config_path=self.config_path, schema_path=self.schema_path\n        )\n'''
new = '''    def refresh_panel(self) -> None:\n        \"\"\"Reload configuration and rebuild widgets.\"\"\"\n\n        schema_path = self.schema_path\n        try:\n            schema_candidate = Path(str(schema_path))\n            if not schema_candidate.is_file():\n                fallback = (Path(__file__).resolve().parent / \"settings_schema.json\").resolve()\n                print(\n                    f\"[WM-DBG][SETTINGS] invalid schema_path={schema_path}; \"\n                    f\"fallback={fallback}\"\n                )\n                schema_path = str(fallback)\n                self.schema_path = schema_path\n        except Exception:\n            fallback = (Path(__file__).resolve().parent / \"settings_schema.json\").resolve()\n            schema_path = str(fallback)\n            self.schema_path = schema_path\n\n        self.cfg = ConfigManager.refresh(\n            config_path=self.config_path, schema_path=schema_path\n        )\n'''
if text.count(old) != 1:
    raise SystemExit(f"refresh block match count={text.count(old)}")
text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("patched gui_settings.py")
