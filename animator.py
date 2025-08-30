"""Narzędzia do animacji trasy na potrzeby widoku hali."""
from __future__ import annotations

from typing import Any, Callable, Iterable, List


class RouteAnimator:
    """Rejestruje wywołania ``after`` i pozwala je anulować."""

    def __init__(self, root: Any) -> None:
        self._root = root
        self._after_ids: List[Any] = []

    def after(self, delay: int, func: Callable, *args: Any) -> Any:
        """Rejestruje wywołanie ``func`` za ``delay`` milisekund."""

        after_id = self._root.after(delay, func, *args)
        self._after_ids.append(after_id)
        return after_id

    def animate(
        self,
        route: Iterable[Any],
        move: Callable[[Any], None],
        delay: int = 50,
        on_finish: Callable[[], None] | None = None,
    ) -> None:
        """Animuje kolejne punkty ``route`` wywołując ``move``.

        ``on_finish`` zostanie wywołane po dojściu do ostatniego punktu.
        """

        route = list(route)
        for idx, point in enumerate(route):
            def step(p: Any = point) -> None:
                move(p)
                if p == route[-1] and on_finish:
                    on_finish()

            self.after(delay * idx, step)

    def cancel_all(self) -> None:
        """Anuluje wszystkie zaplanowane animacje."""

        for after_id in self._after_ids:
            try:
                self._root.after_cancel(after_id)
            except Exception:
                pass
        self._after_ids.clear()
