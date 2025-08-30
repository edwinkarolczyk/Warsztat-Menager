"""Prosta implementacja algorytmu A* na potrzeby widoku hali."""

from __future__ import annotations

from heapq import heappop, heappush
from typing import Callable, Dict, Iterable, List, Sequence, Set, Tuple, TypeVar

T = TypeVar("T")


def a_star(
    start: T,
    goal: T,
    neighbors: Callable[[T], Iterable[T]],
    heuristic: Callable[[T, T], float],
) -> List[T]:
    """Zwróć listę węzłów od ``start`` do ``goal`` lub pustą listę."""
    open_set: List[Tuple[float, T]] = []
    heappush(open_set, (0.0, start))
    came_from: Dict[T, T] = {}
    g_score: Dict[T, float] = {start: 0.0}

    while open_set:
        _, current = heappop(open_set)
        if current == goal:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            return list(reversed(path))
        for neighbor in neighbors(current):
            tentative = g_score[current] + 1
            if tentative < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = tentative
                f = tentative + heuristic(neighbor, goal)
                heappush(open_set, (f, neighbor))
    return []


def find_path(
    start: Tuple[int, int],
    goal: Tuple[int, int],
    walls: Sequence[Tuple[int, int, int, int]],
) -> List[Tuple[int, int]]:
    """Znajdź ścieżkę od ``start`` do ``goal`` na siatce 4px.

    ``walls`` to sekwencja prostokątów ``(x1, y1, x2, y2)`` opisujących
    przeszkody. Funkcja zwraca listę punktów (w pikselach) prowadzącą do
    celu lub pustą listę, gdy ścieżka nie istnieje.
    """

    step = 4
    sx, sy = start
    gx, gy = goal
    start_cell = (sx // step, sy // step)
    goal_cell = (gx // step, gy // step)

    blocked: Set[Tuple[int, int]] = set()
    for x1, y1, x2, y2 in walls:
        cx1, cx2 = sorted((x1 // step, x2 // step))
        cy1, cy2 = sorted((y1 // step, y2 // step))
        for x in range(cx1, cx2 + 1):
            for y in range(cy1, cy2 + 1):
                blocked.add((x, y))

    def neighbors(node: Tuple[int, int]) -> Iterable[Tuple[int, int]]:
        x, y = node
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (x + dx, y + dy)
            if nxt not in blocked:
                yield nxt

    def heuristic(a: Tuple[int, int], b: Tuple[int, int]) -> float:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    path_cells = a_star(start_cell, goal_cell, neighbors, heuristic)
    return [(x * step, y * step) for x, y in path_cells]
