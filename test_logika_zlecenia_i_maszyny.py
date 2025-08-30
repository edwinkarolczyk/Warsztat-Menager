import json
import shutil
from pathlib import Path

import pytest
import zlecenia_logika as zl
import maszyny_logika as ml
from config_manager import ConfigManager
import gui_zlecenia


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


def test_role_without_permission_cannot_edit(monkeypatch):
    try:
        import tkinter as tk
        from tkinter import ttk
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter not available")

    root.withdraw()
    root._wm_rola = "goscie"

    def fake_get(self, key, default=None):
        if key == "zlecenia.edit_roles":
            return ["admin"]
        return default

    monkeypatch.setattr(ConfigManager, "get", fake_get, raising=False)
    frame = gui_zlecenia.panel_zlecenia(root, root)
    actions = frame.winfo_children()[1]
    btns = {
        w.cget("text"): w
        for w in actions.winfo_children()
        if isinstance(w, ttk.Button)
    }
    assert btns["Nowe zlecenie"].instate(["disabled"])
    assert btns["Edytuj"].instate(["disabled"])
    assert btns["Usuń"].instate(["disabled"])
    assert btns["Rezerwuj"].instate(["disabled"])
    root.destroy()
