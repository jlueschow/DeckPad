"""
MenuBarApp — macOS Menu-Bar-Icon via QSystemTrayIcon.
Zeigt Szenen-Wechsel, Konfigurations-Öffner und Quit.
Verbindet HIDThread-Signale mit ConfigWindow-Updates.

SIGBUS-Schutz:
  Solange das Kontextmenü offen ist DARF weder setContextMenu() noch
  HID-device.read() aufgerufen werden — beides kollidiert mit
  NSEventTrackingRunLoopMode und erzeugt auf macOS einen Bus Error.
  Lösung:
    • _menu_open-Flag: blockiert _rebuild_menu() + HID-Polling
    • menu.aboutToShow / aboutToHide: steuern Flag + HID-Pause
    • _needs_rebuild-Flag: stellt auf, wenn Rebuild während Menü versucht wurde

triggered-nach-aboutToHide (macOS QSystemTrayIcon):
  Auf macOS feuert QMenu.triggered NACH aboutToHide, nicht davor.
  Wird _rebuild_menu() sofort in _on_menu_hidden aufgerufen, werden die
  alten QAction-Objekte per Python-GC zerstört bevor triggered feuern kann
  → Signal geht verloren, Konfigurationsfenster öffnet sich nicht.
  Fix: Rebuild 200 ms verzögern (QTimer.singleShot), damit triggered zuerst
  verarbeitet wird. _show_config prüft daher _menu_open == False.
"""

import sys, os, io
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication, QLabel
from PySide6.QtGui import QIcon, QPixmap, QImage, QColor, QPainter, QFont
from PySide6.QtCore import Qt, QObject, Slot, QTimer

from config.config_manager import cfg
# HIDThread + ConfigWindow werden lazy importiert:
#   hid_thread  → in _start_hid()        (spart ~4s auf langsamem Volume)
#   config_window → in _init_config_window() (spart ~5s auf langsamem Volume)
from app.log_window import show_log_window
from log_sink import log


# ── Tray-Icon erzeugen ─────────────────────────────────────────────────────────

def _make_tray_icon() -> QIcon:
    """
    Erzeugt ein 44×44 Tray-Icon (Retina: 22pt × 2).
    Weißes Knopf-Symbol auf transparentem Grund — sichtbar auf dunkler Menüleiste.
    """
    try:
        from PIL import Image, ImageDraw
        size = 44
        img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        cx, cy, r = size // 2, size // 2, size // 2 - 3
        draw.ellipse([cx-r, cy-r, cx+r, cy+r], outline=(255,255,255,240), width=3)
        draw.ellipse([cx-4, cy-4, cx+4, cy+4], fill=(255,255,255,220))
        draw.line([cx, cy-r+2, cx, cy-r+8], fill=(255,255,255,200), width=3)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        pm = QPixmap()
        pm.loadFromData(buf.getvalue())
        pm.setDevicePixelRatio(2.0)
        return QIcon(pm)
    except Exception:
        pm = QPixmap(22, 22)
        pm.fill(QColor(255, 255, 255))
        return QIcon(pm)


# ── MenuBarApp ─────────────────────────────────────────────────────────────────

class MenuBarApp(QObject):
    """
    Verbindet QSystemTrayIcon, HIDThread und ConfigWindow.
    Wird einmal in app_main.py instanziiert.
    """

    def __init__(self, app: QApplication):
        super().__init__()
        self._app              = app
        self._config_window    = None
        self._hid_thread       = None
        self._run_action       = None   # wird in _start_hid() gesetzt
        self._run_knob_action  = None
        self._status_text      = "Verbinde…"

        # Kontextmenü-Sicherheit: kein Rebuild / kein HID-Read wenn Menü offen
        self._menu_open      = False
        self._needs_rebuild  = False
        self._pending_show   = False   # Nur noch als Fallback; triggered kommt nach aboutToHide

        self._setup_tray()

        QTimer.singleShot(400, self._init_config_window)
        QTimer.singleShot(800, self._start_hid)

    # ── Tray-Icon ──────────────────────────────────────────────────────────────

    def _setup_tray(self):
        self._tray = QSystemTrayIcon(_make_tray_icon())
        self._tray.setToolTip("AKP03E Konfiguration")
        # Kein activated-Handler: auf macOS zeigt das Icon immer das Kontextmenü.
        # "Konfigurieren…" im Menü ist der korrekte Weg.
        self._tray.setVisible(True)
        self._rebuild_menu()

    def _rebuild_menu(self):
        """
        Baut das Kontextmenü neu auf und setzt es am Tray-Icon.
        DARF NICHT aufgerufen werden solange das Menü offen ist
        (würde NSMenu mid-display ersetzen → SIGBUS).
        """
        if self._menu_open:
            # Rebuild nach Schließen des Menüs nachholen
            self._needs_rebuild = True
            return

        menu   = QMenu()
        config = cfg.get()
        scenes = config.get("scenes", [])
        active = config.get("active_scene", 0)

        # Status-Zeile (nicht anklickbar)
        status_action = menu.addAction(f"⬤  {self._status_text}")
        status_action.setEnabled(False)
        menu.addSeparator()

        # Szenen
        for i, scene in enumerate(scenes):
            name = scene.get("name", f"Szene {i+1}")
            prefix = "✓  " if i == active else "    "
            a = menu.addAction(f"{prefix}{name}")
            a.triggered.connect(lambda checked, idx=i: self._switch_scene(idx))

        menu.addSeparator()

        # Konfigurieren
        cfg_action = menu.addAction("⚙  Konfigurieren…")
        cfg_action.triggered.connect(self._show_config)

        # Ereignis-Log
        log_action = menu.addAction("☰  Ereignis-Log…")
        log_action.triggered.connect(self._show_log)
        menu.addSeparator()

        # Beenden
        quit_action = menu.addAction("✕  Beenden")
        quit_action.triggered.connect(self._quit)

        # ── Menü-Sichtbarkeit überwachen ──────────────────────────────────────
        # aboutToShow / aboutToHide sind zuverlässig auf macOS (Qt 6).
        menu.aboutToShow.connect(self._on_menu_shown)
        menu.aboutToHide.connect(self._on_menu_hidden)

        self._tray.setContextMenu(menu)
        self._needs_rebuild = False

    def _on_menu_shown(self):
        """Menü wird geöffnet — HID-Polling pausieren und Rebuilds sperren."""
        self._menu_open = True
        if self._hid_thread:
            self._hid_thread.pause_polling()

    def _on_menu_hidden(self):
        """
        Menü geschlossen — HID-Polling fortsetzen, ggf. Menü neu bauen.

        WICHTIG: triggered feuert auf macOS NACH aboutToHide (nicht davor).
        Deshalb darf _rebuild_menu() hier NICHT sofort aufgerufen werden:
        Der sofortige Rebuild ersetzt das QMenu → alte QAction-Objekte werden
        per Python-GC zerstört → triggered kann nicht mehr feuern → Signal weg.
        Fix: Rebuild 200 ms verzögern, damit triggered zuerst verarbeitet wird.
        """
        self._menu_open = False
        if self._hid_thread:
            self._hid_thread.resume_polling()
        if self._needs_rebuild:
            # Verzögerter Rebuild: triggered muss zuerst feuern können
            QTimer.singleShot(200, self._rebuild_menu)
        # Fallback falls triggered ausnahmsweise vor aboutToHide feuert
        if self._pending_show:
            self._pending_show = False
            QTimer.singleShot(50, self._do_raise_config)

    # ── Lazy-Init ──────────────────────────────────────────────────────────────

    def _init_config_window(self):
        from app.config_window import ConfigWindow   # lazy: spart ~5s auf langsamem Volume
        self._config_window = ConfigWindow()
        self._config_window.scene_changed.connect(self._on_scene_changed_from_ui)
        self._config_window.brightness_changed.connect(self._on_brightness_from_ui)

    # ── HID-Thread ─────────────────────────────────────────────────────────────

    def _start_hid(self):
        from app.hid_thread import HIDThread, _run_action, _run_knob_action  # lazy
        self._run_action      = _run_action
        self._run_knob_action = _run_knob_action
        self._hid_thread = HIDThread()
        self._hid_thread.connected.connect(self._on_connected)
        self._hid_thread.disconnected.connect(self._on_disconnected)
        self._hid_thread.status_message.connect(self._on_status)
        self._hid_thread.scene_changed.connect(self._on_scene_changed_from_device)
        self._hid_thread.button_pressed.connect(self._on_button_action)
        self._hid_thread.knob_turned.connect(self._on_knob_action)
        self._hid_thread.knob_pressed.connect(self._on_knob_press_action)
        self._hid_thread.open_config_requested.connect(self._show_config)
        self._hid_thread.start()
        if self._config_window:
            self._config_window.set_hid_thread(self._hid_thread)

    # ── HID-Signale ────────────────────────────────────────────────────────────

    @Slot()
    def _on_connected(self):
        self._status_text = "Verbunden"
        self._rebuild_menu()
        if self._config_window:
            self._config_window.update_device_status(True)

    @Slot()
    def _on_disconnected(self):
        self._status_text = "Getrennt"
        self._rebuild_menu()
        if self._config_window:
            self._config_window.update_device_status(False)

    @Slot(str)
    def _on_status(self, msg: str):
        self._status_text = msg
        self._rebuild_menu()   # Sicher: wird übersprungen wenn _menu_open

    @Slot(int)
    def _on_scene_changed_from_device(self, scene_index: int):
        self._rebuild_menu()
        if self._config_window and self._config_window.isVisible():
            self._config_window.select_scene(scene_index)

    @Slot(int)
    def _on_button_action(self, btn_index: int):
        """Main-Thread-Slot — sicher für Quartz/AppKit."""
        config  = cfg.get()
        si      = config.get("active_scene", 0)
        scenes  = config.get("scenes", [])
        if si >= len(scenes):
            return
        buttons = scenes[si].get("buttons", [])
        btn = next((b for b in buttons if b["index"] == btn_index), None)
        if btn and btn.get("action"):
            if btn["action"].get("type") == "open_config":
                self._show_config()
            else:
                if self._run_action:
                    self._run_action(btn["action"])

    @Slot(int, int)
    def _on_knob_action(self, knob_index: int, direction: int):
        """Main-Thread-Slot — sicher für Quartz/AppKit."""
        config = cfg.get()
        si     = config.get("active_scene", 0)
        scenes = config.get("scenes", [])
        if si >= len(scenes):
            return
        knobs = scenes[si].get("knobs", [])
        knob  = next((k for k in knobs if k["index"] == knob_index), None)
        if knob and knob.get("action") and self._run_knob_action:
            self._run_knob_action(knob["action"], direction)

    @Slot(int)
    def _on_knob_press_action(self, knob_index: int):
        """Main-Thread-Slot für Knob-Druck — sicher für Quartz/AppKit."""
        log(f"knob ▶ press  index={knob_index}")
        config = cfg.get()
        si     = config.get("active_scene", 0)
        scenes = config.get("scenes", [])
        if si >= len(scenes):
            log(f"knob ▶ press  FEHLER: Szene {si} nicht gefunden")
            return
        knobs = scenes[si].get("knobs", [])
        knob  = next((k for k in knobs if k["index"] == knob_index), None)
        if not knob:
            log(f"knob ▶ press  FEHLER: Knob {knob_index} nicht in Szene {si}")
            return
        press_action = knob.get("press_action")
        log(f"press ▶ action={press_action!r}")
        if not press_action:
            log("press ▶ keine Aktion konfiguriert")
            return
        if press_action.get("type") == "open_config":
            self._show_config()
        else:
            if self._run_action:
                self._run_action(press_action)

    # ── Szenen-Wechsel ─────────────────────────────────────────────────────────

    def _switch_scene(self, idx: int):
        if self._hid_thread:
            self._hid_thread.upload_scene_now(idx)
        self._rebuild_menu()
        if self._config_window and self._config_window.isVisible():
            self._config_window.select_scene(idx)

    @Slot(int)
    def _on_scene_changed_from_ui(self, scene_index: int):
        if self._hid_thread:
            self._hid_thread.upload_scene_now(scene_index)
        self._rebuild_menu()

    @Slot(int)
    def _on_brightness_from_ui(self, value: int):
        if self._hid_thread:
            self._hid_thread.set_brightness_now(value)

    # ── Fenster ────────────────────────────────────────────────────────────────

    def _show_config(self):
        """
        Konfigurationsfenster anzeigen.

        Auf macOS mit QSystemTrayIcon feuert triggered NACH aboutToHide.
        Deshalb ist _menu_open hier immer False — direkter Timer-Pfad.
        _pending_show bleibt als Fallback für den umgekehrten Fall erhalten.

        Für Aufrufe außerhalb des Menüs (z.B. open_config-Button am Gerät):
        Verhalten identisch — _menu_open ist False → direkter Timer.
        """
        if self._config_window is None:
            self._init_config_window()
            if self._hid_thread:
                self._config_window.set_hid_thread(self._hid_thread)

        if self._menu_open:
            # Fallback: triggered kam ausnahmsweise vor aboutToHide
            self._pending_show = True
        else:
            # Normalfall (macOS): triggered nach aboutToHide → Menü ist schon zu
            QTimer.singleShot(50, self._do_raise_config)

    def _do_raise_config(self):
        """
        Fenster in den Vordergrund holen — NSMenu ist zu diesem Zeitpunkt
        garantiert vollständig geschlossen.

        winId() liefert auf macOS den NSView-Pointer; .window() gibt den
        zugehörigen NSWindow. Kein Titel-Lookup nötig → kein Race-Risiko.
        NSWindowCollectionBehaviorMoveToActiveSpace (2) stellt sicher, dass
        das Fenster nach mehrmaligem Öffnen/Schließen immer auf dem aktuellen
        Space erscheint.
        """
        if not self._config_window:
            return
        self._config_window.show()
        self._config_window.raise_()
        if sys.platform == "darwin":
            try:
                from AppKit import NSApplication
                import objc
                NSWindowCollectionBehaviorMoveToActiveSpace = 2
                nsapp = NSApplication.sharedApplication()
                nsapp.activateIgnoringOtherApps_(True)
                # winId() → NSView-Pointer → NSWindow (direkt, kein Titel-Lookup)
                nsview = objc.objc_object(c_void_p=int(self._config_window.winId()))
                nswin  = nsview.window()
                if nswin is not None:
                    nswin.setCollectionBehavior_(
                        nswin.collectionBehavior() | NSWindowCollectionBehaviorMoveToActiveSpace
                    )
                    nswin.makeKeyAndOrderFront_(None)
            except Exception:
                self._config_window.activateWindow()
        else:
            self._config_window.activateWindow()

    def _show_log(self):
        """Ereignis-Log-Fenster öffnen (oder in den Vordergrund holen)."""
        show_log_window()

    def _quit(self):
        if self._hid_thread:
            self._hid_thread.stop()
            self._hid_thread.wait(2000)
        self._tray.setVisible(False)
        self._app.quit()
