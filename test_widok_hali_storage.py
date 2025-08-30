import json

import widok_hali.storage as storage
import logger


def test_load_config_hala_missing_file(tmp_path, monkeypatch):
    logs = []
    monkeypatch.setattr(logger, "log_akcja", lambda msg: logs.append(msg))

    cfg = storage.load_config_hala(str(tmp_path / "cfg.json"))

    assert cfg == storage.DEFAULT_CFG_HALA
    assert any("Brak pliku" in m for m in logs)


def test_load_config_hala_partial(tmp_path, monkeypatch):
    data = {"hala": {"show_grid": False, "backgrounds": {"1": "a.jpg"}}}
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    logs = []
    monkeypatch.setattr(logger, "log_akcja", lambda msg: logs.append(msg))

    cfg = storage.load_config_hala(str(cfg_path))

    assert cfg["show_grid"] is False
    assert cfg["grid_step_px"] == 4  # default
    assert cfg["backgrounds"]["1"] == "a.jpg"
    assert cfg["backgrounds"]["2"] == storage.DEFAULT_CFG_HALA["backgrounds"]["2"]
    assert any("hala.grid_step_px" in m for m in logs)
    assert any("tła hali 2" in m for m in logs)
