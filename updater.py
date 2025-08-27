# Wersja pliku: 1.2.3
# Plik: updater.py
# Zmiany 1.2.3 (2025-08-18):
# - Wymuszenie ciemnego tła dla TFrame i TLabelframe (spójny theme w całej zakładce)
# - Zachowane: Git pull, update z .zip (z backupem), restore z backups/,
#   tabela wersji (.py) z przyciskami Odśwież/Kopiuj, log + autorestart.
# ⏹ KONIEC KODU

import os
import sys
import re
import json
import shutil
import zipfile
import subprocess
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

LOGS_DIR = Path("logs")
BACKUP_DIR = Path("backups")

# --- utils ---

def _now_stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def _ensure_dirs():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

def _write_log(stamp: str, text: str, kind: str = "update"):
    _ensure_dirs()
    p = LOGS_DIR / f"{kind}_{stamp}.log"
    with p.open("a", encoding="utf-8") as f:
        f.write(text.rstrip() + "\n")


def load_last_update_info() -> str:
    """Return info about the last update.

    Reads the latest entry from ``logi_wersji.json`` and returns a
    user-facing string with the timestamp.  If the file is missing or
    malformed, a fallback string is returned.
    """

    try:
        with open("logi_wersji.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and data:
            return f"Ostatnia aktualizacja: {data[-1].get('data', '')}"
    except Exception:
        pass

    try:
        with open("CHANGES_PROFILES_UPDATE.txt", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("Data:"):
                    return f"Ostatnia aktualizacja: {line.split('Data:')[1].strip()}"
    except Exception:
        pass

    return "brak danych o aktualizacjach"

def _restart_app():
    python = sys.executable
    os.execl(python, python, *sys.argv)

# --- backup / restore ---

def _backup_files(file_list, stamp):
    """Kopiuje pliki do backups/<stamp>/, zachowując strukturę."""
    dest_root = BACKUP_DIR / stamp
    for rel in file_list:
        src = Path(rel)
        if src.exists() and src.is_file():
            dest = dest_root / src
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(src, dest)
            except Exception as e:
                _write_log(stamp, f"[WARN] Backup fail: {src} :: {e}", kind="update")
    return dest_root

def _restore_backup(stamp: str):
    """Przywraca backup o podanym znaczniku czasu."""
    src_root = BACKUP_DIR / stamp
    if not src_root.exists():
        raise FileNotFoundError(f"Backup {stamp} nie istnieje.")
    restored = []
    for root, _dirs, files in os.walk(src_root):
        for f in files:
            src_file = Path(root) / f
            rel_path = src_file.relative_to(src_root)
            dst_file = Path(rel_path)
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)
            restored.append(str(rel_path))
    _write_log(stamp, "[RESTORE] Przywrócono:\n" + "\n".join(restored), kind="restore")
    return restored

def _list_backups():
    _ensure_dirs()
    return sorted([d.name for d in BACKUP_DIR.iterdir() if d.is_dir()])

# --- update methods ---

def _extract_zip_overwrite(zip_path: Path, stamp: str):
    """Rozpakowuje ZIP nadpisując istniejące pliki. Tworzy backup tylko nadpisywanych."""
    changed = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for zi in zf.infolist():
            if zi.is_dir():
                continue
            rel_path = Path(zi.filename)
            # bezpieczeństwo: nie pozwól wychodzić ponad katalog
            if ".." in rel_path.parts:
                continue
            changed.append(str(rel_path))

    _backup_files(changed, stamp)

    with zipfile.ZipFile(zip_path, "r") as zf:
        for zi in zf.infolist():
            if zi.is_dir():
                continue
            rel_path = Path(zi.filename)
            if ".." in rel_path.parts:
                continue
            rel_path.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(zi, "r") as src, open(rel_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
    return changed


def _git_has_updates(cwd: Path) -> bool:
    """Sprawdza, czy zdalne repozytorium zawiera nowe commity.

    Wykonuje ``git fetch`` oraz ``git rev-list HEAD..origin/<branch>``.
    Zwraca ``True`` jeśli dostępne są aktualizacje lub ``False`` w
    przeciwnym przypadku. W razie błędów subprocess zwraca ``False`` i
    zapisuje informację do logu.
    """
    try:
        # aktualizacja odniesień zdalnych
        subprocess.run(
            ["git", "fetch"],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )

        # ustalenie bieżącej gałęzi
        proc_branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        branch = proc_branch.stdout.strip()

        # sprawdzenie różnic między HEAD a origin/<branch>
        proc_rev = subprocess.run(
            ["git", "rev-list", f"HEAD..origin/{branch}"],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        return bool(proc_rev.stdout.strip())
    except subprocess.SubprocessError as e:
        _write_log(_now_stamp(), f"[WARN] git update check failed: {e}")
        return False
    except Exception as e:
        _write_log(_now_stamp(), f"[WARN] git update check failed: {e}")
        return False


def _run_git_pull(cwd: Path, stamp: str):
    """Wykonuje git pull w katalogu aplikacji."""
    cmd = ["git", "pull"]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        log_text = "[GIT PULL OUTPUT]\n" + result.stdout
        if result.stderr:
            log_text += "\n[GIT PULL ERROR]\n" + result.stderr
        _write_log(stamp, log_text, kind="update")
        return result.stdout
    except subprocess.CalledProcessError as e:
        log_text = "[GIT PULL OUTPUT]\n" + (e.stdout or "") + "\n[GIT PULL ERROR]\n" + (e.stderr or "")
        _write_log(stamp, log_text, kind="update")
        raise RuntimeError(f"git pull failed: {e.stderr.strip()}")

# --- version scanner ---

_SKIP_DIRS = {".git", "__pycache__", "venv", ".venv", "logs", "backups", "dist", "build", ".idea", ".vscode"}
_RX_VERSION = re.compile(r"^#\s*Wersja pliku:\s*(.+)$", re.M)

def _iter_python_files(root: Path):
    """Rekurencyjnie iteruje po .py z pominięciem katalogów ze _SKIP_DIRS."""
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for fname in files:
            if fname.endswith(".py"):
                yield Path(base) / fname

def _read_head(path: Path, max_chars: int = 4000) -> str:
    """Czyta tylko początek pliku (dla szybkości)."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(max_chars)
    except Exception:
        return ""

def _scan_versions(start_dir: Path = Path(".")):
    """Zwraca listę (plik, wersja) dla wszystkich .py z nagłówkiem '# Wersja pliku:'."""
    entries = []
    for p in _iter_python_files(start_dir.resolve()):
        head = _read_head(p)
        m = _RX_VERSION.search(head)
        if m:
            ver = m.group(1).strip()
            try:
                rel = p.relative_to(Path.cwd())
            except Exception:
                rel = p
            entries.append((str(rel).replace("\\", "/"), ver))
    # sort: najpierw pliki w katalogu głównym, potem alfabetycznie
    entries.sort(key=lambda t: (t[0].count("/"), t[0].lower()))
    return entries

def _versions_to_text(rows):
    return "\n".join(f"{fname} {ver}" for fname, ver in rows)

# --- theme helpers ---

def _style_exists(stylename: str) -> bool:
    try:
        st = ttk.Style()
        return bool(st.layout(stylename))
    except Exception:
        return False

def _theme_colors():
    st = ttk.Style()
    bg = st.lookup("TFrame", "background") or st.lookup(".", "background") or "#1e1e1e"
    fg = st.lookup("TLabel", "foreground") or st.lookup(".", "foreground") or "#e6e6e6"
    sel = st.lookup("Treeview", "fieldbackground") or "#2b2b2b"
    acc = st.lookup("TButton", "background") or "#3a3a3a"
    return bg, fg, sel, acc

# --- UI ---

class UpdatesUI(ttk.Frame):
    """
    Zakładka "Aktualizacje" do Ustawień.
    Udostępnia:
      - git pull
      - update z pliku .zip (z backupem)
      - przywrócenie poprzedniej wersji (restore z backups/)
      - podgląd aktualnych wersji plików (z nagłówków)
    """
    def __init__(self, master):
        super().__init__(master)
        self._build()
        self._apply_local_theme()

    def _build(self):
        self.columnconfigure(0, weight=1)

        ttk.Label(self, text="Aktualizacje Warsztat Menager", font=("Segoe UI", 12, "bold"))\
            .grid(row=0, column=0, sticky="w", padx=8, pady=(8,4))

        ttk.Label(self, text="Pobierz z Git / wgraj ZIP / cofnij do backupu. Poniżej wersje plików.")\
            .grid(row=1, column=0, sticky="w", padx=8, pady=(0,8))

        # status repozytorium
        self.status_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.status_var)\
            .grid(row=2, column=0, sticky="w", padx=8)

        # przyciski akcji
        btns = ttk.Frame(self)
        btns.grid(row=3, column=0, sticky="ew", padx=8, pady=8)
        for i in range(3):
            btns.columnconfigure(i, weight=1)

        self.git_button = ttk.Button(btns, text="Pobierz z Git (git pull)", command=self._on_git_pull)
        self.git_button.grid(row=0, column=0, sticky="ew", padx=(0,4))
        self.git_button.state(["disabled"])  # domyślnie nieaktywne, dopóki nie sprawdzimy statusu
        ttk.Button(btns, text="Wgraj paczkę .zip (lokalnie)", command=self._on_zip_update)\
            .grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(btns, text="Cofnij aktualizację (restore)", command=self._on_restore)\
            .grid(row=0, column=2, sticky="ew", padx=(4,0))

        # log/wyjście tekstowe
        self.out = tk.Text(self, height=10, highlightthickness=0, bd=0)
        self.out.grid(row=4, column=0, sticky="nsew", padx=8, pady=(4,8))
        self.rowconfigure(4, weight=1)

        # sekcja wersji
        ver_frame = ttk.LabelFrame(self, text="Aktualne wersje plików (.py)")
        ver_frame.grid(row=5, column=0, sticky="nsew", padx=8, pady=(0,8))
        ver_frame.columnconfigure(0, weight=1)
        ver_frame.rowconfigure(1, weight=1)

        # toolbar dla wersji
        tb = ttk.Frame(ver_frame)
        tb.grid(row=0, column=0, sticky="ew", padx=8, pady=(8,4))
        ttk.Button(tb, text="Odśwież listę", command=self._refresh_versions).pack(side="left")
        ttk.Button(tb, text="Kopiuj listę", command=self._copy_versions).pack(side="left", padx=(8,0))

        # Treeview (fallback stylu jeśli nie masz własnego WM.Treeview)
        style_tv = "WM.Treeview" if _style_exists("WM.Treeview") else "Treeview"
        self.tree = ttk.Treeview(ver_frame, columns=("plik", "wersja"), show="headings", height=10, style=style_tv)
        self.tree.heading("plik", text="Plik")
        self.tree.heading("wersja", text="Wersja")
        self.tree.column("plik", width=420, anchor="w")
        self.tree.column("wersja", width=140, anchor="center")
        self.tree.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0,8))

        yscroll = ttk.Scrollbar(ver_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        yscroll.grid(row=1, column=1, sticky="ns", pady=(0,8))

        # startowe odświeżenie listy wersji
        self._refresh_versions()

        # sprawdzenie stanu repozytorium względem zdalnego
        self.check_remote_status()

    def _apply_local_theme(self):
        """
        Wyrównanie wyglądu zakładki do ciemnego motywu:
        - tło całej zakładki (Frame),
        - ciemny LabelFrame,
        - ciemny Text (log),
        - fallback Treeview jeśli nie istnieje styl WM.Treeview,
        - wymuszenie ciemnego tła dla TFrame/TLabelframe.
        """
        bg, fg, sel, _ = _theme_colors()

        # całe tło zakładki
        try:
            if _style_exists("WM.Card.TFrame"):
                self.configure(style="WM.Card.TFrame")
            else:
                self.configure(bg=bg)
        except Exception:
            pass

        # Text (log)
        try:
            self.out.configure(bg=bg, fg=fg, insertbackground=fg)
        except Exception:
            pass

        # Treeview fallback (jeśli brak dedykowanego stylu WM.Treeview)
        st = ttk.Style()
        if not _style_exists("WM.Treeview"):
            st.configure("Treeview",
                         background=bg,
                         fieldbackground=bg,
                         foreground=fg,
                         borderwidth=0)
            st.map("Treeview",
                   background=[("selected", sel)],
                   foreground=[("selected", fg)])

        # LabelFrame i jego etykieta – na ciemno
        st.configure("TLabelframe", background=bg, foreground=fg, borderwidth=0)
        st.configure("TLabelframe.Label", background=bg, foreground=fg)

        # 🔥 KLUCZ: wymuszenie ciemnego tła na wszystkich ramkach
        st.configure("TFrame", background=bg)

    # --- helpers ---

    def _append_out(self, msg: str):
        try:
            self.out.insert("end", msg + "\n")
            self.out.see("end")
            self.update_idletasks()
        except Exception:
            pass

    def check_remote_status(self):
        """Sprawdza zdalny status repozytorium i aktualizuje UI."""
        try:
            subprocess.run(["git", "fetch"], cwd=str(Path.cwd()),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            proc = subprocess.run([
                "git", "rev-list", "--count", "HEAD..@{u}"
            ], cwd=str(Path.cwd()), stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, check=True)
            behind = int(proc.stdout.strip() or "0")
        except Exception:
            behind = 0

        if behind > 0:
            self.status_var.set(f"Dostępne aktualizacje: {behind}")
            try:
                self.git_button.state(["!disabled"])
            except Exception:
                pass
            self._append_out("[INFO] Dostępne są aktualizacje. Użyj 'Pobierz z Git'.")
        else:
            self.status_var.set("Repozytorium aktualne")
            try:
                self.git_button.state(["disabled"])
            except Exception:
                pass

    # --- actions ---

    def _on_git_pull(self):
        stamp = _now_stamp()
        try:
            self._append_out("[INFO] Rozpoczynam git pull…")
            output = _run_git_pull(Path.cwd(), stamp)
            self._append_out(output.strip() or "[INFO] Brak nowych zmian.")
            self.check_remote_status()
            messagebox.showinfo("Aktualizacje", "Zaktualizowano z Git. Program uruchomi się ponownie.")
            _restart_app()
        except Exception as e:
            _write_log(stamp, f"[ERROR] git pull: {e}", kind="update")
            messagebox.showerror("Aktualizacje", f"Błąd git pull:\n{e}")

    def _on_zip_update(self):
        zip_path = filedialog.askopenfilename(
            title="Wybierz paczkę ZIP z aktualizacją",
            filetypes=[("Paczki ZIP", "*.zip")]
        )
        if not zip_path:
            return
        stamp = _now_stamp()
        try:
            self._append_out(f"[INFO] Import paczki: {zip_path}")
            changed = _extract_zip_overwrite(Path(zip_path), stamp)
            self._append_out(f"[INFO] Nadpisano plików: {len(changed)}")
            for c in changed[:80]:
                self._append_out(f" - {c}")
            if len(changed) > 80:
                self._append_out(" - … (lista skrócona w UI, pełna w logu)")
            _write_log(stamp, "[INFO] ZIP updated files:\n" + "\n".join(changed), kind="update")
            self.check_remote_status()
            messagebox.showinfo("Aktualizacje", "Wgrano paczkę. Program uruchomi się ponownie.")
            _restart_app()
        except Exception as e:
            _write_log(stamp, f"[ERROR] ZIP update: {e}", kind="update")
            messagebox.showerror("Aktualizacje", f"Błąd podczas importu ZIP:\n{e}")

    def _on_restore(self):
        backups = _list_backups()
        if not backups:
            messagebox.showwarning("Przywracanie", "Brak dostępnych backupów w katalogu 'backups/'.")
            return

        dlg = tk.Toplevel(self)
        dlg.title("Wybierz backup do przywrócenia")
        dlg.geometry("460x380")
        try:
            dlg.transient(self.winfo_toplevel())
            dlg.grab_set()
        except Exception:
            pass

        # Lista backupów (dopasowanie do motywu)
        bg, fg, sel, _ = _theme_colors()
        try:
            dlg.configure(bg=bg)
        except Exception:
            pass

        ttk.Label(dlg, text="Dostępne backupy:", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=8, pady=(8,4))

        lb = tk.Listbox(dlg, height=12, highlightthickness=0, bd=0)
        try:
            lb.configure(bg=bg, fg=fg, selectbackground=sel, selectforeground=fg)
        except Exception:
            pass
        for b in backups:
            lb.insert("end", b)
        lb.pack(fill="both", expand=True, padx=8, pady=4)

        frm_btn = ttk.Frame(dlg)
        frm_btn.pack(fill="x", padx=8, pady=8)

        def _ok():
            sel_idx = lb.curselection()
            if not sel_idx:
                messagebox.showwarning("Przywracanie", "Wybierz backup z listy.")
                return
            chosen = lb.get(sel_idx[0])
            dlg.destroy()
            self._do_restore(chosen)

        ttk.Button(frm_btn, text="Przywróć", command=_ok).pack(side="right", padx=(4,0))
        ttk.Button(frm_btn, text="Anuluj", command=dlg.destroy).pack(side="right")

    def _do_restore(self, chosen_stamp: str):
        if not messagebox.askyesno(
            "Przywracanie",
            f"Czy na pewno przywrócić backup: {chosen_stamp}?\nAktualne pliki zostaną nadpisane."
        ):
            return
        try:
            self._append_out(f"[INFO] Przywracanie backupu {chosen_stamp}…")
            restored = _restore_backup(chosen_stamp)
            self._append_out(f"[INFO] Przywrócono plików: {len(restored)}")
            for r in restored[:80]:
                self._append_out(f" - {r}")
            if len(restored) > 80:
                self._append_out(" - … (lista skrócona w UI, pełna w logu)")
            self.check_remote_status()
            messagebox.showinfo("Przywracanie", "Przywrócono poprzednią wersję. Program uruchomi się ponownie.")
            _restart_app()
        except Exception as e:
            _write_log(chosen_stamp, f"[ERROR] RESTORE: {e}", kind="restore")
            messagebox.showerror("Przywracanie", f"Błąd przywracania:\n{e}")

    # --- versions UI ---

    def _refresh_versions(self):
        rows = _scan_versions(Path("."))
        for it in self.tree.get_children():
            self.tree.delete(it)
        for fname, ver in rows:
            self.tree.insert("", "end", values=(fname, ver))
        self._last_versions = rows

    def _copy_versions(self):
        rows = getattr(self, "_last_versions", [])
        text = _versions_to_text(rows)
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self._append_out("[INFO] Skopiowano listę wersji do schowka.")
        except Exception:
            self._append_out("[INFO] Nie udało się skopiować do schowka. Poniżej lista:")
            self._append_out(text)

# ⏹ KONIEC KODU
