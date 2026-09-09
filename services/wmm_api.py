from __future__ import annotations

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

logger = logging.getLogger(__name__)

_HOST = "0.0.0.0"
_PORT = int(os.environ.get("WM_WMM_PORT", "8765") or "8765")
_SERVER: ThreadingHTTPServer | None = None
_THREAD: threading.Thread | None = None
_LOCK = threading.Lock()
_KEY_LOCK = threading.Lock()
_KEY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
WMM_COMPAT_VERSION = "0.5.1"
_SESSION_TTL_SECONDS = 90
_SESSIONS: dict[str, dict[str, Any]] = {}
_SESSIONS_LOCK = threading.Lock()


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _safe_user(user: dict[str, Any]) -> dict[str, Any]:
    """Zwróć tylko dane użytkownika potrzebne WMM; nigdy PIN/hasło."""
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


def _pairing_file() -> Path:
    return _root_dir() / "data" / "wmm" / "pairing.json"


def _pairing_key() -> str:
    """Stały 6-znakowy klucz instalacji WM, przechowywany w WM_ROOT."""
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
    base_url = f"http://{ip}:{_PORT}"
    return {
        "host": ip,
        "port": _PORT,
        "key": key,
        "base_url": base_url,
        "qr": f"WMM://CONNECT?host={ip}&port={_PORT}&key={key}",
        "wmm_version": WMM_COMPAT_VERSION,
    }


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
        _SESSIONS[session_id] = {
            "user": dict(user),
            "last_seen": time.time(),
        }
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


def _drop_session(session_id: str) -> None:
    if not session_id:
        return
    with _SESSIONS_LOCK:
        _SESSIONS.pop(session_id, None)


def mobile_status() -> dict[str, Any]:
    """Stan aktywnych klientów WMM do prezentacji w GUI WM."""
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
    return {
        "connected": bool(users),
        "users": users,
        "count": len(users),
        "wmm_version": WMM_COMPAT_VERSION,
    }


class _WmmHandler(BaseHTTPRequestHandler):
    server_version = "WarsztatMenagerWMM/1.2"

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
        if length <= 0 or length > 16_384:
            return {}
        try:
            raw = self.rfile.read(length)
            value = json.loads(raw.decode("utf-8"))
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send(
                200,
                {
                    "ok": True,
                    "service": "WM API",
                    "api_version": "1",
                    "wmm_version": WMM_COMPAT_VERSION,
                },
            )
            return
        if self.path == "/api/v1/info":
            self._send(
                200,
                {
                    "ok": True,
                    "service": "Warsztat Menager",
                    "api_version": "1",
                    "wmm": True,
                    "wmm_version": WMM_COMPAT_VERSION,
                },
            )
            return
        if self.path == "/api/v1/pairing":
            self._send(200, {"ok": True, **pairing_info()})
            return
        self._send(404, {"ok": False, "error": "Nie znaleziono endpointu."})

    def do_POST(self) -> None:  # noqa: N802
        payload = self._read_json()

        if self.path == "/api/v1/mobile/heartbeat":
            session_id = str(payload.get("session_id", "") or "").strip()
            user = _touch_session(session_id)
            if user is None:
                self._send(401, {"ok": False, "error": "Sesja WMM wygasła."})
                return
            self._send(200, {"ok": True, "user": user})
            return

        if self.path == "/api/v1/auth/logout":
            session_id = str(payload.get("session_id", "") or "").strip()
            _drop_session(session_id)
            self._send(200, {"ok": True})
            return

        if self.path != "/api/v1/auth/login":
            self._send(404, {"ok": False, "error": "Nie znaleziono endpointu."})
            return

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


def start_wmm_api() -> tuple[str, int] | None:
    """Uruchom lekkie API WMM w tle. Funkcja jest idempotentna."""
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
        _THREAD = threading.Thread(
            target=server.serve_forever,
            name="wm-wmm-api",
            daemon=True,
        )
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
