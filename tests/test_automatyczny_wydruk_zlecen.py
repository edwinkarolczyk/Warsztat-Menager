from pathlib import Path

import drukowanie_zlecen as dz


def test_automatic_print_is_independent_from_approval(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(dz, "_auto_print_enabled", lambda: True)
    monkeypatch.setattr(dz, "_print_posix", lambda path: (True, "test-printer"))

    data = {
        "id": "ZW-0001",
        "rodzaj": "ZW",
        "status": "nowe",
        "opis": "Testowe zlecenie",
        "produkt": "TEST",
        "ilosc": 2,
    }

    result = dz.drukuj_nowe_zlecenie(data, autor="edwin")

    assert result["status"] == "wydrukowano"
    assert Path(result["plik"]).exists()
    assert "akcept" not in Path(result["plik"]).read_text(encoding="utf-8").lower()


def test_print_failure_does_not_raise(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(dz, "_auto_print_enabled", lambda: True)
    monkeypatch.setattr(dz, "_print_posix", lambda path: (False, "brak drukarki"))

    result = dz.drukuj_nowe_zlecenie(
        {"id": "ZW-0002", "rodzaj": "ZW", "status": "nowe", "opis": "Test"},
        autor="edwin",
    )

    assert result["status"] == "blad"
    assert "brak drukarki" in result["blad"]
