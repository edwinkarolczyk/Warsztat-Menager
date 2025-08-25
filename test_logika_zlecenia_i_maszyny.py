import json
import shutil
from pathlib import Path

import zlecenia_logika as zl
import maszyny_logika as ml


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
    src = Path('maszyny.json')
    dest = tmp_path / 'maszyny.json'
    shutil.copy(src, dest)
    monkeypatch.setattr(ml, 'DATA_FILE', dest)

    machines = ml.machines_with_next_task()
    assert machines, 'Powinna istnieć co najmniej jedna maszyna'
    tokarka = next(m for m in machines if m['nr_ewid'] == '27')
    assert tokarka['next_task']['data'] == '2025-01-01'
