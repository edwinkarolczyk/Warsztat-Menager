# version: 1.5
from pathlib import Path
import ast

import pytest

SOURCE = Path("gui_settings.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)

def _method(name):
    for node in ast.walk(TREE):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(SOURCE, node) or ""
    raise AssertionError(name)

def test_tab_switch_does_not_prompt_for_save():
    body = _method("_on_tab_change")
    assert "_confirm_save_changes" not in body

def test_close_prompt_uses_real_value_comparison():
    assert "def _has_real_changes" in SOURCE
    body = _method("_confirm_save_changes")
    assert "_has_real_changes()" in body

def test_programmatic_save_guard_runs_before_dirty_mark():
    body = _method("_on_var_write")
    assert body.index("_saving") < body.index("_has_real_changes()")

def test_failed_save_keeps_unsaved_snapshot():
    from gui_settings import SettingsPanel

    class FakeVar:
        def get(self):
            return "nowa"

    class FailingConfig:
        def set(self, _key, _value):
            return None

        def save_all(self):
            raise OSError("brak zapisu")

    panel = SettingsPanel.__new__(SettingsPanel)
    panel.vars = {"test.key": FakeVar()}
    panel._initial = {"test.key": "stara"}
    panel._options = {}
    panel.cfg = FailingConfig()
    panel._user_var = None
    panel._saving = False
    panel._dirty = True
    panel._unsaved = True
    panel._active_settings_tab_name = lambda: "Test"
    panel._mark_save_dirty = lambda: None

    with pytest.raises(OSError, match="brak zapisu"):
        panel.save()

    assert panel._initial["test.key"] == "stara"
    assert panel._has_real_changes() is True
    assert panel._dirty is True
    assert panel._unsaved is True

def test_patch_version_bumped():
    from __version__ import get_version
    assert get_version() == "0.6.2"
