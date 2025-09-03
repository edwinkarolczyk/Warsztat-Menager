"""Migracja produktów ze starego pola ``BOM`` do ``polprodukty``."""

import glob
import json
import os

DATA_DIR = os.path.join("data", "produkty")


def migrate() -> None:
    """Przepisuje definicje produktów do nowego klucza ``polprodukty``."""
    for path in glob.glob(os.path.join(DATA_DIR, "*.json")):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        bom = data.pop("BOM", None)
        if not bom:
            continue
        polprodukty = []
        for poz in bom:
            kod = poz.get("kod_materialu", "")
            il = poz.get("ilosc", 1)
            sr = {"typ": kod}
            dl = poz.get("dlugosc_mm")
            if dl is not None:
                sr["dlugosc"] = dl
            polprodukty.append(
                {
                    "kod": kod,
                    "ilosc_na_szt": il,
                    "czynnosci": [],
                    "surowiec": sr,
                }
            )
        data["polprodukty"] = polprodukty
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Converted {os.path.basename(path)}")


if __name__ == "__main__":
    migrate()
