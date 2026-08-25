from pathlib import Path

path = Path("start.py")
text = path.read_text(encoding="utf-8")

old_header = '''# WM-VERSION: 0.1
# version: 1.1.4
# Moduł: start
# Zmiany 1.1.4:
'''
new_header = '''# WM-VERSION: 0.1
# version: 1.1.5
# Moduł: start
# Zmiany 1.1.5:
# - Dodano ekran sprawdzania aktualizacji z dużym animowanym spinnerem przed uruchomieniem WM.
# - Status pokazuje sprawdzanie, pobieranie oraz wynik aktualizacji; operacje Git działają poza wątkiem GUI.
# Zmiany 1.1.4:
'''
if text.count(old_header) != 1:
    raise SystemExit(f"header match count={text.count(old_header)}")
text = text.replace(old_header, new_header, 1)

old_imports = '''import logging
import subprocess
import shutil
from pathlib import Path
import tkinter as tk
'''
new_imports = '''import logging
import subprocess
import shutil
import threading
import queue
from pathlib import Path
import tkinter as tk
'''
if text.count(old_imports) != 1:
    raise SystemExit(f"imports match count={text.count(old_imports)}")
text = text.replace(old_imports, new_imports, 1)

old_signature = '''def _wm_git_check_on_start(
    preferred_branch: str | None = None,
):
    """Automatyczny check aktualizacji z repozytorium."""
'''
new_signature = '''def _wm_git_check_on_start(
    preferred_branch: str | None = None,
    status_callback=None,
):
    """Automatyczny check aktualizacji z repozytorium.

    ``status_callback`` jest opcjonalny i służy wyłącznie do prezentowania
    postępu w ekranie startowym. Sama logika Git pozostaje bez zmian.
    """

    def _status(message: str) -> None:
        if callable(status_callback):
            try:
                status_callback(message)
            except Exception:
                pass

    _status("Sprawdzam aktualizacje...")
'''
if text.count(old_signature) != 1:
    raise SystemExit(f"signature match count={text.count(old_signature)}")
text = text.replace(old_signature, new_signature, 1)

old_no_git = '''        if not shutil.which("git"):
            print("[WM-DBG][GIT] git.exe nie znaleziony – pomijam check.")
            return
'''
new_no_git = '''        if not shutil.which("git"):
            print("[WM-DBG][GIT] git.exe nie znaleziony – pomijam check.")
            _status("Git niedostępny — pomijam aktualizację")
            return "skipped"
'''
if text.count(old_no_git) != 1:
    raise SystemExit(f"no_git match count={text.count(old_no_git)}")
text = text.replace(old_no_git, new_no_git, 1)

old_detect = '''                print(
                    "[WM-DBG][GIT] Wykryto nowsze commity w origin, wykonuję git pull --rebase..."
                )
                pull_proc = subprocess.run(
'''
new_detect = '''                print(
                    "[WM-DBG][GIT] Wykryto nowsze commity w origin, wykonuję git pull --rebase..."
                )
                _status("Pobieram aktualizację WM...")
                pull_proc = subprocess.run(
'''
if text.count(old_detect) != 1:
    raise SystemExit(f"detect match count={text.count(old_detect)}")
text = text.replace(old_detect, new_detect, 1)

old_pull_result = '''                if pull_proc.returncode == 0:
                    print("[WM-DBG][GIT] Aktualizacja lokalnego repo zakończona.")
                else:
                    print(
                        "[WM-DBG][GIT] git pull --rebase zakończony kodem "
                        f"{pull_proc.returncode}."
                    )
        else:
            print("[WM-DBG][GIT] Repozytorium aktualne, brak zmian.")
'''
new_pull_result = '''                if pull_proc.returncode == 0:
                    print("[WM-DBG][GIT] Aktualizacja lokalnego repo zakończona.")
                    _status("Aktualizacja zakończona ✓")
                    result = "updated"
                else:
                    print(
                        "[WM-DBG][GIT] git pull --rebase zakończony kodem "
                        f"{pull_proc.returncode}."
                    )
                    _status("Błąd pobierania aktualizacji")
                    result = "error"
            if status_proc.returncode == 0 and status_proc.stdout.strip():
                _status("Pominięto aktualizację — lokalne zmiany")
                result = "skipped"
        else:
            print("[WM-DBG][GIT] Repozytorium aktualne, brak zmian.")
            _status("WM jest aktualny ✓")
            result = "current"
'''
if text.count(old_pull_result) != 1:
    raise SystemExit(f"pull_result match count={text.count(old_pull_result)}")
text = text.replace(old_pull_result, new_pull_result, 1)

old_tail = '''        if ahead > 0:
            print(
                "[WM-DBG][GIT] Lokalny branch jest przed origin – brak automatycznych akcji."
            )

    except Exception as exc:
        print(f"[WM-DBG][GIT] Wyjątek w _wm_git_check_on_start: {exc}")


# ====== MAIN ======
'''
new_tail = '''        if ahead > 0:
            print(
                "[WM-DBG][GIT] Lokalny branch jest przed origin – brak automatycznych akcji."
            )

        return locals().get("result", "current")
    except Exception as exc:
        print(f"[WM-DBG][GIT] Wyjątek w _wm_git_check_on_start: {exc}")
        _status("Nie udało się sprawdzić aktualizacji")
        return "error"


def _wm_git_update_splash() -> str:
    """Pokaż prosty ekran aktualizacji i wykonaj Git poza wątkiem Tk."""

    try:
        splash = tk.Tk()
    except Exception:
        return _wm_git_check_on_start()

    splash.title("Warsztat Menager — aktualizacja")
    splash.configure(bg="#111214")
    splash.resizable(False, False)
    width, height = 520, 330
    try:
        sx = (splash.winfo_screenwidth() - width) // 2
        sy = (splash.winfo_screenheight() - height) // 2
        splash.geometry(f"{width}x{height}+{sx}+{sy}")
    except Exception:
        splash.geometry(f"{width}x{height}")

    try:
        splash.attributes("-topmost", True)
    except Exception:
        pass

    tk.Label(
        splash,
        text="Warsztat Menager",
        font=("Segoe UI", 22, "bold"),
        bg="#111214",
        fg="#f3f4f6",
    ).pack(pady=(28, 8))

    canvas = tk.Canvas(
        splash,
        width=120,
        height=120,
        bg="#111214",
        highlightthickness=0,
    )
    canvas.pack(pady=(8, 12))
    arc = canvas.create_arc(
        16,
        16,
        104,
        104,
        start=0,
        extent=260,
        style="arc",
        width=10,
        outline="#e5e7eb",
    )

    status_var = tk.StringVar(value="Sprawdzam aktualizacje...")
    tk.Label(
        splash,
        textvariable=status_var,
        font=("Segoe UI", 13),
        bg="#111214",
        fg="#d1d5db",
    ).pack(pady=(4, 4))

    tk.Label(
        splash,
        text="Nie zamykaj programu podczas pobierania zmian.",
        font=("Segoe UI", 9),
        bg="#111214",
        fg="#9ca3af",
    ).pack(pady=(0, 12))

    events: queue.Queue[tuple[str, str]] = queue.Queue()
    result_box = {"value": "current"}
    animation = {"angle": 0, "running": True}

    def _animate() -> None:
        if not animation["running"]:
            return
        animation["angle"] = (animation["angle"] - 18) % 360
        try:
            canvas.itemconfigure(arc, start=animation["angle"])
        except Exception:
            return
        splash.after(45, _animate)

    def _worker() -> None:
        result = _wm_git_check_on_start(
            status_callback=lambda message: events.put(("status", message))
        )
        events.put(("done", str(result or "current")))

    def _poll() -> None:
        try:
            while True:
                kind, value = events.get_nowait()
                if kind == "status":
                    status_var.set(value)
                elif kind == "done":
                    result_box["value"] = value
                    animation["running"] = False
                    if value == "updated":
                        status_var.set("Aktualizacja zakończona ✓")
                    elif value == "current":
                        status_var.set("WM jest aktualny ✓")
                    elif value == "skipped":
                        status_var.set("Aktualizacja pominięta")
                    else:
                        status_var.set("Nie udało się sprawdzić aktualizacji")
                    splash.after(650 if value in {"updated", "current"} else 1000, splash.destroy)
                    return
        except queue.Empty:
            pass
        splash.after(70, _poll)

    threading.Thread(target=_worker, name="wm-startup-git", daemon=True).start()
    _animate()
    _poll()
    try:
        splash.mainloop()
    finally:
        try:
            if splash.winfo_exists():
                splash.destroy()
        except Exception:
            pass
    return result_box["value"]


# ====== MAIN ======
'''
if text.count(old_tail) != 1:
    raise SystemExit(f"tail match count={text.count(old_tail)}")
text = text.replace(old_tail, new_tail, 1)

old_bottom = '''    BOOTSTRAP_ACTIVE = False
    try:
        _wm_git_check_on_start()
    finally:
        BOOTSTRAP_ACTIVE = True
    main()
'''
new_bottom = '''    BOOTSTRAP_ACTIVE = False
    try:
        _wm_git_update_splash()
    finally:
        BOOTSTRAP_ACTIVE = True
    main()
'''
if text.count(old_bottom) != 1:
    raise SystemExit(f"bottom match count={text.count(old_bottom)}")
text = text.replace(old_bottom, new_bottom, 1)

path.write_text(text, encoding="utf-8")
print("patched start.py with startup update spinner")
