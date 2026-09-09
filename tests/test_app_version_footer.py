# version: 1.0
from pathlib import Path

def test_main_footer_shows_central_app_version():
    text = Path("gui_panel.py").read_text(encoding="utf-8")
    assert 'text=f"Warsztat Menager v{APP_VERSION}"' in text

def test_central_version_uses_three_part_semver():
    from __version__ import get_version
    parts = get_version().split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)
