# WM-VERSION: 0.1

from pathlib import Path

from gui_planista import _work_order_html, _work_order_output_path
from zlecenia_logika import _bars_for_cuts


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
            "R40x40": {
                "ilosc": 10016,
                "jednostka": "mm",
                "nazwa": "Profil 40x40",
                "dlugosc_sztangi_mm": 6000,
                "sztangi_potrzebne": 2,
            }
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
    assert "Długość detalu: 1250 mm (1.25 m)" in html
    assert (
        "Do odcięcia: <b>1250 mm (1.25 m) + grubość piły/taśmy 2 mm = "
        "1252 mm (1.252 m) / szt.</b>"
    ) in html
    assert "Surowiec do pobrania i cięcia" in html
    assert "10016 mm (10.016 m)" in html
    assert "6000 mm (6 m)" in html
    assert "Potrzeba sztang" in html
    assert ">2</b>" in html
    assert "9000 mm (9 m)" in html
    assert "Zarezerwowano z magazynu" in html
    assert "ilość surowca już zablokowana w Magazynie dla tego zlecenia" in html
    assert "Grubość piły/taśmy:</b> 2 mm" in html
    assert "Rzaz piły/tarczy:" not in html
    assert "szerokość materiału zabierana przez narzędzie podczas cięcia" not in html
    assert html.count("class='check-box'") == 2
    assert "Cięcie" in html
    assert "Wiercenie" in html
    assert "Po wykonaniu wszystkich operacji oznacz zlecenie jako wykonane w WM." in html
    assert "Pozostało:" in html
    assert "<b>Pozostało:</b> 8" in html
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


def test_bar_count_respects_real_cut_layout_not_only_total_length():
    # 3 x 3502 mm nie da się rozłożyć na dwóch sztangach 6000 mm,
    # mimo że suma długości jest mniejsza niż 2 x 6000 mm.
    plan = _bars_for_cuts([3502, 3502, 3502], 6000, 10506)

    assert plan["sztangi_potrzebne"] == 3
    assert plan["blad_ciecia"] == ""


def test_bar_count_rejects_piece_longer_than_standard_bar():
    plan = _bars_for_cuts([6102], 6000, 6102)

    assert plan["sztangi_potrzebne"] is None
    assert "dłuższy niż sztanga" in plan["blad_ciecia"]
