from __future__ import annotations

import json
import threading
import time
from pathlib import Path


def _prepare_root(tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
    root = tmp_path / "wm-root"
    data = root / "data"
    products = data / "produkty"
    orders = data / "zlecenia"
    products.mkdir(parents=True)
    orders.mkdir(parents=True)
    (products / "P1.json").write_text(
        json.dumps(
            {
                "kod": "P1",
                "nazwa": "Produkt testowy",
                "polprodukty": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("WM_ROOT", str(root))
    monkeypatch.setenv("WM_DATA_ROOT", str(data))
    return root, data


def test_desktop_and_wmm_create_orders_with_distinct_ids(tmp_path, monkeypatch):
    root, data = _prepare_root(tmp_path, monkeypatch)

    import gui_planowanie  # noqa: F401
    import planista_audit_runtime as PAR
    import planista_safety_runtime as PSR
    import zlecenia_logika as ZL
    from services import wmm_api

    monkeypatch.setattr(ZL, "_data_dir", lambda: data)
    monkeypatch.setattr(PSR, "_active_data_dir", lambda: data)
    monkeypatch.setattr(PAR, "_canonical_warehouse_snapshot", lambda: {})
    monkeypatch.setattr(PAR, "_disposition_snapshot", lambda: (None, None))
    ZL.bom.DATA_DIR = data

    desktop_next = ZL._next_id
    wmm_next = wmm_api._next_order_id

    def slow_desktop_next():
        value = desktop_next()
        time.sleep(0.15)
        return value

    def slow_wmm_next():
        value = wmm_next()
        time.sleep(0.15)
        return value

    monkeypatch.setattr(ZL, "_next_id", slow_desktop_next)
    monkeypatch.setattr(wmm_api, "_next_order_id", slow_wmm_next)

    start = threading.Event()
    results: dict[str, str] = {}
    errors: list[Exception] = []

    def desktop_worker() -> None:
        try:
            start.wait(timeout=1.0)
            order, _shortages = ZL.create_zlecenie(
                "P1",
                1,
                autor="desktop",
                reserve=False,
                auto_dyspozycje=False,
            )
            results["desktop"] = str(order["id"])
        except Exception as exc:  # pragma: no cover - diagnoza testu
            errors.append(exc)

    def wmm_worker() -> None:
        try:
            start.wait(timeout=1.0)
            order = wmm_api._create_planista_order(
                {"product_code": "P1", "quantity": 1},
                "mobile",
            )
            results["wmm"] = str(order["id"])
        except Exception as exc:  # pragma: no cover - diagnoza testu
            errors.append(exc)

    desktop = threading.Thread(target=desktop_worker)
    mobile = threading.Thread(target=wmm_worker)
    desktop.start()
    mobile.start()
    start.set()
    desktop.join(timeout=5.0)
    mobile.join(timeout=5.0)

    assert not desktop.is_alive()
    assert not mobile.is_alive()
    assert errors == []
    assert sorted(results.values()) == ["000001", "000002"]

    orders = root / "data" / "zlecenia"
    saved = sorted(path.name for path in orders.glob("*.json"))
    assert saved == ["000001.json", "000002.json"]
