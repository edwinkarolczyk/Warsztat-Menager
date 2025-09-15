# utils/moduly.py
# Wersja pliku: 1.0.0 (2025-09-15)
# Zmiany:
# - Nowy loader manifestu modułów (PL) + walidacja zależności + tag do logów.
# - Brak wpływu na istniejącą logikę; wyłącznie funkcje pomocnicze.

from __future__ import annotations
import json
import os
from typing import Dict, List, Any

_MANIFEST_CACHE: Dict[str, Any] | None = None


class ManifestBlad(Exception):
    """Błąd związany z manifestem modułów."""


def _wczytaj_json(sciezka: str) -> Dict[str, Any]:
    if not os.path.exists(sciezka):
        raise ManifestBlad(f"[ERROR] Brak pliku manifestu modułów: {sciezka}")
    with open(sciezka, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise ManifestBlad(f"[ERROR] Niepoprawny JSON w {sciezka}: {e}") from e


def zaladuj_manifest(sciezka: str = "data/moduly_manifest.json") -> Dict[str, Any]:
    """
    Ładuje i cache'uje manifest modułów.
    """
    global _MANIFEST_CACHE
    if _MANIFEST_CACHE is not None:
        return _MANIFEST_CACHE
    manifest = _wczytaj_json(sciezka)
    # Walidacja minimalna
    if "rdzen" not in manifest or "moduly" not in manifest:
        raise ManifestBlad("[ERROR] Manifest musi zawierać klucze: 'rdzen' i 'moduly'.")
    if not isinstance(manifest["moduly"], list):
        raise ManifestBlad("[ERROR] 'moduly' musi być listą.")
    _MANIFEST_CACHE = manifest
    return manifest


def pobierz_modul(modul_id: str, manifest: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Zwraca definicję modułu wg 'id'. Specjalny 'rdzen' zwraca sekcję rdzenia.
    """
    man = manifest or zaladuj_manifest()
    if modul_id == "rdzen":
        return man["rdzen"]
    for m in man["moduly"]:
        if m.get("id") == modul_id:
            return m
    raise ManifestBlad(f"[ERROR] Nie znaleziono modułu o id='{modul_id}'.")


def lista_modulow(manifest: Dict[str, Any] | None = None) -> List[str]:
    """
    Zwraca listę ID wszystkich modułów (bez 'rdzen').
    """
    man = manifest or zaladuj_manifest()
    return [m.get("id") for m in man["moduly"]]


def zaleznosci(modul_id: str, manifest: Dict[str, Any] | None = None) -> List[str]:
    """
    Zwraca listę ID modułów, z których dany moduł korzysta (korzysta_z).
    """
    mod = pobierz_modul(modul_id, manifest)
    return list(mod.get("korzysta_z", []))


def sprawdz_reguly(manifest: Dict[str, Any] | None = None) -> List[str]:
    """
    Sprawdza sekcję 'reguly' i zwraca listę ostrzeżeń/błędów (stringi).
    Na dziś: tylko raport tekstowy (bez podnoszenia wyjątków).
    """
    man = manifest or zaladuj_manifest()
    komunikaty: List[str] = []
    reguly = man.get("reguly", [])
    # Prosta weryfikacja istnienia modułów wskazanych w regułach
    znane = set(lista_modulow(man) + ["rdzen"])
    for r in reguly:
        a = r.get("modul")
        b = r.get("musi_startowac_przed")
        if a not in znane:
            komunikaty.append(f"[WARN] Reguła odwołuje się do nieznanego modułu: {a}")
        if b not in znane:
            komunikaty.append(f"[WARN] Reguła odwołuje się do nieznanego modułu: {b}")
    return komunikaty


def assert_zaleznosci_gotowe(modul_id: str, zainicjowane: List[str], manifest: Dict[str, Any] | None = None) -> None:
    """
    Dla danego modułu sprawdza, czy wszystkie 'korzysta_z' znajdują się na liście zainicjowanych.
    Jeśli nie – rzuca ManifestBlad z czytelnym komunikatem PL.
    """
    deps = zaleznosci(modul_id, manifest)
    brak = [d for d in deps if d not in zainicjowane]
    if brak:
        raise ManifestBlad(
            "[ERROR] Moduł '{0}' wymaga wcześniejszej inicjalizacji: {1}".format(
                modul_id, ", ".join(brak)
            )
        )


def tag_logu(modul_id: str) -> str:
    """
    Zwraca ujednolicony tag do logów, np. '[WM-DBG][mod:magazyn]'
    """
    return f"[WM-DBG][mod:{modul_id}]"


# ⏹ KONIEC KODU
