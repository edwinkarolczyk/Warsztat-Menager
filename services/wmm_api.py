from __future__ import annotations

import json
import logging
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

logger = logging.getLogger(__name__)

_HOST = "0.0.0.0"
_PORT = int(os.environ.get("WM_WMM_PORT", "8765") or "8765")
_SERVER: ThreadingHTTPServer | None = None
_THREAD: threading.Thread | None = None
_LOCK = threading.Lock()


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


class _WmmHandler(BaseHTTPRequestHandler):
    server_version = "WarsztatMenagerWMM/1.0"

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
            self._send(200, {"ok": True, "service": "WM API", "api_version": "1"})
            return
        if self.path == "/api/v1/info":
            self._send(
                200,
                {
                    "ok": True,
                    "service": "Warsztat Menager",
                    "api_version": "1",
                    "wmm": True,
                },
            )
            return
        self._send(404, {"ok": False, "error": "Nie znaleziono endpointu."})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/v1/auth/login":
            self._send(404, {"ok": False, "error": "Nie znaleziono endpointu."})
            return

        payload = self._read_json()
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

        self._send(200, {"ok": True, "user": _safe_user(user)})


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
        ip = _lan_ip()
        print(f"[WM-WMM] API aktywne: http://{ip}:{_PORT}")
        logger.info("[WMM API] aktywne: http://%s:%s", ip, _PORT)
        return ip, _PORT


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
