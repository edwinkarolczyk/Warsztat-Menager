# version: 1.0
"""Regression tests for the optional helper grid in the hall renderer."""

import pytest

from widok_hali import renderer as renderer_module


class FakeCanvas:
    """Minimal canvas implementation used by the grid rendering tests."""

    def __init__(self):
        self.deleted = []
        self.images = []
        self.bindings = []

    def delete(self, target):
        self.deleted.append(target)

    def create_image(self, *args, **kwargs):
        self.images.append((args, kwargs))

    def tag_bind(self, *args):
        self.bindings.append(args)


def make_renderer(*, show_grid=False, edit_mode=False):
    """Build a renderer without initializing Tk or scheduling blink jobs."""

    hall_renderer = renderer_module.Renderer.__new__(renderer_module.Renderer)
    hall_renderer.canvas = FakeCanvas()
    hall_renderer._items_by_id = {}
    hall_renderer.machines = []
    hall_renderer._bg_image = object()
    hall_renderer.show_grid = show_grid
    hall_renderer._edit_mode = edit_mode
    return hall_renderer


@pytest.mark.parametrize(
    ("show_grid", "edit_mode", "expected"),
    [
        (False, False, False),
        (True, False, True),
        (False, True, True),
        (True, True, True),
    ],
)
def test_should_draw_grid_when_enabled_or_editing(show_grid, edit_mode, expected):
    hall_renderer = make_renderer(show_grid=show_grid, edit_mode=edit_mode)

    assert hall_renderer._should_draw_grid() is expected


def test_draw_all_keeps_normal_hall_image_free_of_grid(monkeypatch):
    hall_renderer = make_renderer()
    draw_grid_calls = []
    monkeypatch.setattr(
        renderer_module,
        "draw_grid",
        lambda *args, **kwargs: draw_grid_calls.append((args, kwargs)),
    )

    hall_renderer._draw_all()

    assert hall_renderer.canvas.deleted == ["all"]
    assert len(hall_renderer.canvas.images) == 1
    assert draw_grid_calls == []


@pytest.mark.parametrize("show_grid, edit_mode", [(True, False), (False, True)])
def test_draw_all_adds_grid_for_explicit_setting_or_edit_mode(
    monkeypatch, show_grid, edit_mode
):
    hall_renderer = make_renderer(show_grid=show_grid, edit_mode=edit_mode)
    draw_grid_calls = []
    monkeypatch.setattr(
        renderer_module,
        "draw_grid",
        lambda *args, **kwargs: draw_grid_calls.append((args, kwargs)),
    )

    hall_renderer._draw_all()

    assert draw_grid_calls == [
        ((hall_renderer.canvas,), {"grid_size": 24, "line": "#1e293b"})
    ]


def test_grid_visibility_and_edit_mode_setters_redraw():
    hall_renderer = make_renderer()
    redraws = []
    hall_renderer._draw_all = lambda: redraws.append(True)

    hall_renderer.set_grid_visible(True)
    hall_renderer.set_edit_mode(True)

    assert hall_renderer.show_grid is True
    assert hall_renderer._edit_mode is True
    assert redraws == [True, True]
