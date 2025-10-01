#!/usr/bin/env python3
import sys, json, os, itertools
def load(p):
    with open(p,"r",encoding="utf-8") as f:
        d=json.load(f)
    if isinstance(d,dict) and isinstance(d.get("items"),list): return d["items"]
    if isinstance(d,list): return d
    raise ValueError("Nieobsługiwany format (oczekiwano listy albo {items:[...]})")
if __name__=="__main__":
    if len(sys.argv)!=2:
        print("Użycie: py -3.13 tools\\check_machines_file.py <ścieżka_do_json>")
        sys.exit(2)
    path=sys.argv[1]
    print(f"[CHK] path={path} exists={os.path.exists(path)}")
    if not os.path.exists(path): sys.exit(1)
    try:
        items=load(path)
        print(f"[CHK] records={len(items)}")
        for m in itertools.islice(items,0,3):
            print(" -", {k:m.get(k) for k in ("id","kod","nazwa","lokacja","status")})
    except Exception as e:
        print("[CHK][ERR]",e); sys.exit(3)
