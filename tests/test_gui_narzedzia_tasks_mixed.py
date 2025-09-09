import types

import gui_narzedzia


class DummyListbox:
    def __init__(self):
        self.deleted = []
        self.inserted = []

    def delete(self, start, end=None):
        self.deleted.append((start, end))

    def insert(self, index, item):
        self.inserted.append((index, item))


def test_update_global_tasks_mixed():
    obj = types.SimpleNamespace(
        global_tasks=["[ ] A", {"text": "B", "done": False, "status": "Nowe"}],
        tasks_listbox=DummyListbox(),
    )

    gui_narzedzia._update_global_tasks(obj, "komentarz", "2025-09-09T12:00:00Z")

    t1, t2 = obj.global_tasks
    assert t1["done"] is True
    assert t2["done"] is True
    assert t1["status"] == t2["status"] == "Zrobione"
    assert t1["done_at"] == t2["done_at"] == "2025-09-09T12:00:00Z"
    assert t1["comment"] == t2["comment"] == "komentarz"

    assert gui_narzedzia._task_to_display(t1) == "[x] A"
    assert gui_narzedzia._task_to_display(t2) == "[x] B"

    assert obj.tasks_listbox.deleted == [(0, "end")]
    assert [call[1] for call in obj.tasks_listbox.inserted] == ["[x] A", "[x] B"]
