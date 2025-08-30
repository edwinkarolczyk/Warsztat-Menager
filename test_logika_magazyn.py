import json
import multiprocessing as mp
import os
import sys

import pytest

import logika_magazyn as lm


def _save_worker(idx, path, start_q, finish_q, ready_evt):
    import logika_magazyn as lm
    import json
    import time
    lm.MAGAZYN_PATH = path
    m = lm.load_magazyn()
    orig_dump = json.dump

    def slow_dump(*a, **kw):
        ready_evt.set()
        time.sleep(0.3)
        return orig_dump(*a, **kw)

    json.dump = slow_dump
    start_q.put(time.time())
    m['meta']['worker'] = idx
    lm.save_magazyn(m)
    finish_q.put(time.time())


def test_rezerwuj_partial(tmp_path, monkeypatch):
    monkeypatch.setattr(lm, 'MAGAZYN_PATH', str(tmp_path / 'magazyn.json'))
    lm.load_magazyn()
    lm.upsert_item({
        'id': 'MAT-X',
        'nazwa': 'Test',
        'typ': 'materiał',
        'jednostka': 'szt',
        'stan': 8,
        'min_poziom': 0,
        'rezerwacje': 3,
    })

    reserved = lm.rezerwuj('MAT-X', 10, uzytkownik='test', kontekst='pytest')

    assert reserved == 5.0
    item = lm.get_item('MAT-X')
    assert item['rezerwacje'] == 8.0
    assert item['historia'][-1]['operacja'] == 'rezerwacja'
    assert item['historia'][-1]['ilosc'] == 5.0


def test_alert_after_zuzycie_below_min(tmp_path, monkeypatch):
    monkeypatch.setattr(lm, 'MAGAZYN_PATH', str(tmp_path / 'magazyn.json'))
    logs = []
    monkeypatch.setattr(lm, '_log_mag', lambda a, d: logs.append((a, d)))

    lm.load_magazyn()
    lm.upsert_item({
        'id': 'MAT-AL',
        'nazwa': 'Aluminium',
        'typ': 'materiał',
        'jednostka': 'szt',
        'stan': 5,
        'min_poziom': 2,
    })

    lm.zuzyj('MAT-AL', 4, uzytkownik='test', kontekst='pytest')

    alerts = [d for a, d in logs if a == 'prog_alert']
    assert alerts, 'powinien zostać zalogowany alert progowy'
    assert alerts[0]['item_id'] == 'MAT-AL'
    assert alerts[0]['stan'] == 1.0
    assert alerts[0]['min_poziom'] == 2.0


def test_load_magazyn_adds_prog_alert(tmp_path, monkeypatch):
    monkeypatch.setattr(lm, 'MAGAZYN_PATH', str(tmp_path / 'magazyn.json'))
    lm.load_magazyn()
    lm.upsert_item({
        'id': 'X',
        'nazwa': 'X',
        'typ': 'materiał',
        'jednostka': 'szt',
        'stan': 1,
        'min_poziom': 2,
    })
    m = lm.load_magazyn()
    assert 'prog_alert' in m['items']['X']
    assert m['items']['X']['prog_alert'] == 2.0


def test_set_order_persists(tmp_path, monkeypatch):
    monkeypatch.setattr(lm, 'MAGAZYN_PATH', str(tmp_path / 'magazyn.json'))
    lm.load_magazyn()
    lm.upsert_item({
        'id': 'A', 'nazwa': 'A', 'typ': 'komponent', 'jednostka': 'szt',
        'stan': 1, 'min_poziom': 0
    })
    lm.upsert_item({
        'id': 'B', 'nazwa': 'B', 'typ': 'komponent', 'jednostka': 'szt',
        'stan': 1, 'min_poziom': 0
    })
    lm.set_order(['B', 'A'])
    ids = [it['id'] for it in lm.lista_items()]
    assert ids[:2] == ['B', 'A']
    ids = [it['id'] for it in lm.lista_items()]
    assert ids[:2] == ['B', 'A']


def test_parallel_saves_are_serial(tmp_path, monkeypatch):
    monkeypatch.setattr(lm, 'MAGAZYN_PATH', str(tmp_path / 'magazyn.json'))
    lm.load_magazyn()
    path = str(tmp_path / 'magazyn.json')

    s1, f1 = mp.Queue(), mp.Queue()
    s2, f2 = mp.Queue(), mp.Queue()
    ready = mp.Event()

    p1 = mp.Process(target=_save_worker, args=(1, path, s1, f1, ready))
    p1.start()
    t1_start = s1.get()
    ready.wait()  # p1 wszedł w zapis i trzyma blokadę

    p2 = mp.Process(target=_save_worker, args=(2, path, s2, f2, mp.Event()))
    p2.start()
    t2_start = s2.get()

    t1_finish = f1.get()
    t2_finish = f2.get()
    p1.join()
    p2.join()

    assert t1_start < t2_start < t1_finish < t2_finish


@pytest.mark.skipif(sys.platform == "win32", reason="test dla systemów Unix")
def test_save_magazyn_uses_lock_unix(tmp_path, monkeypatch):
    monkeypatch.setattr(lm, "MAGAZYN_PATH", str(tmp_path / "magazyn.json"))
    data = lm._default_magazyn()
    calls = []

    orig_lock = lm.lock_file
    orig_unlock = lm.unlock_file

    def lock_spy(f):
        calls.append("lock")
        orig_lock(f)

    def unlock_spy(f):
        calls.append("unlock")
        orig_unlock(f)

    monkeypatch.setattr(lm, "lock_file", lock_spy)
    monkeypatch.setattr(lm, "unlock_file", unlock_spy)

    lm.save_magazyn(data)

    assert calls == ["lock", "unlock"]
    with open(lm.MAGAZYN_PATH, "r", encoding="utf-8") as f:
        assert json.load(f)["meta"]


@pytest.mark.skipif(sys.platform != "win32", reason="test tylko dla Windows")
def test_save_magazyn_uses_lock_windows(tmp_path, monkeypatch):
    monkeypatch.setattr(lm, "MAGAZYN_PATH", str(tmp_path / "magazyn.json"))
    data = lm._default_magazyn()
    calls = []

    orig_lock = lm.lock_file
    orig_unlock = lm.unlock_file

    def lock_spy(f):
        calls.append("lock")
        orig_lock(f)

    def unlock_spy(f):
        calls.append("unlock")
        orig_unlock(f)

    monkeypatch.setattr(lm, "lock_file", lock_spy)
    monkeypatch.setattr(lm, "unlock_file", unlock_spy)

    lm.save_magazyn(data)

    assert calls == ["lock", "unlock"]
    assert os.path.exists(lm.MAGAZYN_PATH)
