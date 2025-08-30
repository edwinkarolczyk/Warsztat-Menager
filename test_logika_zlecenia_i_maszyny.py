import json
import shutil
from pathlib import Path

import zlecenia_logika as zl
import maszyny_logika as ml
import bom


def _setup_zlecenia_copy(tmp_path, monkeypatch):
    data_src = Path('data')
    data_copy = tmp_path / 'data'
    shutil.copytree(data_src, data_copy)
    monkeypatch.setattr(zl, 'DATA_DIR', data_copy)
    monkeypatch.setattr(zl, 'BOM_DIR', data_copy / 'produkty')
    monkeypatch.setattr(zl, 'MAG_DIR', data_copy / 'magazyn')
    monkeypatch.setattr(zl, 'ZLECENIA_DIR', data_copy / 'zlecenia')
    return data_copy


def test_wczytanie_wielu_zlecen_filtracja(tmp_path, monkeypatch):
    data_copy = _setup_zlecenia_copy(tmp_path, monkeypatch)
    zdir = data_copy / 'zlecenia'
    zdir.mkdir(exist_ok=True)
    sample = [
        {"id": "000010", "status": "nowe"},
        {"id": "000011", "status": "w trakcie"},
        {"id": "000012", "status": "nowe"},
    ]
    for obj in sample:
        with open(zdir / f"{obj['id']}.json", 'w', encoding='utf-8') as f:
            json.dump(obj, f)

    loaded = zl.list_zlecenia()
    nowe = [z['id'] for z in loaded if z['status'] == 'nowe']
    w_trakcie = [z['id'] for z in loaded if z['status'] == 'w trakcie']
    assert set(nowe) == {"000010", "000012"}
    assert w_trakcie == ["000011"]


def test_machines_with_next_task(tmp_path, monkeypatch):
    src = Path('data/maszyny.json')
    dest = tmp_path / 'maszyny.json'
    shutil.copy(src, dest)
    monkeypatch.setattr(ml, 'DATA_FILE', dest)

    machines = ml.machines_with_next_task()
    assert machines, 'Powinna istnieć co najmniej jedna maszyna'
    tokarka = next(m for m in machines if m['nr_ewid'] == '27')
    assert tokarka['next_task']['data'] == '2025-01-01'


def test_polprodukty_check_and_reserve(tmp_path, monkeypatch):
    data_copy = _setup_zlecenia_copy(tmp_path, monkeypatch)
    bom = zl.read_bom('PRD001')

    braki = zl.check_materials(bom, 30)
    braki_dict = {b['kod']: b['brakuje'] for b in braki}
    assert braki_dict['PP001'] == 10
    assert braki_dict['PP002'] == 18

    mag_path = data_copy / 'magazyn' / 'polprodukty.json'
    with open(mag_path, encoding='utf-8') as f:
        mag_before = json.load(f)

    updated = zl.reserve_materials(bom, 5)

    with open(mag_path, encoding='utf-8') as f:
        mag_after = json.load(f)

    assert mag_after['PP001']['stan'] == mag_before['PP001']['stan'] - 10
    assert mag_after['PP002']['stan'] == mag_before['PP002']['stan'] - 5
    assert updated['PP001'] == mag_after['PP001']['stan']
    assert updated['PP002'] == mag_after['PP002']['stan']


def test_create_zlecenie_uses_selected_version(tmp_path, monkeypatch):
    data_copy = _setup_zlecenia_copy(tmp_path, monkeypatch)
    monkeypatch.setattr(bom, 'DATA_DIR', data_copy)

    v2 = {
        "kod": "PRD001",
        "nazwa": "Stojak spawany",
        "polprodukty": [
            {"kod": "PP001", "ilosc_na_szt": 2.0},
            {"kod": "PP002", "ilosc_na_szt": 1.0},
            {"kod": "PP003", "ilosc_na_szt": 1.0},
        ],
        "version": "2.0",
        "bom_revision": 2,
        "effective_from": "2024-06-01",
        "effective_to": None,
        "is_default": False,
    }
    prd_path = data_copy / 'produkty' / 'PRD001_v2.json'
    with open(prd_path, 'w', encoding='utf-8') as f:
        json.dump(v2, f, ensure_ascii=False, indent=2)

    zlec, braki = zl.create_zlecenie('PRD001', 1, wersja='2.0', reserve=False)
    assert zlec['wersja'] == '2.0'
    assert any(b['kod'] == 'PP003' for b in braki)
