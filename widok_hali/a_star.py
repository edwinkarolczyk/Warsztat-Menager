"""Prosty algorytm wyszukiwania trasy A* na siatce.

Krok przeszukiwania wynosi 4 piksele. Heurystyka oparta jest na
odległości Manhattan. Funkcja omija pola znajdujące się na liście
``walls``.
"""
from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
from typing import Dict, Iterable, List, Optional, Set, Tuple

Point = Tuple[int, int]


@dataclass(order=True)
class Node:
    """Węzeł w kolejce priorytetowej."""

    f: int
    g: int
    position: Point


def _neighbors(node: Point, step: int) -> Iterable[Point]:
    """Zwraca sąsiadów w czterech kierunkach."""

    x, y = node
    yield x + step, y
    yield x - step, y
    yield x, y + step
    yield x, y - step


def _manhattan(a: Point, b: Point) -> int:
    """Oblicza odległość Manhattan pomiędzy dwoma punktami."""

    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def a_star(start: Point, goal: Point, walls: Iterable[Point], step: int = 4) -> Optional[List[Point]]:
    """Znajduje trasę pomiędzy punktami ``start`` i ``goal``.

    :param start: punkt początkowy
    :param goal: punkt docelowy
    :param walls: iterowalna kolekcja zablokowanych pól
    :param step: wielkość kroku siatki w pikselach (domyślnie 4)
    :return: lista punktów od ``start`` do ``goal`` włącznie lub ``None``
             gdy brak trasy
    """

    blocked: Set[Point] = set(walls)
    open_set: List[Node] = []
    heappush(open_set, Node(_manhattan(start, goal), 0, start))
    came_from: Dict[Point, Point] = {}
    g_costs: Dict[Point, int] = {start: 0}

    while open_set:
        current_node = heappop(open_set)
        current = current_node.position

        if current == goal:
            path: List[Point] = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            return list(reversed(path))

        for neighbor in _neighbors(current, step):
            if neighbor in blocked:
                continue
            tentative_g = g_costs[current] + step
            if tentative_g < g_costs.get(neighbor, float("inf")):
                g_costs[neighbor] = tentative_g
                f_score = tentative_g + _manhattan(neighbor, goal)
                heappush(open_set, Node(f_score, tentative_g, neighbor))
                came_from[neighbor] = current

    return None
