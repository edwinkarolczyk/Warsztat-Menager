from __future__ import annotations

from datetime import datetime
import json
import logging
import mimetypes
import os
import re
import secrets
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

logger = logging.getLogger(__name__)

_HOST = "0.0.0.0"
_PORT = int(os.environ.get("WM_WMM_PORT", "8765") or "8765")
_SERVER: ThreadingHTTPServer | None = None
_THREAD: threading.Thread | None = None
_LOCK = threading.Lock()
_KEY_LOCK = threading.Lock()
_KEY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
WMM_COMPAT_VERSION = "0.5.5-beta"
_SESSION_TTL_SECONDS = 90
_SESSIONS: dict[str, dict[str, Any]] = {}
_SESSIONS_LOCK = threading.Lock()
_KEY_CLIENT_LAST_SEEN = 0.0
_MAX_JSON_BYTES = 128_000
_MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _safe_user(user: dict[str, Any]) -> dict[str, Any]:
    login = str(user.get("login", "") or "").strip()
    first = str(user.get("imie", "") or "").strip()
    last = str(user.get("nazwisko", "") or "").strip()
    display_name = " ".join(part for part in (first, last) if part).strip() or login
    return {
        "user_id": str(user.get("user_id") or user.get("id") or "").strip(),
        "login": login,
        "name": display_name,
        "role": str(user.get("rola") or user.get("role") or "").strip(),
        "rank": str(user.get("ranga") or user.get("rank") or "").strip(),
    }


def _lan_ip() -> str:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(("8.8.8.8", 80))
            return str(sock.getsockname()[0])
        finally:
            sock.close()
    except Exception:
        return "127.0.0.1"


def _root_dir() -> Path:
    raw = str(os.environ.get("WM_ROOT", "") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path.cwd().resolve()


def _data_dir() -> Path:
    root = _root_dir()
    return root if root.name.casefold() == "data" else root / "data"


def _pairing_file() -> Path:
    return _data_dir() / "wmm" / "pairing.json"


def _pairing_key() -> str:
    with _KEY_LOCK:
        path = _pairing_file()
        try:
            if path.is_file():
                raw = json.loads(path.read_text(encoding="utf-8"))
                key = str(raw.get("key", "") if isinstance(raw, dict) else "").strip().upper()
                if len(key) == 6 and all(ch in _KEY_ALPHABET for ch in key):
                    return key
        except Exception:
            logger.exception("[WMM API] nie udało się odczytać klucza parowania")

        key = "".join(secrets.choice(_KEY_ALPHABET) for _ in range(6))
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"key": key}, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            logger.exception("[WMM API] nie udało się zapisać klucza parowania")
        return key


def pairing_info() -> dict[str, Any]:
    ip = _lan_ip()
    key = _pairing_key()
    return {
        "host": ip,
        "port": _PORT,
        "key": key,
        "base_url": f"http://{ip}:{_PORT}",
        "qr": f"WMM://CONNECT?host={ip}&port={_PORT}&key={key}",
        "wmm_version": WMM_COMPAT_VERSION,
        "channel": "beta",
    }


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Nie można odczytać {path.name}: {exc}") from exc


def _write_json_atomic(path: Path, value: Any) -> None:
    temp = path.with_name(path.name + ".wmm.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, path)
    except OSError as exc:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        raise RuntimeError(f"Nie można zapisać {path.name}: {exc}") from exc


def _rows_from_value(value: Any, keys: tuple[str, ...] = ("items", "rows", "data")) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in keys:
            raw = value.get(key)
            if isinstance(raw, list):
                return [dict(item) for item in raw if isinstance(item, dict)]
        if value and all(isinstance(item, dict) for item in value.values()):
            out: list[dict[str, Any]] = []
            for key, item in value.items():
                row = dict(item)
                row.setdefault("id", str(key))
                out.append(row)
            return out
    return []


def _planista_orders() -> list[dict[str, Any]]:
    folder = _data_dir() / "zlecenia"
    if not folder.is_dir():
        raise RuntimeError("Brak katalogu data/zlecenia.")
    rows: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.json")):
        if path.name.startswith("_"):
            continue
        try:
            raw = _read_json(path)
        except RuntimeError:
            logger.exception("[WMM API] pominięto uszkodzone zlecenie: %s", path)
            continue
        if isinstance(raw, dict):
            item = dict(raw)
            item.setdefault("id", path.stem)
            rows.append(item)
    return rows


def _planista_products() -> list[dict[str, Any]]:
    folder = _data_dir() / "produkty"
    if not folder.is_dir():
        raise RuntimeError("Brak katalogu data/produkty.")
    rows: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.json")):
        try:
            row = _read_json(path)
        except RuntimeError:
            continue
        if not isinstance(row, dict):
            continue
        code = str(row.get("kod") or row.get("oznaczenie") or row.get("symbol") or path.stem).strip()
        if code:
            rows.append({"kod": code, "nazwa": str(row.get("nazwa") or code).strip(), "version": row.get("version", row.get("wersja"))})
    return rows


def _next_order_id() -> str:
    folder = _data_dir() / "zlecenia"
    numbers: list[int] = []
    for path in folder.glob("*.json"):
        try:
            numbers.append(int(path.stem))
        except ValueError:
            pass
    return f"{(max(numbers) + 1 if numbers else 1):06d}"


def _create_planista_order(payload: dict[str, Any], author: str) -> dict[str, Any]:
    product_code = str(payload.get("product_code") or "").strip()
    if not product_code:
        raise RuntimeError("Wybierz produkt.")
    products = {str(item.get("kod") or ""): item for item in _planista_products()}
    if product_code not in products:
        raise RuntimeError(f"Brak produktu WM: {product_code}")
    try:
        quantity = float(payload.get("quantity"))
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Ilość musi być liczbą.") from exc
    if quantity <= 0:
        raise RuntimeError("Ilość musi być większa od zera.")

    external_no = str(payload.get("external_no") or "").strip()
    if external_no:
        for existing in _planista_orders():
            if str(existing.get("zlec_wew") or "").strip().casefold() == external_no.casefold() and str(existing.get("produkt") or "").strip().casefold() == product_code.casefold():
                raise RuntimeError("Istnieje już zlecenie z tym samym Zleceniem wew i Produktem.")

    order_id = _next_order_id()
    now = datetime.now()
    order: dict[str, Any] = {
        "id": order_id,
        "produkt": product_code,
        "ilosc": quantity,
        "wykonano": 0.0,
        "status": "nowe",
        "termin": str(payload.get("due_date") or "").strip(),
        "rzaz_mm": 2.0,
        "utworzono": now.strftime("%Y-%m-%d %H:%M:%S"),
        "uwagi": str(payload.get("notes") or ""),
        "plan_polprodukty": {},
        "zapotrzebowanie_surowce": {},
        "rezerwacje_polprodukty": {},
        "rezerwacje_surowce": {},
        "materialy_zarezerwowane": False,
        "historia": [{"kiedy": now.isoformat(timespec="seconds"), "kto": author, "co": "utworzenie"}],
    }
    version = products[product_code].get("version")
    if version not in (None, ""):
        order["version"] = version
    if external_no:
        order["zlec_wew"] = external_no
    target = _data_dir() / "zlecenia" / f"{order_id}.json"
    _write_json_atomic(target, order)
    return order


def _machines_path() -> Path:
    return _data_dir() / "maszyny" / "maszyny.json"


def _machine_key(row: dict[str, Any]) -> str:
    return str(row.get("id") or row.get("nr_ewid") or row.get("numer") or row.get("nr") or "").strip()


def _machines() -> list[dict[str, Any]]:
    path = _machines_path()
    if not path.is_file():
        raise RuntimeError("Brak data/maszyny/maszyny.json.")
    rows = _rows_from_value(_read_json(path), ("items", "maszyny", "rows", "data"))
    for row in rows:
        key = _machine_key(row)
        row.setdefault("id", key)
        row.setdefault("nr", str(row.get("nr_ewid") or row.get("numer") or key))
        row.setdefault("lokalizacja", str(row.get("lokalizacja") or row.get("hala") or row.get("nr_hali") or "").strip())
        row.setdefault("photos", [])
    return rows


def _find_machine(machine_id: str) -> dict[str, Any] | None:
    needle = str(machine_id or "").strip().casefold()
    for row in _machines():
        values = (row.get("id"), row.get("nr_ewid"), row.get("numer"), row.get("nr"))
        if any(str(value or "").strip().casefold() == needle for value in values):
            return row
    return None


def _update_machine(machine_id: str, mutator) -> dict[str, Any]:
    path = _machines_path()
    raw = _read_json(path)
    rows = _rows_from_value(raw, ("items", "maszyny", "rows", "data"))
    needle = str(machine_id or "").strip().casefold()
    changed: dict[str, Any] | None = None
    for index, row in enumerate(rows):
        values = (row.get("id"), row.get("nr_ewid"), row.get("numer"), row.get("nr"))
        if not any(str(value or "").strip().casefold() == needle for value in values):
            continue
        updated = dict(row)
        mutator(updated)
        rows[index] = updated
        changed = updated
        break
    if changed is None:
        raise RuntimeError("Nie znaleziono maszyny.")
    if isinstance(raw, list):
        value: Any = rows
    elif isinstance(raw, dict):
        value = dict(raw)
        target_key = next((key for key in ("items", "maszyny", "rows", "data") if isinstance(value.get(key), list)), None)
        if target_key:
            value[target_key] = rows
        else:
            value = rows
    else:
        value = rows
    _write_json_atomic(path, value)
    key = _machine_key(changed)
    changed.setdefault("id", key)
    changed.setdefault("nr", str(changed.get("nr_ewid") or key))
    changed.setdefault("photos", [])
    return changed


def _tools() -> list[dict[str, Any]]:
    folder = _data_dir() / "narzedzia"
    if not folder.is_dir():
        raise RuntimeError("Brak katalogu data/narzedzia.")
    rows: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.json")):
        if path.name.startswith("_"):
            continue
        try:
            raw = _read_json(path)
        except RuntimeError:
            continue
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        tool_id = str(row.get("id") or row.get("numer") or row.get("nr") or path.stem).strip()
        if not tool_id:
            continue
        row["id"] = tool_id
        row.setdefault("nr", tool_id)
        row.setdefault("lokalizacja", str(row.get("lokalizacja") or row.get("miejsce") or "").strip())
        row.setdefault("photos", [])
        rows.append(row)
    return rows


def _tool_path(tool_id: str) -> Path | None:
    needle = str(tool_id or "").strip().casefold()
    folder = _data_dir() / "narzedzia"
    direct = folder / f"{tool_id}.json"
    if direct.is_file():
        return direct
    for path in folder.glob("*.json"):
        try:
            raw = _read_json(path)
        except RuntimeError:
            continue
        if not isinstance(raw, dict):
            continue
        values = (raw.get("id"), raw.get("numer"), raw.get("nr"), path.stem)
        if any(str(value or "").strip().casefold() == needle for value in values):
            return path
    return None


def _find_tool(tool_id: str) -> dict[str, Any] | None:
    path = _tool_path(tool_id)
    if path is None:
        return None
    raw = _read_json(path)
    if not isinstance(raw, dict):
        return None
    row = dict(raw)
    key = str(row.get("id") or row.get("numer") or row.get("nr") or path.stem).strip()
    row["id"] = key
    row.setdefault("nr", key)
    row.setdefault("lokalizacja", str(row.get("lokalizacja") or row.get("miejsce") or "").strip())
    row.setdefault("photos", [])
    return row


def _update_tool(tool_id: str, mutator) -> dict[str, Any]:
    path = _tool_path(tool_id)
    if path is None:
        raise RuntimeError("Nie znaleziono narzędzia.")
    raw = _read_json(path)
    if not isinstance(raw, dict):
        raise RuntimeError("Nieprawidłowe dane narzędzia.")
    row = dict(raw)
    mutator(row)
    _write_json_atomic(path, row)
    result = dict(row)
    key = str(result.get("id") or result.get("numer") or result.get("nr") or path.stem).strip()
    result["id"] = key
    result.setdefault("nr", key)
    result.setdefault("photos", [])
    return result


def _dispositions() -> list[dict[str, Any]]:
    try:
        from dyspozycje_store import load_dyspozycje
        rows = load_dyspozycje()
        if isinstance(rows, list):
            return [dict(row) for row in rows if isinstance(row, dict)]
    except Exception:
        logger.exception("[WMM API] nie udało się odczytać dyspozycji przez store")
    path = _data_dir() / "dyspozycje" / "dyspozycje.json"
    if not path.is_file():
        legacy = _data_dir() / "dyspozycje.json"
        if not legacy.is_file():
            return []
        path = legacy
    return _rows_from_value(_read_json(path), ("items", "dyspozycje", "rows", "data"))


def _set_disposition_status(item_id: str, status: str, author: str) -> dict[str, Any]:
    try:
        from dyspozycje_store import set_dyspozycja_status
        result = set_dyspozycja_status(item_id, status, changed_by=author)
        if isinstance(result, dict):
            return result
    except Exception:
        logger.exception("[WMM API] błąd zmiany statusu dyspozycji")
    raise RuntimeError("Nie udało się zmienić statusu dyspozycji.")


def _warehouse() -> list[dict[str, Any]]:
    candidates = [_data_dir() / "magazyn" / "surowce.json", _data_dir() / "magazyn.json"]
    rows: list[dict[str, Any]] = []
    for path in candidates:
        if not path.is_file():
            continue
        try:
            current = _rows_from_value(_read_json(path), ("items", "surowce", "pozycje", "rows", "data"))
        except RuntimeError:
            continue
        if current:
            rows = current
            break
    states_path = _data_dir() / "magazyn" / "stany.json"
    states: Any = None
    if states_path.is_file():
        try:
            states = _read_json(states_path)
        except RuntimeError:
            states = None
    for row in rows:
        item_id = str(row.get("id") or row.get("kod") or row.get("symbol") or "").strip()
        if item_id:
            row.setdefault("id", item_id)
        if isinstance(states, dict) and item_id in states:
            state = states[item_id]
            if isinstance(state, dict):
                for key in ("stan", "ilosc", "lokalizacja"):
                    if key in state:
                        row[key] = state[key]
            else:
                row["stan"] = state
    return rows


def _history_entry(action: str, author: str, note: str = "") -> dict[str, Any]:
    return {"kiedy": datetime.now().isoformat(timespec="seconds"), "kto": author, "co": action, "uwaga": note}


def _append_history(row: dict[str, Any], action: str, author: str, note: str = "") -> None:
    history = row.get("historia")
    if not isinstance(history, list):
        history = []
    history.append(_history_entry(action, author, note))
    row["historia"] = history


def _safe_filename(value: str) -> str:
    name = Path(value or "photo.jpg").name
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._") or "photo.jpg"
    return stem[:120]


def _media_root(kind: str, object_id: str) -> Path:
    if kind == "machines":
        return _data_dir() / "maszyny" / "attachments" / str(object_id)
    return _data_dir() / "narzedzia" / "attachments" / str(object_id)


def _store_photo(kind: str, object_id: str, filename: str, data: bytes, author: str) -> dict[str, Any]:
    folder = _media_root(kind, object_id)
    folder.mkdir(parents=True, exist_ok=True)
    safe = _safe_filename(filename)
    suffix = Path(safe).suffix.lower() or ".jpg"
    stored = f"wmm_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(3)}{suffix}"
    target = folder / stored
    target.write_bytes(data)
    return {
        "name": stored,
        "filename": stored,
        "url": f"/api/v1/media/{kind}/{str(object_id)}/{stored}",
        "author": author,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def _prune_sessions(now: float | None = None) -> None:
    current = time.time() if now is None else now
    stale = [sid for sid, session in _SESSIONS.items() if current - float(session.get("last_seen", 0.0) or 0.0) > _SESSION_TTL_SECONDS]
    for session_id in stale:
        _SESSIONS.pop(session_id, None)


def _new_session(user: dict[str, Any]) -> str:
    session_id = secrets.token_urlsafe(24)
    with _SESSIONS_LOCK:
        _prune_sessions()
        _SESSIONS[session_id] = {"user": dict(user), "last_seen": time.time()}
    return session_id


def _touch_session(session_id: str) -> dict[str, Any] | None:
    if not session_id:
        return None
    with _SESSIONS_LOCK:
        _prune_sessions()
        session = _SESSIONS.get(session_id)
        if session is None:
            return None
        session["last_seen"] = time.time()
        user = session.get("user")
        return dict(user) if isinstance(user, dict) else None


def _touch_key_client() -> None:
    global _KEY_CLIENT_LAST_SEEN
    _KEY_CLIENT_LAST_SEEN = time.time()


def _drop_session(session_id: str) -> None:
    if not session_id:
        return
    with _SESSIONS_LOCK:
        _SESSIONS.pop(session_id, None)


def mobile_status() -> dict[str, Any]:
    with _SESSIONS_LOCK:
        _prune_sessions()
        unique: dict[str, dict[str, Any]] = {}
        for session in _SESSIONS.values():
            user = session.get("user")
            if not isinstance(user, dict):
                continue
            key = str(user.get("user_id") or user.get("login") or "").strip().casefold()
            if key:
                unique[key] = dict(user)
        users = list(unique.values())
    key_client_active = time.time() - _KEY_CLIENT_LAST_SEEN <= _SESSION_TTL_SECONDS
    if not users and key_client_active:
        users = [{"user_id": "wmm-mobile", "login": "WMM", "name": "WMM Mobile BETA", "role": "", "rank": ""}]
    return {"connected": bool(users), "users": users, "count": len(users), "wmm_version": WMM_COMPAT_VERSION}


class _WmmHandler(BaseHTTPRequestHandler):
    server_version = "WarsztatMenagerWMM/1.5-beta"

    def log_message(self, fmt: str, *args: Any) -> None:
        logger.debug("[WMM API] " + fmt, *args)

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        if not path.is_file():
            self._send(404, {"ok": False, "error": "Nie znaleziono zdjęcia."})
            return
        body = path.read_bytes()
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _content_length(self) -> int:
        try:
            return int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            return 0

    def _read_json(self) -> dict[str, Any]:
        length = self._content_length()
        if length <= 0 or length > _MAX_JSON_BYTES:
            return {}
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}

    def _read_multipart_photo(self) -> tuple[str, bytes]:
        length = self._content_length()
        if length <= 0:
            raise RuntimeError("Brak danych zdjęcia.")
        if length > _MAX_UPLOAD_BYTES:
            raise RuntimeError("Zdjęcie jest za duże. Maksymalnie 20 MB.")
        content_type = str(self.headers.get("Content-Type") or "")
        match = re.search(r"boundary=(?:\"([^\"]+)\"|([^;]+))", content_type, re.I)
        if not match:
            raise RuntimeError("Nieprawidłowy format przesyłanego zdjęcia.")
        boundary = (match.group(1) or match.group(2) or "").strip().encode("utf-8")
        body = self.rfile.read(length)
        marker = b"--" + boundary
        for part in body.split(marker):
            if b"Content-Disposition:" not in part or b'name="photo"' not in part:
                continue
            head, sep, data = part.partition(b"\r\n\r\n")
            if not sep:
                continue
            header_text = head.decode("utf-8", errors="replace")
            filename_match = re.search(r'filename="([^"]*)"', header_text, re.I)
            filename = filename_match.group(1) if filename_match else "photo.jpg"
            payload = data.rstrip(b"\r\n-")
            if not payload:
                raise RuntimeError("Przesłane zdjęcie jest puste.")
            return filename, payload
        raise RuntimeError("Nie znaleziono pola photo w danych multipart.")

    def _has_pairing_key(self) -> bool:
        supplied = str(self.headers.get("X-WMM-Key") or self.headers.get("X-Cidex-Token") or "").strip().upper()
        ok = bool(supplied) and secrets.compare_digest(supplied, _pairing_key())
        if ok:
            _touch_key_client()
            session_id = str(self.headers.get("X-WMM-Session") or "").strip()
            if session_id:
                _touch_session(session_id)
        return ok

    def _require_pairing_key(self) -> bool:
        if self._has_pairing_key():
            return True
        self._send(401, {"ok": False, "error": "Brak lub błędny klucz połączenia WMM."})
        return False

    def _author(self) -> str:
        session_id = str(self.headers.get("X-WMM-Session") or "").strip()
        user = _touch_session(session_id) if session_id else None
        if isinstance(user, dict):
            return str(user.get("login") or user.get("name") or "WMM").strip() or "WMM"
        return "WMM"

    def _send_rows(self, loader) -> None:
        try:
            rows = loader()
        except RuntimeError as exc:
            self._send(400, {"ok": False, "error": str(exc)})
            return
        self._send(200, {"ok": True, "count": len(rows), "items": rows})

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/health":
            self._send(200, {"ok": True, "service": "WM API", "api_version": "1", "wmm_version": WMM_COMPAT_VERSION, "channel": "beta"})
            return
        if path == "/api/v1/info":
            self._has_pairing_key()
            self._send(200, {"ok": True, "service": "Warsztat Menager", "api_version": "1", "wmm": True, "wmm_version": WMM_COMPAT_VERSION, "channel": "beta", "features": {"planista_read": True, "planista_create": True, "machines_read": True, "machines_write": True, "machine_photos": True, "tools_read": True, "tools_write": True, "tool_photos": True, "dispositions_read": True, "dispositions_write": True, "warehouse_read": True, "qr_resolve": True}})
            return
        if path == "/api/v1/pairing":
            self._send(200, {"ok": True, **pairing_info()})
            return

        if path.startswith("/api/v1/media/"):
            if not self._require_pairing_key():
                return
            parts = [unquote(part) for part in path.split("/") if part]
            if len(parts) != 7 or parts[:3] != ["api", "v1", "media"]:
                self._send(404, {"ok": False, "error": "Nie znaleziono zdjęcia."})
                return
            kind, object_id, filename = parts[3], parts[4], parts[5]
            if kind not in {"machines", "tools"}:
                self._send(404, {"ok": False, "error": "Nie znaleziono zdjęcia."})
                return
            self._send_file(_media_root(kind, object_id) / Path(filename).name)
            return

        protected = {"/api/v1/planista/orders", "/api/v1/planista/products", "/api/v1/machines", "/api/v1/tools", "/api/v1/dispositions", "/api/v1/warehouse", "/api/v1/qr/resolve"}
        if path in protected and not self._require_pairing_key():
            return
        if path == "/api/v1/planista/orders":
            self._send_rows(_planista_orders)
            return
        if path == "/api/v1/planista/products":
            self._send_rows(_planista_products)
            return
        if path == "/api/v1/machines":
            self._send_rows(_machines)
            return
        if path == "/api/v1/tools":
            self._send_rows(_tools)
            return
        if path == "/api/v1/dispositions":
            self._send_rows(_dispositions)
            return
        if path == "/api/v1/warehouse":
            self._send_rows(_warehouse)
            return
        if path == "/api/v1/qr/resolve":
            code = unquote(str((parse_qs(parsed.query).get("code") or [""])[0])).strip()
            item = _find_machine(code)
            if item is not None:
                self._send(200, {"ok": True, "item": {**item, "entity": "machine"}})
                return
            tool = _find_tool(code)
            if tool is not None:
                self._send(200, {"ok": True, "item": {**tool, "entity": "tool"}})
                return
            self._send(404, {"ok": False, "error": "Nie znaleziono obiektu dla tego kodu QR."})
            return

        for prefix, finder in (("/api/v1/machines/", _find_machine), ("/api/v1/tools/", _find_tool)):
            if path.startswith(prefix):
                if not self._require_pairing_key():
                    return
                rest = path[len(prefix):]
                if "/" in rest:
                    break
                item = finder(unquote(rest))
                if item is None:
                    self._send(404, {"ok": False, "error": "Nie znaleziono obiektu."})
                else:
                    self._send(200, {"ok": True, "item": item})
                return
        self._send(404, {"ok": False, "error": "Nie znaleziono endpointu."})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        is_photo = bool(re.fullmatch(r"/api/v1/(machines|tools)/[^/]+/photos", path))
        payload = {} if is_photo else self._read_json()

        if path == "/api/v1/mobile/heartbeat":
            session_id = str(payload.get("session_id", "") or "").strip()
            user = _touch_session(session_id)
            if user is None:
                self._send(401, {"ok": False, "error": "Sesja WMM wygasła."})
                return
            _touch_key_client()
            self._send(200, {"ok": True, "user": user})
            return
        if path == "/api/v1/auth/logout":
            _drop_session(str(payload.get("session_id", "") or "").strip())
            self._send(200, {"ok": True})
            return
        if path == "/api/v1/auth/login":
            login = str(payload.get("login", "") or "").strip()
            pin = str(payload.get("pin", "") or "").strip()
            if not login or not pin:
                self._send(400, {"ok": False, "error": "Podaj login i PIN."})
                return
            try:
                from services.profile_service import authenticate
                user = authenticate(login, pin)
            except Exception:
                logger.exception("[WMM API] błąd weryfikacji użytkownika")
                self._send(500, {"ok": False, "error": "Błąd weryfikacji użytkownika WM."})
                return
            if not user:
                self._send(401, {"ok": False, "error": "Nieprawidłowy login lub PIN."})
                return
            safe_user = _safe_user(user)
            session_id = _new_session(safe_user)
            _touch_key_client()
            self._send(200, {"ok": True, "user": safe_user, "session_id": session_id, "heartbeat_seconds": 30, "wmm_version": WMM_COMPAT_VERSION, "channel": "beta"})
            return

        if not self._require_pairing_key():
            return
        author = self._author()

        if path == "/api/v1/planista/orders":
            try:
                order = _create_planista_order(payload, author)
            except RuntimeError as exc:
                self._send(400, {"ok": False, "error": str(exc)})
                return
            self._send(201, {"ok": True, "item": order})
            return

        machine_match = re.fullmatch(r"/api/v1/machines/([^/]+)/(status|note|photos)", path)
        if machine_match:
            machine_id = unquote(machine_match.group(1))
            action = machine_match.group(2)
            try:
                if action == "status":
                    status = str(payload.get("status") or "").strip()
                    note = str(payload.get("note") or "").strip()
                    if not status:
                        raise RuntimeError("Brak statusu maszyny.")
                    def mutate(row: dict[str, Any]) -> None:
                        row["status"] = status
                        if note:
                            row["uwagi"] = note
                        _append_history(row, f"status: {status}", author, note)
                    item = _update_machine(machine_id, mutate)
                elif action == "note":
                    note = str(payload.get("note") or "").strip()
                    if not note:
                        raise RuntimeError("Uwaga jest pusta.")
                    def mutate(row: dict[str, Any]) -> None:
                        row["uwagi"] = note
                        _append_history(row, "uwaga", author, note)
                    item = _update_machine(machine_id, mutate)
                else:
                    filename, data = self._read_multipart_photo()
                    photo = _store_photo("machines", machine_id, filename, data, author)
                    def mutate(row: dict[str, Any]) -> None:
                        photos = row.get("photos") if isinstance(row.get("photos"), list) else []
                        photos.append(photo)
                        row["photos"] = photos
                        _append_history(row, "zdjęcie", author, photo["name"])
                    item = _update_machine(machine_id, mutate)
                self._send(200, {"ok": True, "item": item})
            except RuntimeError as exc:
                self._send(400, {"ok": False, "error": str(exc)})
            except Exception as exc:
                logger.exception("[WMM API] operacja maszyny nieudana")
                self._send(500, {"ok": False, "error": f"Błąd operacji maszyny: {exc}"})
            return

        tool_match = re.fullmatch(r"/api/v1/tools/([^/]+)/(status|photos)", path)
        if tool_match:
            tool_id = unquote(tool_match.group(1))
            action = tool_match.group(2)
            try:
                if action == "status":
                    status = str(payload.get("status") or "").strip()
                    note = str(payload.get("note") or "").strip()
                    if not status:
                        raise RuntimeError("Brak statusu narzędzia.")
                    def mutate(row: dict[str, Any]) -> None:
                        row["status"] = status
                        if note:
                            row["opis"] = note
                        _append_history(row, f"status: {status}", author, note)
                    item = _update_tool(tool_id, mutate)
                else:
                    filename, data = self._read_multipart_photo()
                    photo = _store_photo("tools", tool_id, filename, data, author)
                    def mutate(row: dict[str, Any]) -> None:
                        photos = row.get("photos") if isinstance(row.get("photos"), list) else []
                        photos.append(photo)
                        row["photos"] = photos
                        _append_history(row, "zdjęcie", author, photo["name"])
                    item = _update_tool(tool_id, mutate)
                self._send(200, {"ok": True, "item": item})
            except RuntimeError as exc:
                self._send(400, {"ok": False, "error": str(exc)})
            except Exception as exc:
                logger.exception("[WMM API] operacja narzędzia nieudana")
                self._send(500, {"ok": False, "error": f"Błąd operacji narzędzia: {exc}"})
            return

        disposition_match = re.fullmatch(r"/api/v1/dispositions/([^/]+)/status", path)
        if disposition_match:
            try:
                item = _set_disposition_status(unquote(disposition_match.group(1)), str(payload.get("status") or "").strip(), author)
                self._send(200, {"ok": True, "item": item})
            except RuntimeError as exc:
                self._send(400, {"ok": False, "error": str(exc)})
            return

        self._send(404, {"ok": False, "error": "Nie znaleziono endpointu."})


def start_wmm_api() -> tuple[str, int] | None:
    global _SERVER, _THREAD
    with _LOCK:
        if _SERVER is not None:
            return _lan_ip(), _PORT
        try:
            server = ThreadingHTTPServer((_HOST, _PORT), _WmmHandler)
        except OSError as exc:
            logger.warning("[WMM API] port %s niedostępny: %s", _PORT, exc)
            return None
        _SERVER = server
        _THREAD = threading.Thread(target=server.serve_forever, name="wm-wmm-api", daemon=True)
        _THREAD.start()
        info = pairing_info()
        print(f"[WM-WMM BETA] API aktywne: {info['base_url']}")
        print(f"[WM-WMM BETA] QR: {info['qr']}")
        logger.info("[WMM API BETA] aktywne: %s", info["base_url"])
        return str(info["host"]), _PORT


def stop_wmm_api() -> None:
    global _SERVER, _THREAD
    with _LOCK:
        server = _SERVER
        _SERVER = None
        _THREAD = None
    if server is not None:
        try:
            server.shutdown()
            server.server_close()
        except Exception:
            logger.exception("[WMM API] błąd zatrzymania serwera")
