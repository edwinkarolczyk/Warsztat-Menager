# version: 1.0
from pathlib import Path

from wm_access import normalize_module_name


def test_profile_sidebar_key_matches_panel_registry():
    """Profil ma używać jednego kanonicznego klucza w dostępie i nawigacji."""
    assert normalize_module_name("profil") == "profile"
    assert normalize_module_name("profile") == "profile"

    panel_source = (
        Path(__file__).resolve().parents[1] / "gui_panel.py"
    ).read_text(encoding="utf-8")
    assert '"profile": lambda' in panel_source
    assert 'elif key == "profile":' in panel_source
