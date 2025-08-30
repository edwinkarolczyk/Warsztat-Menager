"""Stałe dla modułu widoku hali."""

# domyślna wielkość kroku siatki (4 px)
GRID_STEP = 4

# czy wyświetlać siatkę na kanwie
SHOW_GRID = True

# plik z danymi hal
HALLS_FILE = "hale.json"

# kolory
BG_GRID_COLOR = "#2e323c"
HALL_OUTLINE = "#ff4b4b"

# warstwy rysowania na kanwie
CANVAS_LAYERS: dict[str, str] = {
    "grid": "grid",
    "halls": "halls",
    "overlay": "overlay",
}

