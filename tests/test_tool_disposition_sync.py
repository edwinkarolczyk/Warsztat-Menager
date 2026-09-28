from __future__ import annotations

import json

import dyspozycje_store as DS
import tool_dyspozycja_sync_runtime as SYNC


def _setup_store(tmp_path, monkeypatch, rows):
    path = tmp_path / "dyspozycje.json"
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    monkeypatch.setattr(DS, "get_dyspozycje_path", lambda: path)
    return path


def _dysp(did, object_id="507", status="nowa"):
    return DS.make_dyspozycja(
        typ_dyspozycji="narzedzie",
        tytul="Naostrzyc 507",
        autor="Marek",
        obiekt_id=object_id,
        status=status,
        meta={"source_test": True},
    ) | {"id": did}


def test_w_ostrzeniu_starts_single_linked_disposition_and_records_worker(tmp_path, monkeypatch):
    path = _setup_store(tmp_path, monkeypatch, [_dysp("D1")])
    result = SYNC.sync_tool_disposition(
        {"numer": "507", "tryb": "STARE", "status": "W ostrzeniu"},
        actor="Edwin", previous_status="Do ostrzenia", new_status="W ostrzeniu",
    )
    assert result["action"] == "start"
    saved = json.loads(path.read_text(encoding="utf-8"))[0]
    assert saved["status"] == "w_toku"
    assert saved["wykonuje"] == "Edwin"
    hist = saved["meta"]["historia_statusow"]
    assert hist[-1]["z"] == "nowa" and hist[-1]["na"] == "w_toku"
    assert hist[-1]["kto"] == "Edwin"
    sync_hist = saved["meta"]["tool_sync_history"]
    assert sync_hist[-1]["z_statusu"] == "Do ostrzenia"
    assert sync_hist[-1]["na_status"] == "W ostrzeniu"
    assert sync_hist[-1]["kto"] == "Edwin"


def test_po_ostrzeniu_closes_and_remembers_exact_closer(tmp_path, monkeypatch):
    row = _dysp("D1", status="w_toku")
    row["wykonuje"] = "Marek"
    path = _setup_store(tmp_path, monkeypatch, [row])
    result = SYNC.sync_tool_disposition(
        {"numer": "507", "tryb": "STARE", "status": "Po ostrzeniu"},
        actor="Edwin", previous_status="W ostrzeniu", new_status="Po ostrzeniu",
    )
    assert result["action"] == "close"
    assert result["zamkniete_przez"] == "Edwin"
    saved = json.loads(path.read_text(encoding="utf-8"))[0]
    assert saved["status"] == "zamknieta"
    assert saved["zamkniete_przez"] == "Edwin"
    assert saved["zamknieto_at"]
    assert saved["wykonano"]
    assert saved["meta"]["historia_statusow"][-1]["kto"] == "Edwin"
    assert saved["meta"]["tool_sync_history"][-1]["akcja"] == "close"


def test_sprawne_after_repair_closes_old_tool_disposition(tmp_path, monkeypatch):
    path = _setup_store(tmp_path, monkeypatch, [_dysp("D1", status="w_toku")])
    result = SYNC.sync_tool_disposition(
        {"numer": "507", "tryb": "STARE", "status": "sprawne"},
        actor="Sebastian", previous_status="w naprawie", new_status="sprawne",
    )
    assert result["action"] == "close"
    saved = json.loads(path.read_text(encoding="utf-8"))[0]
    assert saved["zamkniete_przez"] == "Sebastian"


def test_multiple_new_dispositions_are_not_guessed_or_closed(tmp_path, monkeypatch):
    path = _setup_store(tmp_path, monkeypatch, [_dysp("D1"), _dysp("D2")])
    result = SYNC.sync_tool_disposition(
        {"numer": "507", "tryb": "STARE", "status": "Po ostrzeniu"},
        actor="Edwin", previous_status="W ostrzeniu", new_status="Po ostrzeniu",
    )
    assert result["changed"] is False
    assert result["reason"] == "no_unique_active_disposition"
    assert result["active_count"] == 2
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert {row["status"] for row in saved} == {"nowa"}


def test_other_tool_disposition_is_never_touched(tmp_path, monkeypatch):
    path = _setup_store(tmp_path, monkeypatch, [_dysp("D1", object_id="508", status="w_toku")])
    result = SYNC.sync_tool_disposition(
        {"numer": "507", "tryb": "STARE", "status": "Po ostrzeniu"},
        actor="Edwin", previous_status="W ostrzeniu", new_status="Po ostrzeniu",
    )
    assert result["reason"] == "no_active_disposition"
    assert json.loads(path.read_text(encoding="utf-8"))[0]["status"] == "w_toku"


def test_unnamed_wmm_actor_cannot_auto_close(tmp_path, monkeypatch):
    path = _setup_store(tmp_path, monkeypatch, [_dysp("D1", status="w_toku")])
    result = SYNC.sync_tool_disposition(
        {"numer": "507", "tryb": "STARE", "status": "Po ostrzeniu"},
        actor="WMM", previous_status="W ostrzeniu", new_status="Po ostrzeniu",
    )
    assert result["reason"] == "missing_named_actor"
    saved = json.loads(path.read_text(encoding="utf-8"))[0]
    assert saved["status"] == "w_toku"
    assert not saved.get("zamkniete_przez")


def test_source_hooks_sync_after_tool_save_and_wmm_durable_write():
    desktop = open("gui_narzedzia.py", encoding="utf-8").read()
    api = open("services/wmm_api_impl.py", encoding="utf-8").read()
    assert desktop.index("_save_tool(data_obj)") < desktop.index("sync_tool_disposition(", desktop.index("_save_tool(data_obj)"))
    run_idx = api.index("replayed, item = _run_idempotent(", api.index("tool_match = re.fullmatch"))
    sync_idx = api.index("sync_tool_disposition(", run_idx)
    assert run_idx < sync_idx
