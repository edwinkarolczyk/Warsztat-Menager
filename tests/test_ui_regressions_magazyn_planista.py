# WM-VERSION: 0.2

from pathlib import Path

import pytest

import rc1_magazyn_fix as rc1
from gui_magazyn_bom import WarehouseModel, _raw_dimension_fields, _raw_dimension_label
from rc1_magazyn_fix import (
    _canonical_semiproduct_raw_relation,
    _catalog_raw_materials_only,
    _ensure_generated_raw_name,
    _generated_raw_name,
    _raw_name_dimension,
    _selected_raw_id,
    ensure_magazyn_toolbar_once,
)
from ui_context_help import _popup_position


PLANOWANIE_SOURCE = Path(__file__).resolve().parents[1] / "gui_planowanie.py"


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


def test_raw_name_is_generated_from_kind_and_dimension_mode():
    assert _generated_raw_name("Profil", "30x30x2") == "Profil - 30x30x2"
    assert _generated_raw_name("Rura", "30x2") == "Rura - Fi 30x2"
    assert _generated_raw_name("Pręt", "20") == "Pręt - Fi 20"
    assert _generated_raw_name("Ceownik", "40x20x3", "wymiar") == "Ceownik - 40x20x3"


def test_raw_name_never_duplicates_fi_prefix():
    assert _raw_name_dimension("Fi 20", "fi") == "Fi 20"
    assert _raw_name_dimension("fi20", "fi") == "Fi 20"
    assert _raw_name_dimension("Ø20", "fi") == "Fi 20"
    assert _generated_raw_name("Pręt", "Fi 20", "fi") == "Pręt - Fi 20"


def test_missing_raw_name_variable_is_recreated(monkeypatch):
    class FakeStringVar:
        def __init__(self, master=None):
            self.master = master
            self.value = ""

        def set(self, value):
            self.value = value

        def get(self):
            return self.value

    monkeypatch.setattr(rc1.tk, "StringVar", FakeStringVar)
    raw_vars = {}
    owner = object()

    name = _ensure_generated_raw_name(raw_vars, owner, "Profil", "30x30x2", "wymiar")

    assert name == "Profil - 30x30x2"
    assert raw_vars["nazwa"].get() == "Profil - 30x30x2"
    assert raw_vars["nazwa"].master is owner


def test_planista_installs_raw_catalog_fix_before_panel_import():
    source = PLANOWANIE_SOURCE.read_text(encoding="utf-8")
    fix_import = "import rc1_magazyn_fix as _planista_raw_catalog_fix"
    panel_import = "from gui_planista_panel import panel_planista"
    assert fix_import in source
    assert panel_import in source
    assert source.index(fix_import) < source.index(panel_import)


def test_planista_raw_selector_uses_only_saved_surowce():
    model = type("Model", (), {})()
    model.surowce = {}
    model.external_or_legacy_items = {
        "SUR-001": {"nazwa": "Drut", "rozmiar": "fi 8"},
    }
    assert _catalog_raw_materials_only(model) == {}

    model.surowce = {
        "SUR-002": {
            "kod": "SUR-002",
            "nazwa": "Profil - 30x30x2",
            "rodzaj": "Profil",
            "rozmiar": "30x30x2",
        }
    }
    assert list(_catalog_raw_materials_only(model)) == ["SUR-002"]

    model.surowce.pop("SUR-002")
    assert _catalog_raw_materials_only(model) == {}
    assert "SUR-001" not in _catalog_raw_materials_only(model)


def test_semiproduct_raw_relation_is_canonical_and_uses_current_catalog_unit():
    model = type("Model", (), {})()
    model.surowce = {
        "SUR-002": {
            "kod": "SUR-002",
            "nazwa": "Profil - 30x30x2",
            "jednostka": "mm",
        }
    }

    relation = _canonical_semiproduct_raw_relation(
        model,
        {
            "kod": "SUR-002",
            "nazwa": "stara nazwa nie może być relacją",
            "ilosc_na_szt": "1250,5",
            "jednostka": "kg",
        },
    )

    assert relation == {
        "kod": "SUR-002",
        "ilosc_na_szt": 1250.5,
        "jednostka": "mm",
    }


def test_semiproduct_raw_relation_rejects_missing_material_id():
    model = type("Model", (), {})()
    model.surowce = {}

    with pytest.raises(ValueError, match="nie istnieje"):
        _canonical_semiproduct_raw_relation(
            model,
            {"kod": "SUR-999", "ilosc_na_szt": 100, "jednostka": "mm"},
        )


def test_visible_raw_choice_cannot_fall_back_to_stale_hidden_id():
    class Var:
        def __init__(self, value):
            self.value = value

        def get(self):
            return self.value

    owner = type("Owner", (), {})()
    owner._raw_by_id = {"SUR-002": {"kod": "SUR-002"}}
    owner._raw_display_to_id = {
        "Profil - 30x30x2  [SUR-002]": "SUR-002",
    }
    owner.pp_raw_choice = Var("Profil - 30x30x2  [SUR-002]")
    owner.pp_vars = {"sr_kod": Var("SUR-OLD")}
    assert _selected_raw_id(owner) == "SUR-002"

    owner.pp_raw_choice = Var("ręcznie zmieniony tekst")
    assert _selected_raw_id(owner) == ""


def test_model_saves_only_canonical_semiproduct_raw_relation(tmp_path):
    model = object.__new__(WarehouseModel)
    model.surowce = {
        "SUR-002": {"kod": "SUR-002", "jednostka": "mm"},
    }
    model.polprodukty = {}
    model.pol_dir = tmp_path

    model.add_or_update_polprodukt(
        {
            "kod": "POL-001",
            "nazwa": "Hak",
            "surowiec": {
                "kod": "SUR-002",
                "ilosc_na_szt": 200,
                "jednostka": "kg",
                "nazwa": "nie zapisuj tego jako relacji",
            },
        }
    )

    assert model.polprodukty["POL-001"]["surowiec"] == {
        "kod": "SUR-002",
        "ilosc_na_szt": 200.0,
        "jednostka": "mm",
    }
