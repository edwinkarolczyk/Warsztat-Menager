"""Modele danych dla widoku hali."""

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class Hala:
    """Reprezentuje prostokątną halę na siatce."""
    nazwa: str
    x1: int
    y1: int
    x2: int
    y2: int


@dataclass
class Machine:
    """Reprezentuje maszynę w hali."""
    nazwa: str
    x1: int
    y1: int
    x2: int
    y2: int


@dataclass
class WallSegment:
    """Pojedynczy segment ściany."""
    x1: int
    y1: int
    x2: int
    y2: int


@dataclass
class TechnicianRoute:
    """Trasa technika jako lista punktów na siatce."""
    punkty: List[Tuple[int, int]] = field(default_factory=list)
