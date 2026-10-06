# WM-VERSION: 0.2

from pathlib import Path

import pytest

import rc1_magazyn_fix as rc1
import planista_stock_runtime as planista_stock
from gui_magazyn_bom import (
    WarehouseModel,
    SEMI_COLUMN_WIDTHS,
    _raw_dimension_fields,
    _raw_dimension_label,
    _raw_mode_unit,
    _raw_piece_meter_text,
    _raw_unit_display,
    configure_semiproduct_tree,
)
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
    assert _raw_dimension_label("pręt") == "Ø [mm]"
    assert _raw_dimension_fields("Rura", "20") == {"rozmiar": "20", "fi": "20"}
    assert _raw_dimension_fields("Profil", "30×30×2") == {
        "rozmiar": "30×30×2",
        "wymiar": "30×30×2",
    }
    assert _raw_dimension_fields("Ceownik", "40×20×3", "wymiar") == {
        "rozmiar": "40×20×3",
        "wymiar": "40×20×3",
    }
    assert _raw_dimension_label("Śruba", "szt") == "Rozmiar / oznaczenie"
    assert _raw_dimension_fields("Śruba", "M10", "szt") == {"rozmiar": "M10"}
    assert _raw_dimension_label("Łańcuszek", "oczka") == "Ilość oczek"
    assert _raw_dimension_fields("Łańcuszek", "13", "oczka") == {"rozmiar": "13"}
    assert _raw_mode_unit("oczka") == "oczek"
    assert _raw_unit_display("oczek") == "Oczek"


def test_raw_name_is_generated_from_kind_and_dimension_mode():
    assert _generated_raw_name("Profil", "30x30x2") == "Profil - 30x30x2"
    assert _generated_raw_name("Rura", "30x2") == "Rura - Ø30x2"
    assert _generated_raw_name("Pręt", "20") == "Pręt - Ø20"
    assert _generated_raw_name("Ceownik", "40x20x3", "wymiar") == "Ceownik - 40x20x3"


def test_raw_name_never_duplicates_fi_prefix():
    assert _raw_name_dimension("Fi 20", "fi") == "Ø20"
    assert _raw_name_dimension("fi20", "fi") == "Ø20"
    assert _raw_name_dimension("Ø20", "fi") == "Ø20"
    assert _generated_raw_name("Pręt", "Fi 20", "fi") == "Pręt - Ø20"


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


def test_planista_raw_stock_shows_pieces_and_meters():
    assert _raw_piece_meter_text(120, 6000) == "120 szt. (6 m)"
    assert _raw_piece_meter_text(3, 18500) == "3 szt. (18.5 m)"


def test_piece_raw_stock_uses_pieces_not_bar_length():
    state = planista_stock._stock_view(
        "SUR-015",
        {"jednostka": "szt", "dlugosc_sztangi_mm": 0},
        {
            "SUR-015": {
                "stan": 125,
                "rezerwacje": 5,
                "jednostka": "szt",
                "dlugosc_sztangi_mm": 0,
            }
        },
    )

    assert state["unit"] == "szt"
    assert state["stock"] == 125
    assert state["available"] == 120
    assert state["bars"] == 125
    assert state["length"] == 0


def test_chain_eye_stock_uses_count_unit_without_bar_length():
    state = planista_stock._stock_view(
        "SUR-003",
        {"jednostka": "oczek", "dlugosc_sztangi_mm": 0},
        {
            "SUR-003": {
                "stan": 130,
                "rezerwacje": 13,
                "jednostka": "oczek",
                "dlugosc_sztangi_mm": 0,
            }
        },
    )

    assert state["unit"] == "oczek"
    assert state["stock"] == 130
    assert state["available"] == 117
    assert state["bars"] == 130
    assert state["length"] == 0


def test_semiproduct_columns_keep_labels_and_second_screen_proportions():
    class FakeTree:
        def __init__(self):
            self.columns = (
                "nazwa", "surowiec", "ilosc", "jednostka",
                "czynnosci", "produkty", "id",
            )
            self.headings = {}
            self.widths = {}

        def cget(self, key):
            assert key == "columns"
            return self.columns

        def heading(self, key, **kwargs):
            self.headings[key] = kwargs

        def column(self, key, **kwargs):
            self.widths[key] = kwargs

    tree = FakeTree()
    configure_semiproduct_tree(tree)

    assert tree.headings["nazwa"]["text"].startswith("Półprodukt")
    assert tree.headings["produkty"]["text"].startswith("Używany w produktach")
    assert tree.widths["nazwa"]["width"] == 150
    assert tree.widths["surowiec"]["width"] == 175
    assert tree.widths["ilosc"]["width"] == 90
    assert tree.widths["jednostka"]["width"] == 70
    assert tree.widths["czynnosci"]["width"] == 410
    assert tree.widths["produkty"]["width"] == 340
    assert tree.widths["id"]["width"] == 95
    assert tree.widths["czynnosci"]["stretch"] is True
    assert tree.widths["produkty"]["stretch"] is True
    assert tree.widths["id"]["stretch"] is False
