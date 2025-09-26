"""Pakiet pomocniczy do wizualizacji hal produkcyjnych."""

from .const import BG_GRID_COLOR, GRID_STEP, HALL_OUTLINE, HALLS_FILE, LAYERS
from .models import Hala, Machine, TechnicianRoute, WallSegment
from .storage import (
    load_awarie,
    load_config_hala,
    load_hale,
    load_machines as load_machines_raw,
    load_machines_models,
    load_walls,
    save_awarie,
    save_hale,
    save_machines,
)
from .renderer import (
    draw_background,
    draw_grid,
    draw_machine,
    draw_status_overlay,
    draw_walls,
)
from .controller import HalaController
from .animator import RouteAnimator
from .a_star import a_star, find_path


def load_machines() -> list[Machine]:
    """Zachowaj zgodność z poprzednim API zwracając modele ``Machine``."""

    return load_machines_models()

__all__ = [
    "GRID_STEP",
    "HALLS_FILE",
    "BG_GRID_COLOR",
    "HALL_OUTLINE",
    "LAYERS",
    "Hala",
    "Machine",
    "TechnicianRoute",
    "WallSegment",
    "load_hale",
    "save_hale",
    "load_machines",
    "load_machines_models",
    "load_machines_raw",
    "save_machines",
    "load_walls",
    "load_config_hala",
    "load_awarie",
    "save_awarie",
    "draw_background",
    "draw_grid",
    "draw_walls",
    "draw_machine",
    "draw_status_overlay",
    "HalaController",
    "RouteAnimator",
    "a_star",
    "find_path",
]
