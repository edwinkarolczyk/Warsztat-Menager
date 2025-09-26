from __future__ import annotations

import json
import os
from contextlib import contextmanager
from typing import Dict, Iterator

import pytest

from config import paths as config_paths
from domain import orders


@contextmanager
def override_orders_dir(tmp_path) -> Iterator[str]:
    overrides: Dict[str, str] = {
        "paths.data_root": str(tmp_path),
        "paths.orders_dir": str(tmp_path / "zlecenia"),
    }

    def getter(key: str):
        return overrides.get(key)

    config_paths.set_getter(getter)
    try:
        yield overrides["paths.orders_dir"]
    finally:
        config_paths.set_getter(lambda _key: None)


def test_ensure_orders_dir_creates_directory(tmp_path):
    with override_orders_dir(tmp_path) as directory:
        assert not os.path.exists(directory)
        created = orders.ensure_orders_dir()
        assert created == directory
        assert os.path.isdir(directory)


def test_save_and_load_order(tmp_path):
    with override_orders_dir(tmp_path) as directory:
        payload = {"id": "ZW-1", "status": "nowe"}
        path = orders.save_order(payload)
        assert path == orders.order_path("ZW-1")
        assert os.path.exists(path)

        loaded = orders.load_order("ZW-1")
        assert loaded == payload

        with open(os.path.join(directory, "ZW-1.json"), "r", encoding="utf-8") as handle:
            assert json.load(handle) == payload


def test_load_orders_skips_invalid_and_hidden_files(tmp_path):
    with override_orders_dir(tmp_path) as directory:
        os.makedirs(directory, exist_ok=True)
        valid = tmp_path / "zlecenia" / "ZW-1.json"
        valid.write_text(json.dumps({"id": "ZW-1"}), encoding="utf-8")
        (tmp_path / "zlecenia" / "_seq.json").write_text("{}", encoding="utf-8")
        (tmp_path / "zlecenia" / "README.txt").write_text("info", encoding="utf-8")
        (tmp_path / "zlecenia" / "ZW-2.json").write_text("not json", encoding="utf-8")

        items = orders.load_orders()
        assert items == [{"id": "ZW-1"}]


def test_sequence_generation(tmp_path):
    with override_orders_dir(tmp_path):
        assert orders.next_sequence("ZW") == 1
        assert orders.next_sequence("ZW") == 2
        assert orders.next_sequence("ZN") == 1
        seq_data = json.loads(
            (tmp_path / "zlecenia" / "_seq.json").read_text(encoding="utf-8")
        )
        assert seq_data["ZW"] == 2
        assert seq_data["ZN"] == 1


def test_generate_order_id_respects_prefix_and_width(tmp_path):
    with override_orders_dir(tmp_path):
        assert orders.generate_order_id("ZW", prefix="ORD-", width=5) == "ORD-00001"
        assert orders.generate_order_id("ZW", width=2) == "ZW-02"
        assert orders.generate_order_id("ZW", width=0).startswith("ZW-")


def test_delete_order(tmp_path):
    with override_orders_dir(tmp_path):
        orders.save_order({"id": "ZW-1"})
        assert orders.load_order("ZW-1") is not None
        orders.delete_order("ZW-1")
        assert orders.load_order("ZW-1") is None
        # Brak wyjątku gdy nie ma pliku
        orders.delete_order("ZW-1")


def test_invalid_order_id_raises(tmp_path):
    with override_orders_dir(tmp_path):
        with pytest.raises(ValueError):
            orders.save_order({})
        with pytest.raises(ValueError):
            orders.order_path(" ")
        with pytest.raises(ValueError):
            orders.next_sequence("")
