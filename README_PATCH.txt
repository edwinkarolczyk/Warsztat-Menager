PATCH: H2c + theme fallback + user files
- Podmień gui_profil.py na ten z paczki.
- Theme: jeśli ui_theme.apply_theme nie działa, panel profil wymusi 'clam' (fallback).
- Pliki użytkownika tworzą się automatycznie przy wejściu: data/user/<login>.json.
  Domyślna struktura:
  {
    "login": "edwin",
    "rola": "brygadzista",
    "stanowisko": "",
    "dzial": "",
    "zmiana": "I",
    "zmiana_godz": "06:00-14:00",
    "telefon": "",
    "email": "",
    "avatar": "",
    "odpowiedzialnosci": []
  }
- Overrides pozostają w data/profil_overrides/* (assign_orders.json, assign_tools.json, status_<login>.json).
