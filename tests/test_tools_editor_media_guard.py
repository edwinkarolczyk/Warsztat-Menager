from __future__ import annotations

import tkinter as tk

from narzedzia_ui import editor_variant_runtime as variant


class _FakeWindow:
    def __init__(self) -> None:
        self._wm_tool_images_get = lambda: []


class _DeadWidget:
    def winfo_children(self):
        raise tk.TclError('bad window path name ".dead"')


def test_empty_live_images_fall_back_to_tool_json(monkeypatch):
    window = _FakeWindow()
    monkeypatch.setattr(
        variant,
        "_current_doc",
        lambda _window: {
            "numer": "512",
            "obrazy": ["media/512_a.jpg", "media/512_b.jpg"],
            "obraz": "media/512_a.jpg",
        },
    )
    monkeypatch.setattr(
        variant,
        "_entry_value_from_field",
        lambda _window, _label: "512",
    )

    assert variant._image_values(window) == [
        "media/512_a.jpg",
        "media/512_b.jpg",
    ]


def test_dead_widget_does_not_break_descendant_scan():
    assert list(variant._all_descendants(_DeadWidget())) == []
