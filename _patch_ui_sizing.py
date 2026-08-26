from __future__ import annotations

import subprocess
from pathlib import Path

FILES = {
    Path("gui_maszyny.py"): "2a711223b1e8970574ac87827ce7916db8da63ee",
    Path("narzedzia_ui/list_panel.py"): "9fb72c04a3a337030480fb19ca0fedd695afcb2f",
    Path("narzedzia_ui/detail_view.py"): "f343d3a6a7a3de114d815d1a4f116debac15e419",
}


def blob_sha(path: Path) -> str:
    return subprocess.check_output(["git", "hash-object", str(path)], text=True).strip()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


for path, expected in FILES.items():
    actual = blob_sha(path)
    if actual != expected:
        raise RuntimeError(f"{path}: expected {expected}, got {actual}")

# Maszyny: tylko zmniejszenie czcionki tabel o 2 pkt, nadal bold.
p = Path("gui_maszyny.py")
text = p.read_text(encoding="utf-8")
text = replace_once(
    text,
    "# version: 1.7\n# Zmiany 1.7:\n",
    "# version: 1.8\n# Zmiany 1.8:\n# - Czcionka tabel Maszyn zmniejszona z 11 do 9 pkt; pozostaje pogrubiona.\n# Zmiany 1.7:\n",
    "machine version",
)
text = replace_once(
    text,
    'style.configure("Maszyny.Treeview", font=("Segoe UI", 11, "bold"), rowheight=30)',
    'style.configure("Maszyny.Treeview", font=("Segoe UI", 9, "bold"), rowheight=30)',
    "machine table font",
)
text = replace_once(
    text,
    'style.configure("Maszyny.Treeview.Heading", font=("Segoe UI", 11, "bold"))',
    'style.configure("Maszyny.Treeview.Heading", font=("Segoe UI", 9, "bold"))',
    "machine heading font",
)
p.write_text(text, encoding="utf-8")

# Narzędzia: większe główne okno listy.
p = Path("narzedzia_ui/list_panel.py")
text = p.read_text(encoding="utf-8")
text = replace_once(
    text,
    "# version: 1.1\n# Zmiany 1.1:\n",
    "# version: 1.2\n# Zmiany 1.2:\n# - Główne okno Narzędzi startuje większe i ma bezpieczny minimalny rozmiar.\n# Zmiany 1.1:\n",
    "tools list version",
)
text = replace_once(text, "    _DEFAULT_WIDTH = 900\n    _DEFAULT_HEIGHT = 540\n", "    _DEFAULT_WIDTH = 1180\n    _DEFAULT_HEIGHT = 700\n", "tools list geometry")
text = replace_once(
    text,
    '        self.window.geometry(f"{self._DEFAULT_WIDTH}x{self._DEFAULT_HEIGHT}")\n        ensure_theme_applied(self.window)\n',
    '        self.window.geometry(f"{self._DEFAULT_WIDTH}x{self._DEFAULT_HEIGHT}")\n        self.window.minsize(1000, 620)\n        self.window.resizable(True, True)\n        ensure_theme_applied(self.window)\n',
    "tools list minsize",
)
p.write_text(text, encoding="utf-8")

# Narzędzia: szczegóły nie mogą startować jako małe automatyczne okno Tk.
p = Path("narzedzia_ui/detail_view.py")
text = p.read_text(encoding="utf-8")
text = replace_once(
    text,
    '# version: 1.0\n"""Widok szczegółów narzędzia oparty o szablony zadań."""\n',
    '# version: 1.1\n# Zmiany 1.1:\n# - Okno szczegółów narzędzia ma większy rozmiar startowy i minimum, żeby nie ucinać treści.\n"""Widok szczegółów narzędzia oparty o szablony zadań."""\n',
    "tool detail version",
)
text = replace_once(
    text,
    '        self.window.title(f"Narzędzie {tool.get(\'id\', \'\')}")\n        ensure_theme_applied(self.window)\n',
    '        self.window.title(f"Narzędzie {tool.get(\'id\', \'\')}")\n        self.window.geometry("900x650")\n        self.window.minsize(800, 560)\n        self.window.resizable(True, True)\n        ensure_theme_applied(self.window)\n',
    "tool detail geometry",
)
p.write_text(text, encoding="utf-8")
