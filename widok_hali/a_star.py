"""Prosta implementacja algorytmu A* na potrzeby widoku hali."""

from __future__ import annotations

from heapq import heappop, heappush
from typing import Callable, Dict, Iterable, List, Tuple, TypeVar

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
