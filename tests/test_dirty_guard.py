import pytest
from dirty_guard import DirtyGuard


def test_mark_dirty_and_clean_reacts_and_logs(capfd):
    events = []
    guard = DirtyGuard(on_dirty_change=lambda state: events.append(state))

    guard.mark_dirty()
    guard.mark_clean()

    assert events == [True, False]
    out = capfd.readouterr().out
    assert "[WM-DBG][DIRTY] dirty" in out
    assert "[WM-DBG][DIRTY] clean" in out


def _run_check(response):
    guard = DirtyGuard()
    guard.mark_dirty()
    called = {"save": False, "discard": False}

    def dialog():
        return response

    def on_save():
        called["save"] = True

    def on_discard():
        called["discard"] = True

    result = guard.check_before(dialog, on_save, on_discard)
    return guard, called, result


@pytest.mark.parametrize("resp,exp_save,exp_discard,exp_result", [
    ("save", True, False, True),
    ("discard", False, True, True),
    ("cancel", False, False, False),
])
def test_check_before_responses(resp, exp_save, exp_discard, exp_result, capfd):
    guard, called, result = _run_check(resp)
    out = capfd.readouterr().out
    assert f"[WM-DBG][DIRTY] dialog={resp}" in out
    assert called["save"] is exp_save
    assert called["discard"] is exp_discard
    assert result is exp_result
    if resp == "cancel":
        assert guard.dirty is True
    else:
        assert guard.dirty is False
