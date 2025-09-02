import json

import pytest

from zlecenia_utils import przelicz_zapotrzebowanie, sprawdz_magazyn


def test_przelicz_zapotrzebowanie_surowce():
    wynik = przelicz_zapotrzebowanie("data/produkty/PRD001.json", 3)
    assert wynik["SR001"] == pytest.approx(1.224)
    assert wynik["SR002"] == pytest.approx(1.575)
    assert set(wynik.keys()) == {"SR001", "SR002"}


def test_sprawdz_magazyn_alerts_and_warnings(tmp_path):
    magazyn = {
        "SR001": {"stan": 120.0, "prog_alertu": 10.0},
        "SR002": {"stan": 60.0, "prog_alertu": 5.0},
    }
    path = tmp_path / "surowce.json"
    path.write_text(json.dumps(magazyn, ensure_ascii=False, indent=2), encoding="utf-8")

    ok, alerts, warnings = sprawdz_magazyn(str(path), {"SR001": 115, "SR002": 1})
    assert ok is True
    assert alerts == ""
    assert "SR001" in warnings

    ok, alerts, _ = sprawdz_magazyn(str(path), {"SR002": 100})
    assert ok is False
    assert "SR002" in alerts

    ok, alerts, _ = sprawdz_magazyn(str(path), {"SR999": 1})
    assert ok is False
    assert "SR999" in alerts
