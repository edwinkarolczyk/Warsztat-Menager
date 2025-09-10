import logika_zadan as LZ


def test_get_collections():
    cfg = {"tools.collections_enabled": ["C1", "C2"]}
    assert LZ.get_collections(cfg) == [
        {"id": "C1", "name": "C1"},
        {"id": "C2", "name": "C2"},
    ]


def test_get_tool_types_and_statuses_and_tasks(monkeypatch):
    data = {
        "C1": [
            {
                "id": "T1",
                "statuses": [{"id": "S1", "tasks": ["A", "B"]}],
            }
        ]
    }
    monkeypatch.setattr(LZ, "_load_tool_tasks", lambda force=False: data)
    LZ._TOOL_TASKS_CACHE = None
    assert LZ.get_tool_types("C1") == [{"id": "T1", "name": "T1"}]
    assert LZ.get_statuses("T1", "C1") == [{"id": "S1", "name": "S1"}]
    assert LZ.get_tasks("T1", "S1", "C1") == ["A", "B"]


def test_should_autocheck():
    cfg = {"tools": {"auto_check_on_status_global": ["S1"]}}
    assert LZ.should_autocheck("S1", "C1", cfg)
    assert not LZ.should_autocheck("S2", "C1", cfg)
