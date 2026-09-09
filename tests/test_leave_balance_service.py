from __future__ import annotations

import json

from services import leave_balance_service as balance


def test_unused_leave_moves_to_next_year_and_oldest_is_consumed_first(tmp_path, monkeypatch):
    path = tmp_path / "leave_balances.json"
    monkeypatch.setattr(balance, "ledger_path", lambda: path)
    monkeypatch.setattr(balance, "_annual_entitlement", lambda _login: 26.0)
    monkeypatch.setattr(balance, "_user_key", lambda _login: "USR-0001")
    monkeypatch.setattr(balance, "_pending", lambda _login, _year: 0.0)
    used = {2026: 20.0, 2027: 4.0}
    monkeypatch.setattr(balance, "_approved_used", lambda _login, year: used.get(int(year), 0.0))

    first = balance.get_balance("jan", 2026)
    assert first["entitlement"] == 26.0
    assert first["remaining"] == 6.0

    second = balance.get_balance("jan", 2027)
    assert second["carryover"] == 6.0
    assert second["available"] == 32.0
    assert second["used"] == 4.0
    assert second["remaining"] == 28.0
    assert second["consumed_by_source"]["2026"] == 4.0
    assert second["remaining_by_source"]["2026"] == 2.0
    assert second["remaining_by_source"]["2027"] == 26.0


def test_manual_carryover_keeps_source_year(tmp_path, monkeypatch):
    path = tmp_path / "leave_balances.json"
    monkeypatch.setattr(balance, "ledger_path", lambda: path)
    monkeypatch.setattr(balance, "_annual_entitlement", lambda _login: 26.0)
    monkeypatch.setattr(balance, "_user_key", lambda _login: "USR-0001")
    monkeypatch.setattr(balance, "_pending", lambda _login, _year: 0.0)
    monkeypatch.setattr(balance, "_approved_used", lambda _login, _year: 3.0)

    balance.set_year_values("jan", 2027, carryover={2025: 2, 2026: 4})
    result = balance.get_balance("jan", 2027)
    assert result["carryover"] == 6.0
    assert result["consumed_by_source"]["2025"] == 2.0
    assert result["consumed_by_source"]["2026"] == 1.0
    assert result["remaining_by_source"]["2025"] == 0.0
    assert result["remaining_by_source"]["2026"] == 3.0
