# Wersja: 1.4.4
# Layout ciemny + większa czcionka + wyszukiwanie + wyrównanie szczegółów

import tkinter as tk

class LayoutProsty(tk.Frame):
    def __init__(self, master, callback, tlo="#1e1e1e", kolor_tekstu="white"):
        super().__init__(master, bg=tlo)
        self.pack(fill="both", expand=True)
        self.callback = callback
        self.kolor_tekstu = kolor_tekstu
        self.tlo = tlo

        # Pasek szukania
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.filtruj_liste)
        entry = tk.Entry(self, textvariable=self.search_var, font=("Arial", 14))
        entry.pack(fill="x", padx=10, pady=5)

        # Układ główny
        main_frame = tk.Frame(self, bg=self.tlo)
        main_frame.pack(fill="both", expand=True)

        # Menu po lewej
        menu = tk.Frame(main_frame, width=200, bg="#2e2e2e")
        menu.pack(side="left", fill="y")
        for nazwa in ["Narzędzia", "Zlecenia", "Maszyny", "Historia", "Ustawienia"]:
            tk.Button(menu, text=nazwa, font=("Arial", 12), width=20,
                      bg="#444", fg="white", activebackground="#666",
                      command=lambda n=nazwa: self.callback(n)).pack(pady=5)

        # Panel główny (środek)
        self.panel = tk.Frame(main_frame, bg=self.tlo)
        self.panel.pack(side="right", fill="both", expand=True)

        self.label_szczegoly = tk.Label(self.panel, text="Szczegóły...", font=("Arial", 16), bg="#333",
                                        fg=self.kolor_tekstu, justify="left", anchor="w")
        self.label_szczegoly.pack(fill="x", padx=10, pady=(10, 0))

        self.label_szczegoly.config(wraplength=700)

        self.lista = tk.Listbox(self.panel, font=("Arial", 12), bg="black", fg="white",
                                selectbackground="#666", highlightbackground="#888")
        self.lista.pack(fill="both", expand=True, padx=10, pady=10)

        self.pelna_lista = []

    def ustaw_szczegoly(self, tekst):
        self.label_szczegoly.config(text=tekst)

    def ustaw_liste(self, elementy):
        self.pelna_lista = elementy
        self.filtruj_liste()

    def filtruj_liste(self, *args):
        tekst = self.search_var.get().lower()
        self.lista.delete(0, tk.END)
        for elem in self.pelna_lista:
            if tekst in elem.lower():
                self.lista.insert(tk.END, elem)
