from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

from animator import RouteAnimator
from controller import Controller
from widok_hali.a_star import a_star


class FakeRoot:
    def __init__(self) -> None:
        self.calls: Dict[Any, Tuple[int, Callable, tuple]] = {}
        self._next_id = 0

    def after(self, delay: int, func: Callable, *args: Any) -> int:
        self._next_id += 1
        self.calls[self._next_id] = (delay, func, args)
        return self._next_id

    def after_cancel(self, call_id: int) -> None:
        self.calls.pop(call_id, None)

    def run(self) -> None:
        for _, (_, func, args) in sorted(self.calls.items(), key=lambda i: i[1][0]):
            func(*args)
        self.calls.clear()


def test_a_star_avoids_walls() -> None:
    start = (0, 0)
    goal = (8, 0)
    walls = {(4, 0)}
    path = a_star(start, goal, walls)
    assert path in (
        [(0, 0), (0, 4), (4, 4), (8, 4), (8, 0)],
        [(0, 0), (0, -4), (4, -4), (8, -4), (8, 0)],
    )


def test_route_animator_cancel_all() -> None:
    root = FakeRoot()
    animator = RouteAnimator(root)
    called: List[int] = []

    animator.after(10, lambda: called.append(1))
    animator.after(20, lambda: called.append(2))
    animator.cancel_all()
    root.run()
    assert called == []


def test_controller_sets_status_after_animation() -> None:
    root = FakeRoot()
    animator = RouteAnimator(root)
    machines = [{"pos": (4, 0), "status": "AWARIA"}]
    ctrl = Controller(machines, animator, service_point=(0, 0), walls=set())
    ctrl.handle_failures()
    root.run()
    assert machines[0]["status"] == "SERWIS"
