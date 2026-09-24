# version: 1.0
"""Windows tray lifetime for the existing WM process and WMM API.

Tk is touched on its main thread only. Tray menu callbacks enqueue commands.
Closing the main window hides it; only an explicit Exit stops the API/process.
"""
from __future__ import annotations

import logging
import queue
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _windows_tray_icon(on_show, on_exit):
    """Lazy import: Tk and headless Linux tests do not need a display backend."""
    import pystray
    from PIL import Image, ImageDraw

    locations = [Path(__file__).resolve().parent.parent / "11.ico"]
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        locations.insert(0, Path(bundle_dir) / "11.ico")
    image = None
    for location in locations:
        try:
            if location.is_file():
                with Image.open(location) as src:
                    image = src.convert("RGBA").resize((64, 64))
                break
        except Exception:
            logger.exception("[WM-TRAY] Nie udało się odczytać ikony %s", location)
    if image is None:
        image = Image.new("RGBA", (64, 64), (27, 31, 36, 255))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((6, 6, 58, 58), radius=12, fill=(32, 166, 93, 255))
        draw.text((12, 24), "WM", fill="white")
    menu = pystray.Menu(
        pystray.MenuItem("Otwórz Warsztat Menager", on_show, default=True),
        pystray.MenuItem("Zakończ WM i wyłącz API", on_exit),
    )
    return pystray.Icon("WarsztatMenager", image, "Warsztat Menager — WMM API", menu)


class WmTrayRuntime:
    def __init__(
        self,
        root,
        *,
        on_exit=None,
        api_start=None,
        api_stop=None,
        status_provider=None,
        icon_factory=None,
    ):
        self.root = root
        self.on_exit_extra = on_exit
        if api_start is None or api_stop is None or status_provider is None:
            from services import wmm_api
            api_start = api_start or wmm_api.start_wmm_api
            api_stop = api_stop or wmm_api.stop_wmm_api
            status_provider = status_provider or wmm_api.mobile_status
        self.api_start = api_start
        self.api_stop = api_stop
        self.status_provider = status_provider
        self.icon_factory = icon_factory
        self.icon = None
        self.api_started = False
        self.stopping = False
        self.tray_events = queue.Queue()
        self.connected_users = set()
        self._tray_hint_sent = False
        self._poll_job = None

    def install(self):
        self.root._wm_background_runtime = self
        self.root._wm_exit_app = self.exit_app
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        try:
            self.api_started = bool(self.api_start())
        except Exception:
            logger.exception("[WM-TRAY] Nie udało się uruchomić WMM API")
        if not self.api_started:
            self._warn(
                "API WMM nie wystartowało (np. port 8765 jest zajęty). "
                "WM pozostaje dostępny, ale telefon nie połączy się z tym serwerem."
            )
        if self.icon_factory is not None or sys.platform == "win32":
            try:
                create = self.icon_factory or _windows_tray_icon
                icon = create(
                    lambda *_args: self.tray_events.put("show"),
                    lambda *_args: self.tray_events.put("exit"),
                )
                icon.run_detached()
                self.icon = icon
            except Exception as exc:
                logger.exception("[WM-TRAY] Ikona systemowa nie wystartowała")
                # A source checkout needs dependencies reinstalled after git pull;
                # an already-built EXE must be rebuilt with the pystray backend.
                if isinstance(exc, ModuleNotFoundError) and (
                    exc.name == "pystray" or "pystray" in str(exc).lower()
                ):
                    reason = (
                        "Brak biblioteki pystray w Pythonie uruchamiającym WM.\n"
                        "Dla wersji .py zainstaluj ją w tym samym interpreterze:\n"
                        "py -3.13 -m pip install pystray\n"
                        "Następnie uruchom WM ponownie.\n"
                        "Dla wersji EXE trzeba zbudować nowy pakiet z aktualnego wm.spec."
                    )
                else:
                    reason = (
                        "Przyczyna: "
                        f"{type(exc).__name__}: {str(exc)[:250]}\n"
                        "Sprawdź szczegóły [WM-TRAY] w logu WM."
                    )
                self._warn(
                    "Nie można uruchomić ikony obok zegara.\n"
                    + reason
                    + "\nZamknięcie okna zakończy WM i zatrzyma lokalne API WMM."
                )
        self._schedule()
        return self

    def _warn(self, text):
        # Never call Tk from a WMM server thread.
        def show():
            if self.stopping:
                return
            try:
                from tkinter import messagebox
                messagebox.showwarning("Warsztat Menager — praca w tle", text, parent=self.root)
            except Exception:
                logger.warning("[WM-TRAY] %s", text)
        try:
            self.root.after(200, show)
        except Exception:
            logger.warning("[WM-TRAY] %s", text)

    def _notify(self, message):
        if self.icon is None:
            return
        try:
            self.icon.notify(message, "Warsztat Menager")
        except Exception:
            logger.exception("[WM-TRAY] Powiadomienie systemowe niedostępne")

    def _presence_tick(self):
        if not self.api_started:
            return
        try:
            state = self.status_provider()
            users = state.get("users") or []
            connected = {}
            for user in users:
                if not isinstance(user, dict):
                    continue
                identity = str(user.get("user_id") or user.get("login") or "").strip().casefold()
                name = str(user.get("name") or user.get("login") or "").strip()
                # A client with pairing key but without user authentication is not
                # identified. Do not announce the synthetic WMM Mobile user.
                if not identity or identity == "wmm-mobile" or not name:
                    continue
                connected[identity] = name
            new = set(connected) - self.connected_users
            self.connected_users = set(connected)
            for identity in sorted(new):
                self._notify(f"Telefon WMM połączony: {connected[identity]}")
        except Exception:
            logger.exception("[WM-TRAY] Nie udało się sprawdzić użytkowników WMM")

    def _schedule(self):
        if self.stopping:
            return
        try:
            self._poll_job = self.root.after(2000, self._tick)
        except Exception:
            logger.exception("[WM-TRAY] Brak możliwości odświeżenia statusu")

    def _tick(self):
        self._poll_job = None
        if self.stopping:
            return
        while True:
            try:
                event = self.tray_events.get_nowait()
            except queue.Empty:
                break
            if event == "exit":
                self.exit_app()
                return
            if event == "show":
                self.show_window()
        self._presence_tick()
        self._schedule()

    def show_window(self):
        if self.stopping:
            return
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        except Exception:
            logger.exception("[WM-TRAY] Nie udało się przywrócić okna")

    def on_close(self):
        if self.stopping:
            return
        if self.icon is None:
            # Never hide the sole window if the tray icon did not start.
            self.exit_app()
            return
        try:
            self.root.withdraw()
        except Exception:
            logger.exception("[WM-TRAY] Nie udało się ukryć okna")
            return
        if not self._tray_hint_sent:
            self._tray_hint_sent = True
            self._notify(
                "WM działa w tle. Otwórz z ikony obok zegara; "
                "Zakończ WM wyłącza również API WMM."
            )

    def shutdown(self):
        if self.stopping:
            return
        self.stopping = True
        if self._poll_job is not None:
            try:
                self.root.after_cancel(self._poll_job)
            except Exception:
                pass
            self._poll_job = None
        if self.icon is not None:
            try:
                self.icon.stop()
            except Exception:
                logger.exception("[WM-TRAY] Zatrzymanie ikony nieudane")
            self.icon = None
        if self.api_started:
            try:
                self.api_stop()
            except Exception:
                logger.exception("[WM-TRAY] Zatrzymanie WMM API nieudane")
            self.api_started = False
        if self.on_exit_extra is not None:
            try:
                self.on_exit_extra()
            except Exception:
                logger.exception("[WM-TRAY] Zatrzymanie usług WM nieudane")

    def exit_app(self):
        self.shutdown()
        try:
            self.root.destroy()
        except Exception:
            logger.exception("[WM-TRAY] Nie udało się zamknąć WM")


def install_wm_background(root, *, on_exit=None):
    current = getattr(root, "_wm_background_runtime", None)
    if current is not None:
        return current
    return WmTrayRuntime(root, on_exit=on_exit).install()


__all__ = ["WmTrayRuntime", "install_wm_background"]
