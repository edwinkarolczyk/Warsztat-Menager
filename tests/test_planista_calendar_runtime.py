# version: 1.0
from pathlib import Path


def test_planista_reuses_shared_calendar_with_today_border():
    runtime = Path("planista_calendar_runtime.py").read_text(encoding="utf-8")
    shared = Path("calendar_ui_runtime.py").read_text(encoding="utf-8")

    assert "from calendar_ui_runtime import open_date_picker" in runtime
    assert "GPP._open_date_calendar = _open_planista_calendar" in runtime
    assert 'GP._open_date_calendar = _open_planista_calendar' in runtime
    assert '_TODAY_BORDER = "#22c55e"' in shared
    assert "current == today" in shared


def test_planista_runtime_installs_calendar_layer():
    text = Path("gui_planowanie.py").read_text(encoding="utf-8")
    assert "install_planista_calendar_runtime" in text
    assert "install_planista_calendar_runtime()" in text
