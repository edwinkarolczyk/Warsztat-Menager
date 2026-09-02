# WM-VERSION: 0.1

from gui_magazyn_bom import _raw_dimension_fields, _raw_dimension_label
from rc1_magazyn_fix import ensure_magazyn_toolbar_once
from ui_context_help import _popup_position


def test_magazyn_toolbar_is_built_for_each_new_panel():
    calls = []

    @ensure_magazyn_toolbar_once
    def build(toolbar, owner):
        calls.append((toolbar, owner))

    first = type("Owner", (), {})()
    second = type("Owner", (), {})()
    build("toolbar-1", first)
    build("toolbar-1", first)
    build("toolbar-2", second)
    assert calls == [("toolbar-1", first), ("toolbar-2", second)]


def test_help_popup_flips_to_left_at_right_screen_edge():
    x, y = _popup_position(980, 100, 20, 300, 100, 1024, 768)
    assert x == 674
    assert y == 100


def test_raw_kind_controls_dimension_name_and_saved_field():
    assert _raw_dimension_label("profil") == "Wymiar"
    assert _raw_dimension_label("Ceownik", "wymiar") == "Wymiar"
    assert _raw_dimension_label("pręt") == "Fi [mm]"
    assert _raw_dimension_fields("Rura", "20") == {"rozmiar": "20", "fi": "20"}
    assert _raw_dimension_fields("Profil", "30×30×2") == {
        "rozmiar": "30×30×2",
        "wymiar": "30×30×2",
    }
    assert _raw_dimension_fields("Ceownik", "40×20×3", "wymiar") == {
        "rozmiar": "40×20×3",
        "wymiar": "40×20×3",
    }
