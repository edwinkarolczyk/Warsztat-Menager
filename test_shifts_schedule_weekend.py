import datetime as dt
import datetime as dt


def test_week_matrix_weekend(monkeypatch):
    import grafiki.shifts_schedule as ss

    monkeypatch.setattr(
        ss,
        "_load_users",
        lambda: [{"id": "1", "name": "Alice", "active": True}],
    )
    monkeypatch.setattr(ss, "_load_modes", lambda: {"modes": {}})
    monkeypatch.setattr(ss, "_slot_for_mode", lambda mode, widx: "POPO")
    monkeypatch.setattr(ss, "_week_idx", lambda day: 0)

    def fake_times():
        return {
            "R_START": dt.time(6, 0),
            "R_END": dt.time(14, 0),
            "P_START": dt.time(14, 0),
            "P_END": dt.time(22, 0),
        }

    monkeypatch.setattr(ss, "_shift_times", fake_times)

    result = ss.week_matrix(dt.date(2025, 1, 6))
    days = result["rows"][0]["days"]

    assert len(days) == 6
    assert all(d["dow"] != "Sun" for d in days)
    assert days[-1]["shift"] == "R"
