# Plik: test_kreator_gui.py
# Wersja pliku: 0.1.0
# Zmiany:
# - Kreator testowy GUI do automatycznego sprawdzania działania logowania i kliknięć
# - Testuje obecność pola PIN, przycisku i logo
# - Zapisuje logi testowe do test_log_gui.txt
#
# Autor: AI – Idea: Edwin Karolczyk

import tkinter as tk
import time
import pyautogui
import os

def zapisz_log(wiadomosc):
    with open("test_log_gui.txt", "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} – {wiadomosc}\n")

zapisz_log("[START] Uruchomiono kreator testu GUI")

# Sprawdzenie obecności okna i pól (manualnie uruchamiasz gui_logowanie.py)
time.sleep(2)

# Szukanie pola PIN i kliknięcie (jeśli znalezione)
pin_input = pyautogui.locateOnScreen("pin_input.png", confidence=0.8)
if pin_input:
    zapisz_log("Znaleziono pole PIN – klikam")
    pyautogui.click(pin_input)
    time.sleep(0.5)
    pyautogui.write("1")
else:
    zapisz_log("Nie znaleziono pola PIN")

# Szukanie przycisku „Zaloguj” i kliknięcie
btn = pyautogui.locateOnScreen("btn_login.png", confidence=0.8)
if btn:
    zapisz_log("Znaleziono przycisk Zaloguj – klikam")
    pyautogui.click(btn)
else:
    zapisz_log("Nie znaleziono przycisku Zaloguj")

zapisz_log("[STOP] Zakończono test GUI")
print("Test zakończony – logi zapisane do test_log_gui.txt")
