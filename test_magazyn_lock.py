import multiprocessing
import time

import logika_magazyn as LM


def _worker(amount):
    LM.zwrot("a", amount, "proc")


def test_parallel_write_uses_file_lock(tmp_path, monkeypatch):
    magazyn = tmp_path / "mag.json"
    monkeypatch.setattr(LM, "MAGAZYN_PATH", str(magazyn))
    monkeypatch.setattr(LM, "MAGAZYN_LOCK_PATH", str(magazyn) + ".lock")

    data = LM._default_magazyn()
    data["items"]["a"] = {
        "id": "a",
        "nazwa": "A",
        "typ": "komponent",
        "jednostka": "szt",
        "stan": 0,
        "min_poziom": 0,
        "rezerwacje": 0,
        "historia": [],
    }
    LM.save_magazyn(data)

    orig_save = LM.save_magazyn

    def delayed_save(d, use_lock=True):
        time.sleep(0.2)
        orig_save(d, use_lock=use_lock)

    monkeypatch.setattr(LM, "save_magazyn", delayed_save)

    p1 = multiprocessing.Process(target=_worker, args=(5,))
    p2 = multiprocessing.Process(target=_worker, args=(3,))
    p1.start()
    p2.start()
    p1.join()
    p2.join()

    result = LM.load_magazyn()
    assert result["items"]["a"]["stan"] == 8.0
    assert len(result["items"]["a"]["historia"]) == 2

