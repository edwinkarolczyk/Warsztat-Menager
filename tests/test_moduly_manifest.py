# tests/test_moduly_manifest.py
# Szybki smoke test manifestu (nie zmienia działania programu).
from utils.moduly import zaladuj_manifest, lista_modulow, pobierz_modul, zaleznosci


def test_manifest_smoke():
    man = zaladuj_manifest()
    mods = lista_modulow(man)
    assert "magazyn" in mods
    assert "zlecenia" in mods
    z = pobierz_modul("zlecenia", man)
    assert "magazyn" in zaleznosci("zlecenia", man)
