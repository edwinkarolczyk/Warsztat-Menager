from __future__ import annotations

"""Simple controller for managing editing modes and drag operations.

The controller keeps track of the current mode (e.g. "select", "move",
"add") and a collection of items positioned on a 2D plane.  Dragging of
items snaps to the grid defined by ``drag_snap_px``.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class Item:
    """Represents a draggable item on the canvas."""

    x: int
    y: int


@dataclass
class Controller:
    """Controller handling basic editing interactions.

    Parameters
    ----------
    drag_snap_px:
        Size of a grid cell used when snapping dragged items.  When ``None``
        or ``0`` the coordinates are not snapped.
    """

    drag_snap_px: int = 0
    mode: str = "select"
    items: Dict[str, Item] = field(default_factory=dict)
    _drag_id: Optional[str] = None

    def set_mode(self, mode: str) -> None:
        """Sets current interaction mode.

        The method simply stores ``mode`` in :attr:`mode`.
        """

        self.mode = mode

    def on_click(self, item_id: str) -> None:
        """Starts dragging of ``item_id`` when in ``move`` mode."""

        if self.mode == "move" and item_id in self.items:
            self._drag_id = item_id

    def on_drag(self, x: int, y: int) -> None:
        """Updates position of the dragged item.

        When :attr:`drag_snap_px` is greater than ``0`` the coordinates are
        snapped to the nearest multiple of the grid step.
        """

        if self._drag_id is None:
            return
        if self.drag_snap_px:
            step = self.drag_snap_px
            x = round(x / step) * step
            y = round(y / step) * step
        itm = self.items[self._drag_id]
        itm.x = x
        itm.y = y

    def on_drop(self) -> None:
        """Finishes drag operation."""

        self._drag_id = None
