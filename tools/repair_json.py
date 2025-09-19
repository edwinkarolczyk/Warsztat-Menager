# tools/repair_json.py
# Wersja: 1.0.0
# Cel:
# - Naprawa pliku data/maszyny/maszyny.json
# - Usunięcie BOM, normalizacja na UTF-8 + LF
# - Walidacja JSON

import os, io, json

TARGET = "data/maszyny/maszyny.json"

def main():
    if not os.path.isfile(TARGET):
        print("[ERROR] Nie znaleziono:", TARGET)
        return

    # Wczytaj z BOM
    with io.open(TARGET, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    # Nadpisz czystym UTF-8 i LF
    os.makedirs(os.path.dirname(TARGET), exist_ok=True)
    with open(TARGET, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("[INFO] Naprawiono i zapisano:", TARGET)
    print("[INFO] Maszyny:", len(data.get("maszyny", [])) if isinstance(data, dict) else len(data))

if __name__ == "__main__":
    main()
