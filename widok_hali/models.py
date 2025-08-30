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
    """Reprezentuje pojedynczą maszynę w hali."""

    id: str
    nazwa: str
    hala: str
    x: int
    y: int
    status: str


@dataclass
class WallSegment:
    """Pojedynczy segment ściany w konkretnej hali."""

    hala: str
    x1: int
    y1: int
    x2: int
    y2: int


@dataclass
class TechnicianRoute:
    """Trasa technika jako lista punktów (w pikselach)."""

    tech_id: int
    hala: str
    path_px: List[Tuple[int, int]] = field(default_factory=list)


__all__ = [
    "Hala",
    "Machine",
    "WallSegment",
    "TechnicianRoute",
]

