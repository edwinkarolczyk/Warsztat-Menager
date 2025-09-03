# migrate_profiles_config.py
# Minimalny migrator config.json -> dodaje profiles.* jeśli brak, bez ruszania reszty
import json, sys, os
from utils.path_utils import cfg_path

PATH = sys.argv[1] if len(sys.argv) > 1 else cfg_path("config.json")
with open(PATH, "r", encoding="utf-8") as f:
    cfg = json.load(f)

profiles = cfg.get("profiles") if isinstance(cfg.get("profiles"), dict) else {}
defaults = {
    "tab_enabled": True,
    "show_name_in_header": True,
    "avatar_dir": "",
    "fields_visible": ["login","nazwa","rola","zmiana"]
}
changed=False
for k,v in defaults.items():
    if profiles.get(k) is None:
        profiles[k]=v; changed=True
cfg["profiles"]=profiles

# płaskie klucze – dodaj tylko jeśli brak
flat = {
    "profiles.tab_enabled": profiles["tab_enabled"],
    "profiles.show_name_in_header": profiles["show_name_in_header"],
    "profiles.avatar_dir": profiles["avatar_dir"],
    "profiles.fields_visible": profiles["fields_visible"],
}
for k,v in flat.items():
    if k not in cfg:
        cfg[k]=v; changed=True

if changed:
    bak = PATH + ".bak"
    if not os.path.exists(bak):
        with open(bak,"w",encoding="utf-8") as f: json.dump(cfg, f, ensure_ascii=False, indent=2)
    with open(PATH,"w",encoding="utf-8") as f: json.dump(cfg, f, ensure_ascii=False, indent=2)
    print("[OK] Zaktualizowano", PATH, " (backup:", bak, ")")
else:
    print("[OK] Nic do zmiany – config jest aktualny")
