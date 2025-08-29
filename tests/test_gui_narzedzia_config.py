import importlib
import sys
from pathlib import Path


class DummyManager:
    def __init__(self):
        self.data = {}
        self.saved = False

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value, who="system"):
        self.data[key] = value

    def save_all(self):
        self.saved = True


def test_append_type_uses_config_manager(monkeypatch):
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    gn = importlib.import_module("gui_narzedzia")
    dummy = DummyManager()

    # Replace factory returning ConfigManager with our dummy instance
    monkeypatch.setattr(gn, "_cfg", lambda: dummy)

    assert gn._append_type_to_config("Nowy typ") is True
    assert dummy.data["typy_narzedzi"] == ["Nowy typ"]
    assert dummy.saved is True
