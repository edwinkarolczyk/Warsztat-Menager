import wm_ui_renovation_runtime as renovation


def test_attendance_builder_does_not_propagate_parent_refresh(monkeypatch):
    calls = []
    decorated = []

    def base(frame, login, *, on_saved=None):
        calls.append((frame, login, on_saved))

    monkeypatch.setattr(
        renovation,
        "_decorate_attendance_batch",
        lambda frame, login: decorated.append((frame, login)),
    )

    frame = object()
    external_refresh = lambda: None
    wrapped = renovation._wrap_attendance_builder(base)
    wrapped(frame, "jan", on_saved=external_refresh)

    assert calls == [(frame, "jan", None)]
    assert decorated == [(frame, "jan")]


def test_batch_merge_changes_only_fields_explicitly_edited():
    base = {
        "date": "2026-09-07",
        "slot": "RANO",
        "day_value": "1",
        "absence": "Brak",
        "overtime": "0",
        "overtime_type": "zwykle",
        "first_login": "05:58",
    }
    edits = {
        "slot": "POPO",
        "day_value": "0",
        "absence": "L4",
        "overtime": "2",
        "overtime_type": "sobota",
    }

    merged = renovation._merge_batch_values(
        base,
        edits,
        {"day_value", "absence"},
    )

    assert merged["date"] == "2026-09-07"
    assert merged["first_login"] == "05:58"
    assert merged["slot"] == "RANO"
    assert merged["day_value"] == "0"
    assert merged["absence"] == "L4"
    assert merged["overtime"] == "0"
    assert merged["overtime_type"] == "zwykle"


def test_renovation_notice_boolean_values_are_stable():
    assert renovation._coerce_bool(True) is True
    assert renovation._coerce_bool(False) is False
    assert renovation._coerce_bool("tak") is True
    assert renovation._coerce_bool("off") is False
    assert renovation._coerce_bool("unknown", default=True) is True


def test_notice_invites_feedback_and_is_signed():
    assert "Wyślij opinię" in renovation.NOTICE_TEXT
    assert "zła czy dobra" in renovation.NOTICE_TEXT
    assert "Edwin K." in renovation.NOTICE_TEXT
