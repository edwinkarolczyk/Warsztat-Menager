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

        ttk.Label(self, text="WebDAV URL:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(self, textvariable=self.url_var, width=40).grid(row=0, column=1, pady=2, sticky="ew")

        ttk.Label(self, text="Użytkownik:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(self, textvariable=self.user_var, width=40).grid(row=1, column=1, pady=2, sticky="ew")

        ttk.Label(self, text="Hasło:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(self, textvariable=self.pass_var, show="*", width=40).grid(row=2, column=1, pady=2, sticky="ew")

        ttk.Label(self, text="Folder docelowy:").grid(row=3, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(self, textvariable=self.folder_var, width=40).grid(row=3, column=1, pady=2, sticky="ew")

        ttk.Button(self, text="Zapisz", command=self.save).grid(row=4, column=0, columnspan=2, pady=6)

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
