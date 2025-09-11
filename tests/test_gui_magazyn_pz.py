import importlib
import pytest


@pytest.fixture
def gmpz(monkeypatch):
    class DummyCfg(dict):
        def get(self, key, default=None):
            defaults = {"magazyn.require_reauth": False}
            return defaults.get(key, default)

    monkeypatch.setattr("config_manager.ConfigManager", lambda: DummyCfg())
    lm = importlib.reload(importlib.import_module("logika_magazyn"))
    module = importlib.reload(importlib.import_module("gui_magazyn_pz"))
    monkeypatch.setattr(module, "LM", lm)
    return module


@pytest.fixture
def warehouse(monkeypatch, gmpz):
    data = {
        "items": {
            "PROFIL_20x20x2_STAL": {
                "nazwa": "profil 20x20x2 stal",
                "jednostka": "mb",
                "stan": 0,
            },
            "RURA_FI30_SC2_STAL": {
                "nazwa": "rura fi30 sc2 stal",
                "jednostka": "mb",
                "stan": 0,
            },
            "ZBIJAK_KORPUS": {
                "nazwa": "ZBIJAK_KORPUS",
                "jednostka": "szt",
                "stan": 0,
            },
        }
    }
    history = []
    monkeypatch.setattr(gmpz.LM, "load_magazyn", lambda: data)
    monkeypatch.setattr(gmpz.LM, "save_magazyn", lambda d: None)
    monkeypatch.setattr(
        gmpz.magazyn_io,
        "append_history",
        lambda items, item_id, user, op, qty, comment="": history.append((item_id, qty)),
    )
    return gmpz, data, history


def test_record_pz_profile_success(warehouse):
    gmpz, data, history = warehouse
    gmpz.record_pz("PROFIL_20x20x2_STAL", 1.5, "user")
    assert data["items"]["PROFIL_20x20x2_STAL"]["stan"] == pytest.approx(1.5)
    assert history[-1] == ("PROFIL_20x20x2_STAL", 1.5)


def test_record_pz_rura_success(warehouse):
    gmpz, data, history = warehouse
    gmpz.record_pz("RURA_FI30_SC2_STAL", 0.75, "user")
    assert data["items"]["RURA_FI30_SC2_STAL"]["stan"] == pytest.approx(0.75)
    assert history[-1] == ("RURA_FI30_SC2_STAL", 0.75)


def test_record_pz_polprodukt_success(warehouse):
    gmpz, data, history = warehouse
    gmpz.record_pz("ZBIJAK_KORPUS", 5, "user")
    assert data["items"]["ZBIJAK_KORPUS"]["stan"] == pytest.approx(5)
    assert history[-1] == ("ZBIJAK_KORPUS", 5)

def test_fractional_quantity_rounds_up(warehouse, monkeypatch):
    gmpz, data, history = warehouse
    monkeypatch.setattr(gmpz.messagebox, "askyesnocancel", lambda *a, **k: True)
    gmpz.record_pz("ZBIJAK_KORPUS", 2.5, "user")
    assert data["items"]["ZBIJAK_KORPUS"]["stan"] == 3
    assert history[-1] == ("ZBIJAK_KORPUS", 3)


def test_fractional_quantity_rounds_down(warehouse, monkeypatch):
    gmpz, data, history = warehouse
    monkeypatch.setattr(gmpz.messagebox, "askyesnocancel", lambda *a, **k: False)
    gmpz.record_pz("ZBIJAK_KORPUS", 2.5, "user")
    assert data["items"]["ZBIJAK_KORPUS"]["stan"] == 2
    assert history[-1] == ("ZBIJAK_KORPUS", 2)


def test_fractional_quantity_rounding_cancel(warehouse, monkeypatch):
    gmpz, data, history = warehouse
    monkeypatch.setattr(gmpz.messagebox, "askyesnocancel", lambda *a, **k: None)
    gmpz.record_pz("ZBIJAK_KORPUS", 2.5, "user")
    assert data["items"]["ZBIJAK_KORPUS"]["stan"] == 0
    assert not history


def test_invalid_profile_dimension_error(warehouse):
    gmpz, _, _ = warehouse
    with pytest.raises(KeyError) as exc:
        gmpz.record_pz("NNxNNxN", 1, "user")
    assert "Brak pozycji NNxNNxN w magazynie" in str(exc.value)
