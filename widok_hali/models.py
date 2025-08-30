"""Modele danych dla widoku hali."""

from dataclasses import dataclass


@dataclass
class Hala:
    """Reprezentuje prostokątną halę na siatce."""
    nazwa: str
    x1: int
    y1: int
    x2: int
    y2: int
