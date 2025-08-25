# Wersja: 1.4.3
# Plik główny do uruchomienia programu Warsztat Menager

import os
import json
import tkinter as tk
from gui_logowanie import ekran_logowania

# Tworzenie wymaganych folderów
os.makedirs("rysunki", exist_ok=True)
os.makedirs("zdjecia", exist_ok=True)
os.makedirs("__pycache__", exist_ok=True)

# Tworzenie wymaganych plików, jeśli nie istnieją
if not os.path.exists("narzedzia.json"):
    with open("narzedzia.json", "w", encoding="utf-8") as f:
        json.dump({}, f)

if not os.path.exists("uzytkownicy.json"):
    with open("uzytkownicy.json", "w", encoding="utf-8") as f:
        json.dump({}, f)

if not os.path.exists("changelog.txt"):
    with open("changelog.txt", "w", encoding="utf-8") as f:
        f.write("Wersja 1.4.3 – utworzono automatycznie\n")

# Uruchomienie GUI
root = tk.Tk()
root.title("Warsztat Menager")
root.geometry("1000x700")
ekran_logowania(root)
root.mainloop()
