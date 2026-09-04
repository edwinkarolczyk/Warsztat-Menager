# version: 1.1
import datetime as dt


def test_week_matrix_weekend(monkeypatch):
    import grafiki.shifts_schedule as ss

    monkeypatch.setattr(
        ss,
        "_load_users",
        lambda: [{
            "id": "USR-0001",
            "login": "alice",
            "name": "Alice",
            "active": True,
            "tryb_zmian": "121",
            "rotacja_start": "",
        }],
    )
    monkeypatch.setattr(
        ss,
        "_load_modes",
        lambda: {
            "anchor_monday": "2025-01-06",
            "patterns": {},
            "modes": {"USR-0001": "121"},
            "user_anchor": {"USR-0001": "2025-01-06"},
        },
    )
    monkeypatch.setattr(ss, "_slot_for_mode", lambda mode, widx: "POPO")

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
    assert all(day["dow"] != "Sun" for day in days)
    assert days[-1]["shift"] == "R"
