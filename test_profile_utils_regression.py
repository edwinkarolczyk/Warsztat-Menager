import json
import profile_utils as pu

def test_old_style_users_upgraded(tmp_path, monkeypatch):
    old_users = [{"login": "jan", "rola": "operator", "pin": "1111"}]
    path = tmp_path / "uzytkownicy.json"
    path.write_text(json.dumps(old_users, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(pu, "USERS_FILE", str(path))
    users = pu.read_users()
    user = users[0]
    for key in pu.DEFAULT_USER.keys():
        assert key in user
    saved = json.loads(path.read_text(encoding="utf-8"))
    for key in pu.DEFAULT_USER.keys():
        assert key in saved[0]
