# WM-VERSION: 0.1
# Plik: tests/test_planista_safety_runtime.py
# version: 1.0

from pathlib import Path

import logika_magazyn as LM
import planista_safety_runtime as PSR
import planista_transaction_runtime as PTR
from planista_versions_runtime import _archive_name, _suggest_next_version


def test_reservation_state_distinguishes_full_partial_and_missing():
    base = {
        "zapotrzebowanie_surowce": {"SUR-1": {"ilosc": 6000}},
        "plan_polprodukty": {"POL-1": {"z_magazynu": 2}},
    }

    full = dict(base, rezerwacje_surowce={"SUR-1": 6000}, rezerwacje_polprodukty={"POL-1": 2})
    partial = dict(base, rezerwacje_surowce={"SUR-1": 3000}, rezerwacje_polprodukty={"POL-1": 2})
    missing = dict(base, rezerwacje_surowce={}, rezerwacje_polprodukty={})

    assert PSR._reservation_state(full) == (True, "pełne")
    assert PSR._reservation_state(partial) == (False, "częściowe")
    assert PSR._reservation_state(missing) == (False, "brak")


def test_reservation_state_no_need_is_not_a_shortage():
    assert PSR._reservation_state({}) == (True, "nie dotyczy")


def test_product_version_archive_name_and_suggestion_are_stable():
    assert _archive_name("1.775/250", "1.0") == "1.775_250__v1.0.json"
    assert _suggest_next_version("1.0") == "1.1"
    assert _suggest_next_version("2.7") == "2.8"


def test_warehouse_restore_writes_snapshot(monkeypatch):
    calls = []
    monkeypatch.setattr(LM, "save_magazyn", lambda data: calls.append(("save", data)))
    monkeypatch.setattr(LM, "zapisz_stan_magazynu", lambda data: calls.append(("state", data)))

    snapshot = {"items": {"SUR-1": {"stan": 123, "rezerwacje": 10}}}
    PTR._restore_warehouse(snapshot)

    assert calls[0][0] == "save"
    assert calls[1][0] == "state"
    assert calls[0][1]["items"]["SUR-1"]["stan"] == 123


def test_gui_planowanie_installs_all_planista_runtime_layers():
    text = Path("gui_planowanie.py").read_text(encoding="utf-8")
    assert "install_planista_safety_runtime" in text
    assert "install_planista_transaction_runtime" in text
    assert "install_planista_versions_runtime" in text
    assert "_runtime_ready" in text
