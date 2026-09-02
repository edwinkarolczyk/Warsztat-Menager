# WM-VERSION: 0.1
# Plik: tests/test_data_root_integrity.py
# version: 1.0

import json
from pathlib import Path

import pytest

import dyspozycje_store as DS
import planista_audit_runtime as PAR
import utils_maszyny as UM
from core import root_paths as RP


def test_machines_save_uses_active_data_root_not_cwd(tmp_path, monkeypatch):
    wm_root = tmp_path / "wm-root"
    data_root = wm_root / "data"
    primary = data_root / "maszyny" / "maszyny.json"
    legacy = data_root / "maszyny.json"
    repo_cwd = tmp_path / "repo"
    repo_cwd.mkdir()

    monkeypatch.chdir(repo_cwd)
    monkeypatch.setattr(RP, "path_machines", lambda: primary)
    monkeypatch.setattr(RP, "get_data_root", lambda: data_root)

    resolved_primary, resolved_legacy = UM._machine_data_paths()
    assert Path(resolved_primary) == primary
    assert Path(resolved_legacy) == legacy

    UM.save_machines([{"id": "42", "nazwa": "Test"}])

    assert primary.exists()
    assert json.loads(primary.read_text(encoding="utf-8"))[0]["id"] == "42"
    assert not (repo_cwd / "data" / "maszyny" / "maszyny.json").exists()


def test_dyspozycje_active_path_stays_inside_data_root(tmp_path, monkeypatch):
    data_root = tmp_path / "wm-root" / "data"
    target = data_root / "dyspozycje" / "dyspozycje.json"

    monkeypatch.setattr(RP, "path_dyspozycje", lambda: target)
    monkeypatch.setattr(DS, "_migrate_legacy_if_needed", lambda _target: None)

    assert DS.get_dyspozycje_path() == target
    assert target.parent == data_root / "dyspozycje"


def test_planista_never_treats_bom_json_as_product(tmp_path):
    import gui_magazyn_bom as GMB

    products = tmp_path / "produkty"
    products.mkdir()
    (products / "bom.json").write_text('{"items": []}', encoding="utf-8")
    (products / "PRD-1.json").write_text(
        '{"symbol": "PRD-1", "nazwa": "Produkt testowy"}',
        encoding="utf-8",
    )

    PAR._install_active_product_loader()
    loaded = GMB.WarehouseModel._load_dir(products)

    assert "PRD-1" in loaded
    assert "bom" not in loaded
    assert PAR._is_reserved_product_json(products / "bom.json") is True


def test_planista_blocks_direct_delete_of_reserved_bom():
    import gui_magazyn_bom as GMB

    PAR._install_active_product_loader()
    model = object.__new__(GMB.WarehouseModel)

    with pytest.raises(ValueError, match="technicznego pliku BOM"):
        GMB.WarehouseModel.delete_produkt(model, "bom")
