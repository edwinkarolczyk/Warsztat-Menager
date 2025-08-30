"""Stałe dla modułu widoku hali."""

# Krok siatki w pikselach – zgodnie z wymaganiami używamy bardzo drobnej
# siatki 4px, dzięki czemu można dokładniej rozmieszczać obiekty na planie
# hali. Wartość jest importowana w wielu modułach (renderowanie, A*,
# kontroler), dlatego trzymamy ją w jednym miejscu.
GRID_STEP = 4

# Nazwa pliku przechowującego definicje hal.
HALLS_FILE = "hale.json"

# Kolor linii siatki tła.
BG_GRID_COLOR = "#2e323c"

# Kolor obrysu hal.
HALL_OUTLINE = "#ff4b4b"

# Słownik warstw Canvas. Mniejsze wartości oznaczają obiekty rysowane bardziej
# "w tle". Dzięki temu łatwo kontrolować kolejność wyświetlania elementów.
LAYERS = {
    "background": 0,
    "grid": 10,
    "walls": 20,
    "machines": 30,
    "overlays": 40,
    "routes": 50,
}

