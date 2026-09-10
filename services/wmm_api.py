from __future__ import annotations

from datetime import datetime
import json
import logging
import os
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
WMM_COMPAT_VERSION = "0.5.3"
_SESSION_TTL_SECONDS = 90
_SESSIONS: dict[str, dict[str, Any]] = {}
_SESSIONS_LOCK = threading.Lock()
_KEY_CLIENT_LAST_SEEN = 0.0


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
            path.write_text(
                json.dumps({"key": key}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
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
        temp.write_text(
            json.dumps(value, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
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
            row = _read_json(path)
        except RuntimeError:
            logger.exception("[WMM API] pominięto uszkodzone zlecenie: %s", path)
            continue
        if isinstance(row, dict):
            item = dict(row)
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
            logger.exception("[WMM API] pominięto uszkodzony produkt: %s", path)
            continue
        if not isinstance(row, dict):
            continue
        code = str(
            row.get("kod")
            or row.get("oznaczenie")
            or row.get("symbol")
            or path.stem
        ).strip()
        if code:
            rows.append(
                {
                    "kod": code,
                    "nazwa": str(row.get("nazwa") or code).strip(),
                    "version": row.get("version", row.get("wersja")),
                }
            )
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


def _create_planista_order(payload: dict[str, Any]) -> dict[str, Any]:
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
            if (
                str(existing.get("zlec_wew") or "").strip().casefold() == external_no.casefold()
                and str(existing.get("produkt") or "").strip().casefold() == product_code.casefold()
            ):
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
        "historia": [{"kiedy": now.isoformat(timespec="seconds"), "kto": "WMM", "co": "utworzenie"}],
    }
    version = products[product_code].get("version")
    if version not in (None, ""):
        order["version"] = version
    if external_no:
        order["zlec_wew"] = external_no
    target = _data_dir() / "zlecenia" / f"{order_id}.json"
    if target.exists():
        raise RuntimeError(f"Plik {target.name} już istnieje.")
    _write_json_atomic(target, order)
    return order


def _machines_path() -> Path:
    return _data_dir() / "maszyny" / "maszyny.json"


def _machines() -> list[dict[str, Any]]:
    path = _machines_path()
    if not path.is_file():
        raise RuntimeError("Brak data/maszyny/maszyny.json.")
    rows = _rows_from_value(_read_json(path), ("items", "maszyny", "rows", "data"))
    for row in rows:
        row.setdefault("id", str(row.get("nr_ewid") or row.get("numer") or row.get("nr") or "").strip())
        row.setdefault("nr", str(row.get("nr_ewid") or row.get("numer") or row.get("id") or "").strip())
        row.setdefault("lokalizacja", str(row.get("lokalizacja") or row.get("hala") or row.get("nr_hali") or "").strip())
    return rows


def _find_machine(machine_id: str) -> dict[str, Any] | None:
    needle = str(machine_id or "").strip().casefold()
    for row in _machines():
        values = (row.get("id"), row.get("nr_ewid"), row.get("numer"), row.get("nr"))
        if any(str(value or "").strip().casefold() == needle for value in values):
            return row
    return None


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
            logger.exception("[WMM API] pominięto uszkodzone narzędzie: %s", path)
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
        rows.append(row)
    return rows


def _find_tool(tool_id: str) -> dict[str, Any] | None:
    needle = str(tool_id or "").strip().casefold()
    for row in _tools():
        if any(
            str(row.get(key) or "").strip().casefold() == needle
            for key in ("id", "numer", "nr")
        ):
            return row
    return None


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


def _warehouse() -> list[dict[str, Any]]:
    candidates = [
        _data_dir() / "magazyn" / "surowce.json",
        _data_dir() / "magazyn.json",
    ]
    rows: list[dict[str, Any]] = []
    for path in candidates:
        if not path.is_file():
            continue
        try:
            current = _rows_from_value(_read_json(path), ("items", "surowce", "pozycje", "rows", "data"))
        except RuntimeError:
            logger.exception("[WMM API] błąd odczytu magazynu: %s", path)
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


def _prune_sessions(now: float | None = None) -> None:
    current = time.time() if now is None else now
    stale = [
        session_id
        for session_id, session in _SESSIONS.items()
        if current - float(session.get("last_seen", 0.0) or 0.0) > _SESSION_TTL_SECONDS
    ]
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
        users = [
            {
                "user_id": "wmm-mobile",
                "login": "WMM",
                "name": "WMM Mobile",
                "role": "",
                "rank": "",
            }
        ]
    return {
        "connected": bool(users),
        "users": users,
        "count": len(users),
        "wmm_version": WMM_COMPAT_VERSION,
    }


class _WmmHandler(BaseHTTPRequestHandler):
    server_version = "WarsztatMenagerWMM/1.4"

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

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            length = 0
        if length <= 0 or length > 64_000:
            return {}
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}

    def _has_pairing_key(self) -> bool:
        supplied = str(
            self.headers.get("X-WMM-Key")
            or self.headers.get("X-Cidex-Token")
            or ""
        ).strip().upper()
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
            self._send(200, {"ok": True, "service": "WM API", "api_version": "1", "wmm_version": WMM_COMPAT_VERSION})
            return
        if path == "/api/v1/info":
            self._has_pairing_key()
            self._send(
                200,
                {
                    "ok": True,
                    "service": "Warsztat Menager",
                    "api_version": "1",
                    "wmm": True,
                    "wmm_version": WMM_COMPAT_VERSION,
                    "features": {
                        "planista_read": True,
                        "planista_create": True,
                        "machines_read": True,
                        "tools_read": True,
                        "dispositions_read": True,
                        "warehouse_read": True,
                        "qr_resolve": True,
                    },
                },
            )
            return
        if path == "/api/v1/pairing":
            self._send(200, {"ok": True, **pairing_info()})
            return

        if path in {
            "/api/v1/planista/orders",
            "/api/v1/planista/products",
            "/api/v1/machines",
            "/api/v1/tools",
            "/api/v1/dispositions",
            "/api/v1/warehouse",
            "/api/v1/qr/resolve",
        } and not self._require_pairing_key():
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
            query = parse_qs(parsed.query)
            code = unquote(str((query.get("code") or [""])[0])).strip()
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
        payload = self._read_json()

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
            self._send(
                200,
                {
                    "ok": True,
                    "user": safe_user,
                    "session_id": session_id,
                    "heartbeat_seconds": 30,
                    "wmm_version": WMM_COMPAT_VERSION,
                },
            )
            return

        if path == "/api/v1/planista/orders":
            if not self._require_pairing_key():
                return
            try:
                order = _create_planista_order(payload)
            except RuntimeError as exc:
                self._send(400, {"ok": False, "error": str(exc)})
                return
            self._send(201, {"ok": True, "item": order})
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
        print(f"[WM-WMM] API aktywne: {info['base_url']}")
        print(f"[WM-WMM] QR: {info['qr']}")
        logger.info("[WMM API] aktywne: %s", info["base_url"])
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
