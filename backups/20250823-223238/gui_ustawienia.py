# Warsztat Menager - gui_ustawienia.py (profiles + presence tabs, role-aware)
def panel_ustawien(root, frame):
    import json
    from tkinter import ttk

    # wipe
    try:
        for w in frame.winfo_children():
            w.destroy()
    except Exception:
        pass

    cfg = globals().get("config", {})
    if not isinstance(cfg, dict): cfg = {}

    nb = ttk.Notebook(frame); nb.pack(fill="both", expand=True, padx=6, pady=6)

    cu = globals().get("CURRENT_USER") or {}
    rola = str(cu.get("rola") or "").lower()
    admin_roles = {"admin","kierownik","brygadzista","lider"}
    read_only = rola not in admin_roles

    def _save_cfg(newcfg):
        try:
            cm = globals().get("CONFIG_MANAGER")
            if cm and hasattr(cm, "save_config"):
                cm.config = newcfg; cm.save_config()
            else:
                with open("config.json","w",encoding="utf-8") as f:
                    json.dump(newcfg,f,ensure_ascii=False,indent=2)
            globals()["config"] = newcfg
        except Exception as e:
            print("[SETTINGS-DBG] save failed:", e)

    _wm_build_profiles_settings_tab(nb, cfg, _save_cfg, read_only=read_only)
    _wm_build_presence_settings_tab(nb, cfg, _save_cfg, read_only=read_only)


def _wm_build_profiles_settings_tab(nb, cfg, save_cb, read_only=False):
    from tkinter import ttk, StringVar, BooleanVar, filedialog
    tab = ttk.Frame(nb, style="WM.TFrame"); nb.add(tab, text="Profile użytkowników")
    ttk.Label(tab, text="Ustawienia profili użytkowników", style="WM.H2.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(8,6))
    pr = cfg.get("profiles", {}) or {}
    v_tab = BooleanVar(value=bool(pr.get("tab_enabled", True)))
    v_hdr = BooleanVar(value=bool(pr.get("show_name_in_header", True)))
    fields_val = pr.get("fields_visible", ["login","nazwa","rola","zmiana"])
    if isinstance(fields_val, list): fields_val = ", ".join(fields_val)
    v_fields = StringVar(value=str(fields_val))
    v_avatar = StringVar(value=str(pr.get("avatar_dir","")))

    ttk.Checkbutton(tab, text="Włącz zakładkę „Profil”", variable=v_tab).grid(row=1, column=0, sticky="w")
    ttk.Checkbutton(tab, text="Pokaż nazwę w nagłówku", variable=v_hdr).grid(row=2, column=0, sticky="w")
    ttk.Label(tab, text="Widoczne pola (CSV):").grid(row=3, column=0, sticky="w"); e_fields = ttk.Entry(tab, textvariable=v_fields, width=40); e_fields.grid(row=3, column=1, sticky="w")
    ttk.Label(tab, text="Folder avatarów:").grid(row=4, column=0, sticky="w"); e_avatar = ttk.Entry(tab, textvariable=v_avatar, width=40); e_avatar.grid(row=4, column=1, sticky="w")
    def _browse():
        d = filedialog.askdirectory()
        if d: v_avatar.set(d)
    ttk.Button(tab, text="Przeglądaj…", command=_browse).grid(row=4, column=2, sticky="w")

    def _save():
        cfg.setdefault("profiles", {})
        cfg["profiles"]["tab_enabled"] = bool(v_tab.get())
        cfg["profiles"]["show_name_in_header"] = bool(v_hdr.get())
        cfg["profiles"]["fields_visible"] = [x.strip() for x in v_fields.get().split(",") if x.strip()]
        cfg["profiles"]["avatar_dir"] = v_avatar.get().strip()
        save_cb(cfg)
    btn = ttk.Button(tab, text="Zapisz", command=_save); btn.grid(row=5, column=0, pady=10, sticky="w")
    if read_only:
        for ch in tab.winfo_children():
            try:
                if ch is not btn: ch.configure(state="disabled")
            except Exception: pass
        ttk.Label(tab, text="(Brak uprawnień do edycji)", style="WM.Muted.TLabel").grid(row=5, column=1, sticky="w")


def _wm_build_presence_settings_tab(nb, cfg, save_cb, read_only=False):
    from tkinter import ttk, IntVar, StringVar, DoubleVar
    tab = ttk.Frame(nb, style="WM.TFrame"); nb.add(tab, text="Obecność")
    ttk.Label(tab, text="Ustawienia obecności", style="WM.H2.TLabel").grid(row=0, column=0, columnspan=4, sticky="w", pady=(8,6))

    pres = cfg.get("presence", {}) or {}
    v_hb  = IntVar(value=int(pres.get("heartbeat_sec", 30)))
    v_win = IntVar(value=int(pres.get("online_window_sec", 120)))
    v_gr  = IntVar(value=int(pres.get("grace_min", 15)))
    def _get_shift_val(name, key, default):
        return StringVar(value=str(pres.get("shifts", {}).get(name, {}).get(key, default)))
    v_I_s = _get_shift_val("I","start","06:00"); v_I_e = _get_shift_val("I","end","14:00")
    v_II_s= _get_shift_val("II","start","14:00"); v_II_e= _get_shift_val("II","end","22:00")
    v_III_s=_get_shift_val("III","start","22:00"); v_III_e=_get_shift_val("III","end","06:00")

    ttk.Label(tab, text="Heartbeat (sek):").grid(row=1, column=0, sticky="w"); hb = ttk.Spinbox(tab, from_=5, to=600, increment=5, textvariable=v_hb, width=8); hb.grid(row=1, column=1, sticky="w")
    ttk.Label(tab, text="Okno ONLINE (sek):").grid(row=2, column=0, sticky="w"); ow = ttk.Spinbox(tab, from_=30, to=900, increment=10, textvariable=v_win, width=8); ow.grid(row=2, column=1, sticky="w")
    ttk.Label(tab, text="Tolerancja spóźnienia (min):").grid(row=3, column=0, sticky="w"); gr = ttk.Spinbox(tab, from_=0, to=120, increment=5, textvariable=v_gr, width=8); gr.grid(row=3, column=1, sticky="w")

    ttk.Label(tab, text="Zmiana I (start–koniec):").grid(row=4, column=0, sticky="w")
    i1 = ttk.Entry(tab, textvariable=v_I_s, width=8); i1.grid(row=4, column=1, sticky="w")
    i2 = ttk.Entry(tab, textvariable=v_I_e, width=8); i2.grid(row=4, column=2, sticky="w")
    ttk.Label(tab, text="Zmiana II (start–koniec):").grid(row=5, column=0, sticky="w")
    i3 = ttk.Entry(tab, textvariable=v_II_s, width=8); i3.grid(row=5, column=1, sticky="w")
    i4 = ttk.Entry(tab, textvariable=v_II_e, width=8); i4.grid(row=5, column=2, sticky="w")
    ttk.Label(tab, text="Zmiana III (start–koniec):").grid(row=6, column=0, sticky="w")
    i5 = ttk.Entry(tab, textvariable=v_III_s, width=8); i5.grid(row=6, column=1, sticky="w")
    i6 = ttk.Entry(tab, textvariable=v_III_e, width=8); i6.grid(row=6, column=2, sticky="w")

    ttk.Separator(tab, orient="horizontal").grid(row=7, column=0, columnspan=4, sticky="we", pady=8)
    ttk.Label(tab, text="Uprawnienia (domyślne)", style="WM.H2.TLabel").grid(row=8, column=0, columnspan=4, sticky="w")
    leaves = cfg.get("leaves", {}) or {}; ents = (leaves.get("entitlements") or {})
    v_urlop = DoubleVar(value=float(ents.get("urlop_rocznie", 26)))
    v_l4lim = DoubleVar(value=float(ents.get("l4_limit_rocznie", 33)))
    ur = ttk.Spinbox(tab, from_=0, to=52, increment=0.5, textvariable=v_urlop, width=8); lr = ttk.Spinbox(tab, from_=0, to=365, increment=0.5, textvariable=v_l4lim, width=8)
    ttk.Label(tab, text="Urlop rocznie (dni):").grid(row=9, column=0, sticky="w"); ur.grid(row=9, column=1, sticky="w")
    ttk.Label(tab, text="L4 limit rocznie (dni):").grid(row=10, column=0, sticky="w"); lr.grid(row=10, column=1, sticky="w")

    def _save():
        cfg.setdefault("presence", {})
        cfg["presence"]["heartbeat_sec"] = int(v_hb.get())
        cfg["presence"]["online_window_sec"] = int(v_win.get())
        cfg["presence"]["grace_min"] = int(v_gr.get())
        cfg["presence"]["shifts"] = {
            "I": {"start": v_I_s.get().strip(), "end": v_I_e.get().strip()},
            "II":{"start": v_II_s.get().strip(), "end": v_II_e.get().strip()},
            "III":{"start": v_III_s.get().strip(), "end": v_III_e.get().strip()}
        }
        cfg.setdefault("leaves", {}); cfg["leaves"]["entitlements"] = {"urlop_rocznie": float(v_urlop.get()), "l4_limit_rocznie": float(v_l4lim.get())}
        save_cb(cfg)
    btn = ttk.Button(tab, text="Zapisz", command=_save); btn.grid(row=11, column=0, pady=10, sticky="w")

    if read_only:
        for ch in tab.winfo_children():
            try:
                if ch is not btn: ch.configure(state="disabled")
            except Exception: pass
        ttk.Label(tab, text="(Brak uprawnień do edycji)", style="WM.Muted.TLabel").grid(row=11, column=1, sticky="w")
