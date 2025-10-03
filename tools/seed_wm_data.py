"""Generator przykładowych danych dla Warsztat Menagera."""

from __future__ import annotations

import json
import os
from datetime import date

from config_manager import ensure_root_dirs, get_config, resolve_rel


def _dump(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def seed_machines(cfg: dict) -> None:
    machines_path = resolve_rel(cfg, r"maszyny\maszyny.json")
    if not machines_path:
        return
    maszyny = [
        {"id": "M-001", "nazwa": "Tokarka CNC", "typ": "CNC", "lokalizacja": "Hala A"},
        {"id": "M-002", "nazwa": "Frezarka 3-osiowa", "typ": "FREZ", "lokalizacja": "Hala A"},
        {"id": "M-003", "nazwa": "Prasa", "typ": "PRASA", "lokalizacja": "Hala B"},
    ]
    _dump(machines_path, {"maszyny": maszyny})


def seed_tools(cfg: dict) -> None:
    tools_path = resolve_rel(cfg, r"narzedzia\narzedzia.json")
    if not tools_path:
        return
    narzedzia = [
        {"id": "T-001", "nazwa": "Klucz dynamometryczny", "status": "OK"},
        {"id": "T-002", "nazwa": "Suwmiarka 150 mm", "status": "OK"},
        {"id": "T-003", "nazwa": "Wiertło Ø8 HSS", "status": "zużyte"},
    ]
    _dump(tools_path, {"narzedzia": narzedzia})


def seed_orders(cfg: dict) -> None:
    orders_path = resolve_rel(cfg, r"zlecenia\zlecenia.json")
    if not orders_path:
        return
    zlecenia = [
        {"id": "Z-2025-001", "klient": "ACME", "status": "otwarte", "data": str(date.today())},
        {"id": "Z-2025-002", "klient": "BRAVO", "status": "w toku", "data": str(date.today())},
    ]
    _dump(orders_path, {"zlecenia": zlecenia})


def seed_stock(cfg: dict) -> None:
    stock_path = resolve_rel(cfg, r"magazyn\magazyn.json")
    if not stock_path:
        return
    magazyn = [
        {"kod": "MAT-001", "nazwa": "Blacha 2mm", "typ": "surowce", "ilosc": 50, "jm": "szt"},
        {"kod": "PP-010", "nazwa": "Konstrukcja A", "typ": "półprodukty", "ilosc": 5, "jm": "szt"},
        {"kod": "PRD-001", "nazwa": "Zespół PRD001", "typ": "produkty", "ilosc": 2, "jm": "szt"},
    ]
    _dump(stock_path, {"pozycje": magazyn})


def seed_all() -> None:
    cfg = get_config()
    ensure_root_dirs(cfg)
    seed_machines(cfg)
    seed_tools(cfg)
    seed_orders(cfg)
    seed_stock(cfg)


if __name__ == "__main__":
    seed_all()
    print("[SEED] Gotowe – utworzono przykładowe dane w <root>.")
