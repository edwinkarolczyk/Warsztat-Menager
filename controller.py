"""Kontroler obsługi trasy serwisanta do maszyn w awarii."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from animator import RouteAnimator
from widok_hali.a_star import a_star

Point = Tuple[int, int]


class Controller:
    """Wyszukuje maszyny w stanie AWARIA i planuje do nich trasę."""

    def __init__(
        self,
        machines: List[Dict[str, Any]],
        animator: RouteAnimator,
        service_point: Point,
        walls: Iterable[Point] | None = None,
    ) -> None:
        self.machines = machines
        self.animator = animator
        self.service_point = service_point
        self.walls = set(walls or [])

    def _move(self, point: Point) -> None:  # pragma: no cover - placeholder
        """Metoda odpowiedzialna za przesuwanie obiektu na ekranie."""

    def handle_failures(self) -> None:
        """Wyszukuje maszyny w stanie AWARIA i animuje dojście do nich."""

        for machine in self.machines:
            if machine.get("status") != "AWARIA":
                continue
            path = a_star(self.service_point, machine["pos"], self.walls)
            if not path:
                continue

            def finished(m: Dict[str, Any] = machine) -> None:
                m["status"] = "SERWIS"

            self.animator.animate(path, self._move, on_finish=finished)
