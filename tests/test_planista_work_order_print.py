# WM-VERSION: 0.1

from pathlib import Path

from gui_planista import _work_order_html, _work_order_output_path


def _sample_order():
    return {
        "id": "000123",
        "zlec_wew": "ZW-77",
        "produkt": "PRD-01",
        "ilosc": 10,
        "wykonano": 2,
        "termin": "2026-09-30",
        "version": "3",
        "rzaz_mm": 2,
        "zezwol_nadprodukcja": True,
        "uwagi": "Kontrola wymiaru po pierwszej sztuce.",
        "plan_polprodukty": {
            "PP-01": {
                "nazwa": "Rama",
                "potrzeba": 10,
                "z_magazynu": 2,
                "do_wykonania": 8,
                "czynnosci": ["Cięcie", "Wiercenie"],
                "surowiec": {
                    "kod": "R40x40",
                    "nazwa": "Profil 40x40",
                    "ilosc_na_szt": 1250,
                    "jednostka": "mm",
                },
            }
        },
        "zapotrzebowanie_surowce": {
            "R40x40": {"ilosc": 10016, "jednostka": "mm"}
        },
        "rezerwacje_surowce": {"R40x40": 9000},
        "braki": [
            {
                "kod": "R40x40",
                "nazwa": "Profil 40x40",
                "brakuje": 1016,
                "jednostka": "mm",
            }
        ],
    }


def test_work_order_contains_raw_material_per_piece_and_total():
    html = _work_order_html(_sample_order())

    assert "Zlecenie warsztatowe:" in html
    assert "ZW-77" in html
    assert "Profil 40x40" in html
    assert "1250 mm / szt." in html
    assert "Łączne zapotrzebowanie surowca" in html
    assert "10016" in html
    assert "9000" in html
    assert "Cięcie → Wiercenie" in html
    assert "Pozostało:" in html
    assert ">8<" in html
    assert "Nadprodukcja:</b> TAK" in html


def test_work_order_output_path_uses_active_wm_root(monkeypatch, tmp_path):
    monkeypatch.setenv("WM_ROOT", str(tmp_path))

    path = _work_order_output_path(_sample_order())

    assert path == tmp_path / "data" / "zlecenia" / "karty" / "zlecenie_000123.html"
    assert path.parent.is_dir()


def test_both_planista_views_use_persistent_work_order_path():
    root = Path(__file__).resolve().parents[1]
    standalone = (root / "gui_planista.py").read_text(encoding="utf-8")
    panel = (root / "gui_planista_panel.py").read_text(encoding="utf-8")

    assert "tempfile.gettempdir()" not in standalone
    assert "tempfile.gettempdir()" not in panel
    assert "path = _work_order_output_path(order)" in standalone
    assert "path = _work_order_output_path(order)" in panel
