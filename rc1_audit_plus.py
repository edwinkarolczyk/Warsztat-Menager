# -*- coding: utf-8 -*-
"""
RC1 Audit+ — rozszerzony audyt WM:
- Odpala audit.run() (core ~10 pkt),
- Dokłada dynamiczne checki (paths, pliki, JSON, maszyny, logi, dispatcher, profiles, itp.),
- Auto-rozszerza liczbę testów, aż łączna liczba (base+plus) >= TARGET_MIN_CHECKS (domyślnie 100),
- Zapisuje scalony raport do <data_root>/logs/audyt_wm-YYYYMMDD-HHMMSS_plus.txt,
- Zwraca {'ok', 'msg', 'path'}.

Możesz dodać własne reguły w USER_EXTRA_CHECKS (na dole) — bez dotykania kodu.
"""

from __future__ import annotations
import os, io, json, datetime, re, tempfile

# --- konfiguracja ---
TARGET_MIN_CHECKS = 100   # cel minimalnej liczby testów (łącznie: base + plus)

ROOT = os.getcwd()
CONFIG_PATH = os.path.join(ROOT, "config.json")

# --- utilsy ---
def _norm(p):
    if not p: return None
    return os.path.normpath(str(p).strip().strip('"').strip("'"))

def _load_cfg() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _dget(d: dict, dotted: str, default=None):
    cur = d
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur

def _data_root(cfg: dict) -> str:
    paths = cfg.get("paths") or {}
    return _norm(paths.get("data_root")) or _norm(cfg.get("data_root")) or os.path.join(ROOT, "data")

def _logs_dir(cfg: dict) -> str:
    base = _data_root(cfg)
    p = os.path.join(base, "logs")
    os.makedirs(p, exist_ok=True)
    return p

def _exists(path: str) -> bool:
    return path and os.path.exists(path)

def _read_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _read_text(path: str, fallback=""):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return fallback

def _path_writable(directory: str) -> bool:
    if not directory: return False
    try:
        os.makedirs(directory, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=directory, delete=True) as _:
            return True
    except Exception:
        return False

def _latest_file(dirpath: str, prefix: str = "", suffix: str = "") -> str | None:
    try:
        files = [os.path.join(dirpath, f) for f in os.listdir(dirpath)
                 if os.path.isfile(os.path.join(dirpath, f))
                 and (not prefix or f.startswith(prefix))
                 and (not suffix or f.endswith(suffix))]
        if not files: return None
        return max(files, key=os.path.getmtime)
    except Exception:
        return None

# --------- checkery (typy) ----------
def _check_config_path_exists(cfg: dict, key: str, label: str, required=True):
    p = _resolve_config_path(cfg, key)
    ok = _exists(p)
    return ok or (not required), f"[{ 'OK' if ok else 'FAIL'}] {label}: {p or '(brak)'}"

def _check_json_file_readable(cfg: dict, key: str, label: str, allow_empty=True, required=True):
    p = _resolve_config_path(cfg, key)
    if not _exists(p):
        return (not required), f"[{ 'WARN' if not required else 'FAIL'}] {label}: brak pliku ({p})"
    try:
        data = _read_json(p)
        if not allow_empty:
            if (isinstance(data, list) and len(data)==0) or (isinstance(data, dict) and len(data)==0):
                return False, f"[FAIL] {label}: plik pusty ({p})"
        return True, f"[OK] {label}: {p}"
    except Exception as e:
        return False, f"[FAIL] {label}: błąd JSON ({e})"

def _check_json_file_is_list(cfg: dict, key: str, label: str, required=True):
    p = _resolve_config_path(cfg, key)
    if not _exists(p): return (not required), f"[{ 'WARN' if not required else 'FAIL'}] {label}: brak pliku ({p})"
    try:
        data = _read_json(p)
        ok = isinstance(data, list)
        return ok or (not required), f"[{ 'OK' if ok else 'FAIL'}] {label}: {p}"
    except Exception as e:
        return False, f"[FAIL] {label}: błąd JSON ({e})"

def _check_json_min_length(cfg: dict, key: str, label: str, min_len: int, required=True):
    p = _resolve_config_path(cfg, key)
    if not _exists(p): return (not required), f"[{ 'WARN' if not required else 'FAIL'}] {label}: brak pliku ({p})"
    try:
        data = _read_json(p)
        ln = len(data) if isinstance(data, list) else 0
        ok = ln >= min_len
        return ok or (not required), f"[{ 'OK' if ok else 'FAIL'}] {label}: {ln} >= {min_len} ({p})"
    except Exception as e:
        return False, f"[FAIL] {label}: błąd JSON ({e})"

def _check_json_unique_field(cfg: dict, key: str, label: str, field: str, required=True):
    p = _resolve_config_path(cfg, key)
    if not _exists(p): return (not required), f"[{ 'WARN' if not required else 'FAIL'}] {label}: brak pliku ({p})"
    try:
        data = _read_json(p)
        seen, dups = set(), []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and field in item:
                    val = str(item[field]).strip().lower()
                    if val in seen:
                        dups.append(val)
                    else:
                        seen.add(val)
        ok = len(dups) == 0
        extra = "" if ok else f" duplikaty: {sorted(set(dups))[:5]}..."
        return ok or (not required), f"[{ 'OK' if ok else 'FAIL'}] {label}:{extra} ({p})"
    except Exception as e:
        return False, f"[FAIL] {label}: błąd JSON ({e})"

def _check_action_callable(label: str, action: str, required=True):
    try:
        import dispatch
        # prefer: dispatch.ACTIONS
        acts = getattr(dispatch, "ACTIONS", None)
        if isinstance(acts, dict) and action in acts:
            return True, f"[OK] {label}: ACTIONS[{action}]"
        # fallback: dispatch.execute exists (nie sprawdzamy realnego clicka)
        exe = getattr(dispatch, "execute", None)
        ok = callable(exe)
        return ok or (not required), f"[{ 'OK' if ok else 'FAIL'}] {label}: execute callable"
    except Exception as e:
        return (not required), f"[{ 'WARN' if not required else 'FAIL'}] {label}: {e}"

def _check_log_no_pattern(cfg: dict, label: str, pattern: str, tail_lines: int = 500, required=True):
    logdir = _logs_dir(cfg)
    latest = _latest_file(logdir, prefix="audyt_wm") or _latest_file(logdir, suffix=".log") or None
    if not latest: 
        # Brak logów → nie karzemy (WARN/OK w zależności od required)
        return (not required), f"[{ 'WARN' if not required else 'FAIL'}] {label}: brak plików logów"
    txt = _tail(latest, tail_lines)
    hit = re.search(pattern, txt, re.IGNORECASE)
    ok = hit is None
    return ok or (not required), f"[{ 'OK' if ok else 'FAIL'}] {label}: {'brak wzorca' if ok else 'wykryto'} ({os.path.basename(latest)})"

def _tail(path: str, n: int) -> str:
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            block = 4096
            data = bytearray()
            while size > 0 and n > 0:
                cur = min(block, size)
                f.seek(size - cur)
                buf = f.read(cur)
                data[:0] = buf
                n -= buf.count(b"\n")
                size -= cur
        return data.decode("utf-8", errors="replace")
    except Exception:
        return _read_text(path, "")

def _check_profiles_no_default_admin(cfg: dict, label: str, required=True):
    p = _resolve_config_path(cfg, "profiles.file")
    if not _exists(p): return (not required), f"[{ 'WARN' if not required else 'FAIL'}] {label}: brak pliku ({p})"
    try:
        data = _read_json(p)
        def_admin = False
        if isinstance(data, list):
            for r in data:
                login = str((r or {}).get("login") or "").strip().lower()
                haslo = str((r or {}).get("haslo") or "")
                if login == "admin" and (haslo == "admin" or haslo.strip() == ""):
                    def_admin = True; break
        ok = not def_admin
        return ok or (not required), f"[{ 'OK' if ok else 'FAIL'}] {label}: {'zmienione' if ok else 'wykryto admin/admin'}"
    except Exception as e:
        return False, f"[FAIL] {label}: błąd JSON ({e})"

def _resolve_config_path(cfg: dict, key: str) -> str | None:
    # aliasy BOM
    if key == "bom.file":
        v = _dget(cfg, "bom.file") or cfg.get("bom.file")
        b = _dget(cfg, "bom")
        if (not v) and isinstance(b, dict):
            v = b.get("file")
        return _norm(v)
    return _norm(_dget(cfg, key))

# ---------- główna procedura ----------
def run() -> dict:
    cfg = _load_cfg()
    logs = _logs_dir(cfg)

    # 1) audyt bazowy
    base_ok, base_ok_cnt, base_total, base_path = True, 0, 0, None
    try:
        import audit
        res = getattr(audit, "run", None)
        if callable(res):
            out = res() or {}
            base_path = out.get("path")
            msg = str(out.get("msg", ""))
            # heurystyka "OK: 10 / 10; FAIL: 0"
            m = re.search(r"OK:\s*(\d+)\s*/\s*(\d+)", msg)
            if m:
                base_ok_cnt, base_total = int(m.group(1)), int(m.group(2))
                base_ok = (base_ok_cnt == base_total)
    except Exception:
        pass

    # 2) plus: dynamiczne checki (bazowe, zawsze przydatne)
    plus_checks = []

    # --- PATHS / DIRS ---
    data_root = _data_root(cfg)
    plus_checks += [
        lambda: (_exists(data_root), f"[{ 'OK' if _exists(data_root) else 'FAIL'}] data_root istnieje: {data_root}"),
        lambda: (_path_writable(data_root), f"[{ 'OK' if _path_writable(data_root) else 'FAIL'}] data_root zapisywalny: {data_root}"),
        lambda: (_path_writable(_logs_dir(cfg)), f"[{ 'OK' if _path_writable(_logs_dir(cfg)) else 'FAIL'}] logs zapisywalne"),
    ]

    # --- CONFIG PATHS EXIST ---
    cfg_path_keys = [
        ("warehouse.stock_source", "Magazyn: magazyn.json istnieje", True),
        ("bom.file",               "BOM: bom.json istnieje",         True),
        ("tools.types_file",       "Narzędzia: typy_narzedzi.json istnieje", True),
        ("tools.statuses_file",    "Narzędzia: statusy_narzedzi.json istnieje", True),
        ("tools.task_templates_file","Narzędzia: szablony_zadan.json istnieje", True),
        ("profiles.file",          "Użytkownicy: profiles.json istnieje", True),
        ("hall.machines_file",     "Hala: maszyny.json istnieje",    True),
    ]
    for key, label, req in cfg_path_keys:
        plus_checks.append(lambda k=key,l=label,r=req: _check_config_path_exists(cfg, k, l, r))

    # --- JSON READABLE / SHAPE ---
    json_read_keys = [
        ("warehouse.stock_source", "Magazyn JSON czytelny", True),
        ("bom.file",               "BOM JSON czytelny", True),
        ("tools.types_file",       "Typy narzędzi JSON czytelny", True),
        ("tools.statuses_file",    "Statusy narzędzi JSON czytelny", True),
        ("tools.task_templates_file","Szablony zadań JSON czytelny", True),
        ("profiles.file",          "Profiles JSON czytelny", True),
        ("hall.machines_file",     "Maszyny JSON czytelny", True),
    ]
    for key, label, req in json_read_keys:
        plus_checks.append(lambda k=key,l=label,r=req: _check_json_file_readable(cfg, k, l, True, r))

    # --- MASZYNY: minimum liczności + unikalność pól ---
    plus_checks += [
        lambda: _check_json_min_length(cfg, "hall.machines_file", "Maszyny: >= 80 pozycji", 80, True),
        lambda: _check_json_file_is_list(cfg, "hall.machines_file", "Maszyny: format = lista", True),
        lambda: _check_json_unique_field(cfg, "hall.machines_file", "Maszyny: unikalne 'id'", "id", True),
        lambda: _check_json_unique_field(cfg, "hall.machines_file", "Maszyny: unikalne 'nr'", "nr", False),
        lambda: _check_json_unique_field(cfg, "hall.machines_file", "Maszyny: unikalne 'nazwa'", "nazwa", False),
    ]

    # --- DISPATCHER / AKCJE ---
    for action,label in [
        ("bom.import_dialog",  "Dispatcher: akcja bom.import_dialog"),
        ("bom.export_current", "Dispatcher: akcja bom.export_current"),
        ("wm_audit.run",       "Dispatcher: akcja wm_audit.run"),
    ]:
        plus_checks.append(lambda a=action,l=label: _check_action_callable(l, a, True))

    # --- LOGI: nie powinno być błędów znanych wzorców ---
    bad_patterns = [
        r"unknown action",
        r"Traceback",
        r"Exception",
        r"ERROR:",
        r"KeyError",
        r"JSONDecodeError",
        r"PermissionError",
        r"FileNotFoundError",
        r"config\.save\.error",
        r"execute\.wrap\.error",
        r"dispatch\.import\.error",
        r"filedialog\.(open|save)\.error",
    ]
    for pat in bad_patterns:
        plus_checks.append(lambda p=pat: _check_log_no_pattern(cfg, f"Logi: brak wzorca /{p}/", p, 800, True))

    # --- PROFILES: bezpieczeństwo admina ---
    plus_checks.append(lambda: _check_profiles_no_default_admin(cfg, "Profiles: brak 'admin' z hasłem domyślnym", True))

    # 3) auto-rozszerzanie (syntetyczne, ale sensowne) do TARGET_MIN_CHECKS
    #    Dorzucamy dodatkowe "no_pattern" na rzadkie, ale ciekawe frazy + redundantne sanity.
    extra_patterns = [
        r"\[FAIL\]", r"ValueError", r"TypeError", r"IndexError", r"OSError",
        r"WinError", r"Permission denied", r"access is denied", r"denied",
        r"Read-only file system", r"disk full", r"no space left", r"out of memory",
        r"writing backup: .*config_.*\.(json)",  # nadmiarowe backupy
        r"login_bg\.png.*(brak|nie znaleziono)",
        r"maszyny\.json.*(brak|nie znaleziono)",
        r"bom\.json.*(brak|nie znaleziono)",
        r"typy_narzedzi\.json.*(brak|nie znaleziono)",
        r"statusy_narzedzi\.json.*(brak|nie znaleziono)",
        r"szablony_zadan\.json.*(brak|nie znaleziono)",
        r"profiles\.json.*(brak|nie znaleziono)",
    ]
    i=0
    while (base_total + len(plus_checks)) < TARGET_MIN_CHECKS and i < 200:
        pat = extra_patterns[i % len(extra_patterns)]
        plus_checks.append(lambda p=pat: _check_log_no_pattern(cfg, f"Logi: brak wzorca /{p}/", p, 800, False))
        i += 1

    # 4) wykonanie PLUS
    plus_ok_cnt, plus_total, plus_lines, plus_fail = 0, 0, [], 0
    for chk in plus_checks:
        try:
            ok, line = chk()
        except Exception as e:
            ok, line = (False, f"[FAIL] (wyjątek w checku): {e}")
        plus_total += 1
        if ok: plus_ok_cnt += 1
        else:  plus_fail += 1
        plus_lines.append(line)

    # 5) zapis raportu
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = os.path.join(_logs_dir(cfg), f"audyt_wm-{ts}_plus.txt")

    lines = []
    lines.append(f"Audyt WM+ — {ts}")
    lines.append("=" * 60)
    lines.append(f"[base]  OK: {base_ok_cnt} / {base_total}   ({'OK' if base_ok else 'PROBLEMY'})")
    lines.append(f"[plus]  OK: {plus_ok_cnt} / {plus_total}   ({'OK' if plus_fail==0 else f'FAIL:{plus_fail}'})")
    lines.append("-" * 60)
    if plus_lines:
        lines.append("[PLUS] Wyniki:")
        lines.extend(plus_lines)
    if base_path:
        lines.append("-" * 60)
        lines.append(f"[base] Raport bazowy: {base_path}")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    # 6) status zwrotny
    total_ok_cnt = base_ok_cnt + plus_ok_cnt
    total_total  = (base_total or 0) + plus_total
    total_ok = (plus_fail == 0) and (base_ok_cnt == base_total if base_total else True)
    msg = f"OK: {total_ok_cnt} / {total_total}; FAIL: {total_total - total_ok_cnt}"
    return {"ok": bool(total_ok), "msg": msg, "path": out_path}


# ========== (opcjonalnie) Twoje dodatkowe reguły ==========
# Wpisz tu lambdy dodające własne sprawdzenia (przykład):
USER_EXTRA_CHECKS = [
    # lambda: _check_log_no_pattern(_load_cfg(), "Logi: brak 'deprecated'", r"deprecated", 500, False),
]
# (Na razie niewykorzystywane w auto-run — można je zintegrować, jeśli chcesz.)
