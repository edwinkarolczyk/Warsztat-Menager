from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from config_manager import ConfigManager


class BackupCloudSettings(ttk.Frame):
    """Frame with controls for WebDAV backup configuration."""

    def __init__(self, master: tk.Misc):
        super().__init__(master)
        self.cfg = ConfigManager()

        self.url_var = tk.StringVar(value=self.cfg.get("backup.cloud.url", ""))
        self.user_var = tk.StringVar(value=self.cfg.get("backup.cloud.username", ""))
        self.pass_var = tk.StringVar(value=self.cfg.get("backup.cloud.password", ""))
        self.folder_var = tk.StringVar(value=self.cfg.get("backup.cloud.folder", ""))
        row = 0
        ttk.Label(
            self,
            text="Kopia w chmurze",
            font=("TkDefaultFont", 12, "bold"),
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=5, pady=(0, 8))
        row += 1

        ttk.Label(self, text="WebDAV URL:").grid(row=row, column=0, sticky="w", padx=5, pady=(5, 0))
        ttk.Entry(self, textvariable=self.url_var, width=40).grid(
            row=row, column=1, pady=(5, 0), sticky="ew"
        )
        row += 1
        ttk.Label(
            self,
            text="Adres serwera WebDAV.",
            font=("", 8),
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=5, pady=(0, 5))
        row += 1

        ttk.Label(self, text="Użytkownik:").grid(row=row, column=0, sticky="w", padx=5, pady=(5, 0))
        ttk.Entry(self, textvariable=self.user_var, width=40).grid(
            row=row, column=1, pady=(5, 0), sticky="ew"
        )
        row += 1
        ttk.Label(self, text="Login do serwera.", font=("", 8)).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=5, pady=(0, 5)
        )
        row += 1

        ttk.Label(self, text="Hasło:").grid(row=row, column=0, sticky="w", padx=5, pady=(5, 0))
        ttk.Entry(self, textvariable=self.pass_var, show="*", width=40).grid(
            row=row, column=1, pady=(5, 0), sticky="ew"
        )
        row += 1
        ttk.Label(self, text="Hasło do WebDAV.", font=("", 8)).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=5, pady=(0, 5)
        )
        row += 1

        ttk.Label(self, text="Folder docelowy:").grid(row=row, column=0, sticky="w", padx=5, pady=(5, 0))
        ttk.Entry(self, textvariable=self.folder_var, width=40).grid(
            row=row, column=1, pady=(5, 0), sticky="ew"
        )
        row += 1
        ttk.Label(
            self,
            text="Docelowy katalog w chmurze.",
            font=("", 8),
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=5, pady=(0, 5))
        row += 1

        ttk.Button(self, text="Zapisz", command=self.save).grid(
            row=row, column=0, columnspan=2, pady=6
        )

        self.columnconfigure(1, weight=1)

    def save(self) -> None:
        self.cfg.set("backup.cloud.url", self.url_var.get())
        self.cfg.set("backup.cloud.username", self.user_var.get())
        self.cfg.set("backup.cloud.password", self.pass_var.get())
        self.cfg.set("backup.cloud.folder", self.folder_var.get())
        self.cfg.save_all()


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Ustawienia kopii w chmurze")
    BackupCloudSettings(root).pack(fill="both", expand=True, padx=10, pady=10)
    root.mainloop()
