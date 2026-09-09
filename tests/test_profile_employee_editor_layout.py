# version: 1.0
"""Regresje layoutu końcowego edytora pracownika."""

import profile_employee_editor_finish_runtime as runtime


class _FakeParent:
    def __init__(self, *, packed=None, gridded=None, fail=False):
        self._packed = list(packed or [])
        self._gridded = list(gridded or [])
        self._fail = fail

    def pack_slaves(self):
        if self._fail:
            raise RuntimeError("layout unavailable")
        return list(self._packed)

    def grid_slaves(self):
        if self._fail:
            raise RuntimeError("layout unavailable")
        return list(self._gridded)


def test_attendance_extensions_follow_final_pack_container():
    outer = object()
    attendance_tab = _FakeParent(packed=[outer])

    host, manager = runtime._attendance_extension_host(attendance_tab)

    assert host is outer
    assert manager == "pack"


def test_attendance_extensions_keep_grid_for_legacy_editor():
    grid_child = object()
    attendance_tab = _FakeParent(gridded=[grid_child])

    host, manager = runtime._attendance_extension_host(attendance_tab)

    assert host is attendance_tab
    assert manager == "grid"


def test_attendance_extensions_fallback_to_grid_when_layout_cannot_be_read():
    attendance_tab = _FakeParent(fail=True)

    host, manager = runtime._attendance_extension_host(attendance_tab)

    assert host is attendance_tab
    assert manager == "grid"
