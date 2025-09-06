#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kreator sprawdzania plikow i wersji – Warsztat Menager
Wersja narzedzia: 1.3.0 (ASCII-only output)

Uruchomienie (przyklad):
    python kreator_sprawdzenia.py --root "C:\sciezka\do\WM" --report raport_sprawdzenia.txt --pause

Funkcje:
- Skanuje katalog projektu i sprawdza:
  * wersje plikow po naglowku: "# Wersja pliku: X.Y.Z"
  * istnienie kluczowych plikow
  * minimalne klucze w config.json
  * obecnosci folderow danych (narzedzia/, data/produkty/)
- Zapisuje wynik do pliku tekstowego oraz wypisuje na konsole (ASCII: [OK]/[WARN]/[ERR])

Konfiguracja oczekiwanych wersji:
- Jesli w katalogu root jest plik "versions_expected.json", zostanie wczytany i nadpisze wbudowane wartosci.
- Format (przyklad):
  {
    "start.py": {"min": "1.0.2"},
    "gui_logowanie.py": {"min": "1.4.12.1"},
    "gui_panel.py": {"min": "1.6.13"},
    "gui_narzedzia.py": {"min": "1.5.9"}
  }

Uwaga:
- Skrypt NIE modyfikuje zadnych plikow.
- Wszystkie komunikaty i znaki sa w ASCII, aby uniknac problemow z konsola Windows.
"""

import os
import re
import json
import argparse
from datetime import datetime

TOOL_VERSION = "1.3.0"

# Wbudowane oczekiwane wersje (moga byc nadpisane przez versions_expected.json)
DEFAULT_EXPECTED = {
    "start.py": {"min": "1.0.2"},
    "gui_logowanie.py": {"min": "1.4.12.1"},
    "gui_panel.py": {"min": "1.6.13"},
    "gui_narzedzia.py": {"min": "1.5.9"},
    "gui_maszyny.py": {"min": "1.0.1"},
    "gui_zlecenia.py": {"min": "1.0.1"},
    "zlecenia_logika.py": {"min": "1.0.0"},
    "gui_uzytkownicy.py": {"min": "1.0.1"},
    "ui_theme.py": {"min": "1.0.0"},
    "ustawienia_systemu.py": {"min": "1.0.0"},
    "modul_serwisowy.py": {"min": "0.9.0"},
    "logger.py": {"min": "1.0.2"},
}

CHECK_FILES = list(DEFAULT_EXPECTED.keys())

VERSION_REGEX = re.compile(r"Wersja\s+pliku:\s*([0-9][0-9a-zA-Z\.\-\_]*)")

REQUIRED_PATHS = [
    "narzedzia",                # folder z plikami narzedzi
    "data",                     # folder danych
    os.path.join("data", "produkty"),  # folder BOM
    os.path.join("data", "magazyn"),   # folder magazynu
]

CONFIG_MIN_KEYS = [
    ("sciezka_danych",),
    ("narzedzia","typy"),
    ("narzedzia","komentarze","wg_statusu"),
]

def parse_args():
    ap = argparse.ArgumentParser(description="Kreator sprawdzania plikow i wersji – Warsztat Menager")
    ap.add_argument("--root", default=".", help="Katalog glowny projektu (domyslnie: .)")
    ap.add_argument("--report", default=None, help="Sciezka pliku raportu TXT (domyslnie: raport_sprawdzenia.txt w katalogu root)")
    ap.add_argument("--pause", action="store_true", help="Na koniec wcisnij Enter (dla Windows)")
    ap.add_argument("--write-sample", action="store_true", help="Zapisz przykladowy versions_expected.sample.json i wyjdz")
    return ap.parse_args()

def read_text_head(path, max_bytes=16384):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(max_bytes)
    except Exception as e:
        return ""

def extract_version_from_text(text):
    m = VERSION_REGEX.search(text)
    if m:
        return m.group(1).strip()
    return None

def version_tuple(v):
    # Konwertuj "1.4.12.2" -> (1,4,12,2); litery sa ignorowane
    parts = []
    for p in re.split(r"[.\-_\s]+", v.strip()):
        if p.isdigit():
            parts.append(int(p))
        else:
            # wyciagnij wiodace cyfry
            m = re.match(r"(\d+)", p)
            if m:
                parts.append(int(m.group(1)))
            else:
                # brak liczby -> 0
                parts.append(0)
    return tuple(parts) if parts else (0,)

def compare_versions(found, expected):
    """Zwraca: 0 = rowne, 1 = found > expected, -1 = found < expected"""
    tf = version_tuple(found)
    te = version_tuple(expected)
    # porownaj krotki (dopelnij do tej samej dlugosci)
    maxlen = max(len(tf), len(te))
    tf += (0,) * (maxlen - len(tf))
    te += (0,) * (maxlen - len(te))
    if tf == te: return 0
    return 1 if tf > te else -1

def load_expected_versions(root):
    cfg_path = os.path.join(root, "versions_expected.json")
    data = DEFAULT_EXPECTED.copy()
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                user = json.load(f)
            # scal slowniki
            for k,v in user.items():
                data[k] = v
        except Exception as e:
            pass
    return data

def check_file_version(root, fname, expected_cfg):
    fpath = os.path.join(root, fname)
    if not os.path.isfile(fpath):
        return ("ERR", f"{fname} – file not found", None, None)

    text = read_text_head(fpath)
    ver = extract_version_from_text(text)
    if ver is None:
        return ("WARN", f"{fname} – no version header found", None, None)

    exp = expected_cfg.get(fname)
    if not exp:
        return ("OK", f"{fname} – version {ver} (no expectation set)", ver, None)

    # exp moze byc {"min": "x"} lub {"eq": "x"} lub {"oneof": ["a","b"]}
    if "eq" in exp:
        eq = exp["eq"]
        if ver == eq:
            return ("OK", f"{fname} – version OK ({ver})", ver, eq)
        else:
            return ("WARN", f"{fname} – version mismatch (found {ver}, expected {eq})", ver, eq)
    elif "oneof" in exp:
        allowed = exp["oneof"]
        if ver in allowed:
            return ("OK", f"{fname} – version OK ({ver})", ver, allowed)
        else:
            return ("WARN", f"{fname} – version mismatch (found {ver}, allowed {allowed})", ver, allowed)
    else:
        # min
        minv = exp.get("min", "0")
        cmp = compare_versions(ver, minv)
        if cmp >= 0:
            return ("OK", f"{fname} – version >= {minv} (found {ver})", ver, minv)
        else:
            return ("WARN", f"{fname} – version too low (found {ver}, min {minv})", ver, minv)

def check_required_paths(root):
    results = []
    for rel in REQUIRED_PATHS:
        path = os.path.join(root, rel)
        if os.path.isdir(path):
            results.append(("OK", f"path OK: {rel}"))
        else:
            results.append(("WARN", f"path missing: {rel}"))
    # dodatkowo sprawdz pliki
    from logika_magazyn import MAGAZYN_PATH

    for relf in [
        os.path.join("data", "maszyny.json"),
        MAGAZYN_PATH,
        "config.json",
    ]:
        p = os.path.join(root, relf)
        if os.path.isfile(p):
            results.append(("OK", f"file OK: {relf}"))
        else:
            results.append(("WARN", f"file missing: {relf}"))
    return results

def check_config_min_keys(root):
    p = os.path.join(root, "config.json")
    if not os.path.isfile(p):
        return [("ERR", "config.json not found"),]

    try:
        with open(p, "r", encoding="utf-8") as f:
            content = "\n".join(
                line for line in f if not line.lstrip().startswith("#")
            )
            cfg = json.loads(content) if content.strip() else {}
    except Exception as e:
        return [("ERR", "config.json cannot be parsed as JSON"),]

    out = []
    for path in CONFIG_MIN_KEYS:
        cur = cfg
        ok = True
        for key in path:
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                ok = False
                break
        if ok:
            out.append(("OK", "config key OK: " + " / ".join(path)))
        else:
            out.append(("WARN", "config key missing: " + " / ".join(path)))
    return out

def write_sample_versions(root):
    sample = {
        "start.py": {"min": "1.0.2"},
        "gui_logowanie.py": {"min": "1.4.12.1"},
        "gui_panel.py": {"min": "1.6.13"},
        "gui_narzedzia.py": {"min": "1.5.9"},
        "gui_maszyny.py": {"min": "1.0.1"},
        "gui_zlecenia.py": {"min": "1.1.2"},
        "zlecenia_logika.py": {"min": "1.1.2"},
        "gui_uzytkownicy.py": {"min": "1.0.1"},
        "ui_theme.py": {"min": "1.0.0"},
        "ustawienia_systemu.py": {"min": "1.0.0"},
        "modul_serwisowy.py": {"min": "0.9.0"},
        "logger.py": {"min": "1.0.2"}
    }
    path = os.path.join(root, "versions_expected.sample.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(sample, f, indent=2, ensure_ascii=False)
        return path
    except Exception:
        return None

def main():
    args = parse_args()
    root = os.path.abspath(args.root)
    if args.report is None:
        report_path = os.path.join(root, "raport_sprawdzenia.txt")
    else:
        report_path = os.path.abspath(args.report)

    if False:  # placeholder, flag handled via getattr  # this will be fixed below because hyphen is invalid in code, we will handle via getattr
        pass

    # Bezpieczne obejscie błedu nazwy flagi write-sample (brak myslnika w atrybucie)
    write_sample = getattr(args, "write_sample", False)
    if write_sample:
        outp = write_sample_versions(root)
        if outp:
            print("[OK] Wrote sample versions file:", outp)
        else:
            print("[ERR] Could not write sample versions file.")
        return

    expected = load_expected_versions(root)

    lines = []
    hdr = "Sprawdzanie plikow i wersji – Warsztat Menager"
    lines.append(hdr)
    lines.append("Tool version: " + TOOL_VERSION)
    lines.append("Project root: " + root)
    lines.append("Generated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    lines.append("-" * 60)

    # 1) Wersje plikow
    lines.append("Pliki i wersje:")
    for fname in CHECK_FILES:
        status, msg, found, exp = check_file_version(root, fname, expected)
        lines.append("  [{0}] {1}".format(status, msg))

    # 2) Sciezki i pliki
    lines.append("")
    lines.append("Sciezki i pliki:")
    for status, msg in check_required_paths(root):
        lines.append("  [{0}] {1}".format(status, msg))

    # 3) Config
    lines.append("")
    lines.append("Config (minimalne klucze):")
    for status, msg in check_config_min_keys(root):
        lines.append("  [{0}] {1}".format(status, msg))

    # Zapis raportu
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print("[OK] Raport zapisany:", report_path)
    except Exception as e:
        print("[ERR] Nie udalo sie zapisac raportu:", e)

    # Wypisz na konsole
    print()
    for ln in lines:
        print(ln)

    if args.pause:
        try:
            input("\nPress Enter to continue . . . ")
        except Exception:
            pass

if __name__ == "__main__":
    main()
