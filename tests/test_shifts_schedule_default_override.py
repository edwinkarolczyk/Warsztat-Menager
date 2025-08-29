import json
import sys
import types

from grafiki import shifts_schedule


def test_set_user_mode_overrides_default(tmp_path, monkeypatch):
    modes_file = tmp_path / "tryby_userow.json"
    data = {
        "version": "1.0.0",
        "anchor_monday": "2025-09-01",
        "patterns": ["111", "112", "121"],
        "modes": {},
    }
    modes_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    monkeypatch.setattr(shifts_schedule, "_MODES_FILE", str(modes_file))

    shifts_schedule._USER_DEFAULTS.clear()
    shifts_schedule._load_users()
    assert shifts_schedule._user_mode("dawid") == "111"

    shifts_schedule.set_user_mode("dawid", "112")
    assert shifts_schedule._user_mode("dawid") == "112"

    with open(modes_file, encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["modes"]["dawid"] == "112"


def test_missing_user_mode_defaults_to_numeric(monkeypatch):
    modes = {"anchor_monday": "2025-09-01", "patterns": {"111": "111"}, "modes": {}}
    monkeypatch.setattr(shifts_schedule, "_load_modes", lambda: modes)
    monkeypatch.setattr(shifts_schedule, "_read_json", lambda path: [])
    dummy_profiles = types.SimpleNamespace(
        get_all_users=lambda: [{"id": "jan", "name": "Jan", "active": True}]
    )
    monkeypatch.setitem(sys.modules, "profiles", dummy_profiles)

    shifts_schedule._USER_DEFAULTS.clear()
    users = shifts_schedule._load_users()
    assert users[0]["tryb_zmian"] == "111"
    assert shifts_schedule._user_mode("jan") == "111"

