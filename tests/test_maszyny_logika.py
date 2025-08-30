from maszyny_logika import delete_machine_with_triple_confirm


class Cfg:
    def __init__(self, triple):
        self._triple = triple

    def get(self, key, default):
        if key == "triple_confirm_delete":
            return self._triple
        return default


def test_delete_machine_requires_triple_confirm():
    machines = [{"id": "m1"}, {"id": "m2"}]
    calls = []

    def confirm():
        calls.append(True)
        return True

    cfg = Cfg(True)
    assert delete_machine_with_triple_confirm(machines, "m1", confirm, cfg)
    assert len(calls) == 3
    assert machines == [{"id": "m2"}]


def test_delete_machine_single_confirmation_when_disabled():
    machines = [{"id": "m1"}, {"id": "m2"}]
    calls = []

    def confirm():
        calls.append(True)
        return True

    cfg = Cfg(False)
    assert delete_machine_with_triple_confirm(machines, "m2", confirm, cfg)
    assert len(calls) == 1
    assert machines == [{"id": "m1"}]
