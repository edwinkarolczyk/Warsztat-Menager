from __future__ import annotations

import json
import os
import socket
import threading
import time
from pathlib import Path

TOKEN = os.environ.get("WMT_BRIDGE_TOKEN", "")
PORT_FILE = os.environ.get("WMT_BRIDGE_FILE", "")
MODAL_LOG = os.environ.get("WMT_MODAL_LOG", "")

try:
    import tkinter as tk
    from tkinter import messagebox
except Exception:
    tk = None
    messagebox = None


def _log_modal(kind, title, message, result=None):
    if not MODAL_LOG:
        return
    try:
        p = Path(MODAL_LOG)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as h:
            h.write(
                json.dumps(
                    {
                        "ts": time.time(),
                        "kind": kind,
                        "title": str(title),
                        "message": str(message),
                        "result": result,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    except Exception:
        pass


# W trybie robota natywne messageboxy nie mogą zablokować automatu.
# Każdy dialog jest logowany. Dotyczy wyłącznie procesu testowego z WMT_ACTIVE=1.
if messagebox is not None and os.environ.get("WMT_ACTIVE") == "1":
    def _show(kind, title, message, *args, **kwargs):
        _log_modal(kind, title, message, "ok")
        return "ok"

    def _yes(kind, title, message, *args, **kwargs):
        _log_modal(kind, title, message, True)
        return True

    try:
        messagebox.showinfo = lambda title, message, *a, **k: _show("showinfo", title, message, *a, **k)
        messagebox.showwarning = lambda title, message, *a, **k: _show("showwarning", title, message, *a, **k)
        messagebox.showerror = lambda title, message, *a, **k: _show("showerror", title, message, *a, **k)
        messagebox.askyesno = lambda title, message, *a, **k: _yes("askyesno", title, message, *a, **k)
        messagebox.askokcancel = lambda title, message, *a, **k: _yes("askokcancel", title, message, *a, **k)
        messagebox.askretrycancel = lambda title, message, *a, **k: False
    except Exception:
        pass


def _root():
    if tk is None:
        return None
    try:
        r = getattr(tk, "_default_root", None)
        if r is not None and int(r.winfo_exists()):
            return r
    except Exception:
        return None
    return None


def _call_tk(fn, timeout=12.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = _root()
        if r is not None:
            break
        time.sleep(0.05)
    else:
        raise RuntimeError("Brak aktywnego root Tk")

    box = {}
    ev = threading.Event()

    def runner():
        try:
            box["value"] = fn()
        except Exception as exc:
            box["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            ev.set()

    r.after(0, runner)
    if not ev.wait(timeout):
        raise TimeoutError("Timeout wykonania polecenia w wątku Tk")
    if "error" in box:
        raise RuntimeError(box["error"])
    return box.get("value")


def _walk(widget):
    out = [widget]
    try:
        for child in widget.winfo_children():
            out.extend(_walk(child))
    except Exception:
        pass
    return out


def _all_widgets():
    r = _root()
    return _walk(r) if r is not None else []


def _text(w):
    try:
        return str(w.cget("text"))
    except Exception:
        return ""


def _state(w):
    try:
        return str(w.cget("state"))
    except Exception:
        return ""


def _value(w):
    try:
        return str(w.get())
    except Exception:
        return ""


def _values(w):
    try:
        raw = w.cget("values")
        if isinstance(raw, (tuple, list)):
            return [str(x) for x in raw]
        return [str(x) for x in w.tk.splitlist(raw)]
    except Exception:
        return []


def _info(w):
    try:
        top = w.winfo_toplevel()
        title = str(top.title())
    except Exception:
        title = ""
    try:
        mapped = bool(w.winfo_ismapped())
    except Exception:
        mapped = False
    try:
        x, y = int(w.winfo_rootx()), int(w.winfo_rooty())
        width, height = int(w.winfo_width()), int(w.winfo_height())
    except Exception:
        x = y = width = height = 0
    try:
        cls = str(w.winfo_class())
    except Exception:
        cls = type(w).__name__
    return {
        "path": str(w),
        "class": cls,
        "text": _text(w),
        "state": _state(w),
        "value": _value(w),
        "values": _values(w),
        "window": title,
        "mapped": mapped,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
    }


def _snapshot():
    return [_info(w) for w in _all_widgets()]


def _visible_widgets(window_contains=""):
    wc = str(window_contains or "").casefold()
    result = []
    for w in _all_widgets():
        info = _info(w)
        if not info["mapped"]:
            continue
        if wc and wc not in info["window"].casefold():
            continue
        result.append((w, info))
    return result


def _match_text(text, exact=True, window_contains=""):
    wanted = str(text or "").strip().casefold()
    hits = []
    for w, info in _visible_widgets(window_contains):
        current = str(info.get("text") or "").strip().casefold()
        if not current:
            continue
        ok = current == wanted if exact else wanted in current
        if ok:
            hits.append((w, info))
    hits.sort(
        key=lambda item: 0
        if any(k in item[1]["class"].casefold() for k in ("button", "radio", "check"))
        else 1
    )
    return hits


def _click_text(text, exact=True, window_contains=""):
    hits = _match_text(text, exact=exact, window_contains=window_contains)
    if not hits and exact:
        hits = _match_text(text, exact=False, window_contains=window_contains)
    if not hits:
        raise LookupError(f"Nie znaleziono kontrolki z tekstem: {text}")
    w, info = hits[0]
    try:
        w.focus_set()
        w.update_idletasks()
    except Exception:
        pass
    if hasattr(w, "invoke"):
        w.invoke()
    else:
        w.event_generate(
            "<ButtonPress-1>",
            x=max(1, info["width"] // 2),
            y=max(1, info["height"] // 2),
        )
        w.event_generate(
            "<ButtonRelease-1>",
            x=max(1, info["width"] // 2),
            y=max(1, info["height"] // 2),
        )
    return info


def _input_candidates(window_contains=""):
    out = []
    for w, info in _visible_widgets(window_contains):
        cls = info["class"].casefold()
        if any(k in cls for k in ("entry", "combobox", "spinbox")):
            out.append((w, info))
    return out


def _set_widget_value(w, value):
    requested = str(value)
    vals = _values(w)
    if requested == "__FIRST__":
        requested = vals[0] if vals else ""
    elif requested == "__SECOND__":
        requested = vals[1] if len(vals) > 1 else (vals[0] if vals else "")

    if hasattr(w, "set"):
        w.set(requested)
    else:
        old_state = _state(w)
        try:
            if old_state == "readonly":
                w.configure(state="normal")
        except Exception:
            pass
        w.delete(0, "end")
        w.insert(0, requested)
        try:
            if old_state == "readonly":
                w.configure(state="readonly")
        except Exception:
            pass
    try:
        w.focus_set()
        w.event_generate("<<ComboboxSelected>>")
        w.event_generate("<KeyRelease>")
    except Exception:
        pass
    return requested


def _set_near_label(label, value, window_contains=""):
    labels = _match_text(label, exact=True, window_contains=window_contains)
    if not labels:
        labels = _match_text(label, exact=False, window_contains=window_contains)
    if not labels:
        raise LookupError(f"Nie znaleziono etykiety: {label}")
    _, li = labels[-1]
    lc_x = li["x"] + li["width"] / 2
    lc_y = li["y"] + li["height"] / 2
    candidates = _input_candidates(window_contains or li["window"])
    if not candidates:
        raise LookupError(f"Brak pola wejściowego przy etykiecie: {label}")
    scored = []
    for w, info in candidates:
        cx = info["x"] + info["width"] / 2
        cy = info["y"] + info["height"] / 2
        dy = cy - lc_y
        penalty = 0 if dy >= -15 else 10000
        dist = abs(cx - lc_x) + abs(cy - lc_y) + penalty
        scored.append((dist, w, info))
    scored.sort(key=lambda x: x[0])
    _, w, info = scored[0]
    selected = _set_widget_value(w, value)
    result = dict(info)
    result["set_to"] = selected
    return result


def _close_window(title_contains):
    wanted = str(title_contains or "").casefold()
    r = _root()
    for w in _all_widgets():
        try:
            if w.winfo_toplevel() is not w:
                continue
            title = str(w.title())
            if w is not r and wanted in title.casefold():
                w.destroy()
                return {"window": title}
        except Exception:
            pass
    raise LookupError(f"Nie znaleziono okna: {title_contains}")


def _shutdown():
    r = _root()
    if r is not None:
        r.after(20, r.destroy)
    return True


def _dispatch(req):
    if req.get("token") != TOKEN:
        raise PermissionError("Błędny token WMT")
    cmd = req.get("cmd")
    if cmd == "ping":
        return {"ok": True, "root": bool(_root())}
    if cmd == "snapshot":
        return _call_tk(_snapshot)
    if cmd == "click_text":
        return _call_tk(
            lambda: _click_text(
                req.get("text", ""),
                bool(req.get("exact", True)),
                req.get("window", ""),
            )
        )
    if cmd == "set_near_label":
        return _call_tk(
            lambda: _set_near_label(
                req.get("label", ""),
                req.get("value", ""),
                req.get("window", ""),
            )
        )
    if cmd == "close_window":
        return _call_tk(lambda: _close_window(req.get("title", "")))
    if cmd == "shutdown":
        return _call_tk(_shutdown)
    raise ValueError(f"Nieznana komenda: {cmd}")


def _serve():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(8)
    port = srv.getsockname()[1]
    if PORT_FILE:
        p = Path(PORT_FILE)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"port": port, "pid": os.getpid()}), encoding="utf-8")

    while True:
        conn, _ = srv.accept()
        try:
            data = b""
            while b"\n" not in data:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                data += chunk
            req = json.loads(data.split(b"\n", 1)[0].decode("utf-8"))
            try:
                result = _dispatch(req)
                payload = {"ok": True, "result": result}
            except Exception as exc:
                payload = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            conn.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
        finally:
            try:
                conn.close()
            except Exception:
                pass


if tk is not None and PORT_FILE and TOKEN:
    threading.Thread(target=_serve, name="WMT-TkBridge", daemon=True).start()
