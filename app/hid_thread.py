"""
HID-Kommunikation — alle HIDAPI-Aufrufe auf dem Main-Thread (macOS SIGBUS-sicher).

Warum:
  HIDAPI auf macOS verwendet intern IOKit + CFRunLoopRunInMode().
  Sobald QSystemTrayIcon (NSStatusItem) aktiv ist, kollidiert jeder
  Background-Thread-Aufruf von HIDAPI mit NSApplication's Haupt-Run-Loop
  → SIGBUS. Einzig sichere Lösung: alle HIDAPI-Aufrufe vom Main-Thread.

Architektur:
  HIDThread (QObject, Main-Thread)
    — _try_connect()     : device.connect() + Initialisierung (Main-Thread)
    — _tick()  [10ms]    : device.read() + Upload fertig-gerenderter Icons
    — _reconnect_timer   : erneuter Verbindungsversuch nach Fehler
    — _start_render()    : startet Icon-Render in threading.Thread (nur Pillow)

  _IconRenderWorker (threading.Thread, daemon)
    — rendert Icons mit Pillow (kein IOKit, kein HIDAPI)
    — legt fertige JPEG-Bytes in _render_queue ab (→ _tick übernimmt Upload)
"""

import sys, os, time, threading, queue
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QObject, QTimer, Signal
from akp03e import AKP03E, EventType, Event, INPUT_SIZE, _parse
from icons import load_app_icon, make_icon, ICON_SIZE
from config.config_manager import cfg
from log_sink import log
import actions


class HIDThread(QObject):
    """
    Öffentliche Schnittstelle — identisch zur alten Version.
    Alle HIDAPI-Aufrufe laufen auf dem Main-Thread.
    """
    button_pressed       = Signal(int)      # button index 1–6
    scene_changed        = Signal(int)      # neuer Szenen-Index nach Wechsel
    knob_turned          = Signal(int, int) # knob index, direction +1/-1
    knob_pressed         = Signal(int)      # knob index
    connected            = Signal()
    disconnected         = Signal()
    status_message       = Signal(str)
    open_config_requested = Signal()        # Nav-Button → Einstellungen öffnen

    def __init__(self, parent=None):
        super().__init__(parent)
        self._device  = AKP03E()
        self._running = False
        self._connected = False
        self._current_scene = 0
        self._config  = None

        # Verhindert veraltete Icon-Renders nach schnellen Szenen-Wechseln
        self._render_gen = 0
        # Queue: (generation, scene_index, [(btn_index, jpeg_bytes), ...])
        self._render_queue: queue.Queue = queue.Queue()

        # 10-ms-Tick: HID-Lesen + Upload fertiger Icons (Main-Thread!)
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(10)
        self._poll_timer.timeout.connect(self._tick)

        # 3-s-Reconnect nach Verbindungsabbruch
        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setInterval(3000)
        self._reconnect_timer.setSingleShot(True)
        self._reconnect_timer.timeout.connect(self._try_connect)

    # ── Lifecycle (gleiche API wie zuvor) ──────────────────────────────────────

    def start(self):
        """Startet den Verbindungsversuch (nächste Event-Loop-Iteration)."""
        self._running = True
        QTimer.singleShot(0, self._try_connect)

    def stop(self):
        self._running = False
        self._poll_timer.stop()
        self._reconnect_timer.stop()
        try:
            self._device.disconnect()
        except Exception:
            pass

    def wait(self, msecs: int = 2000):
        """Kompatibilitäts-Stub (kein Background-Thread mehr)."""
        pass

    def pause_polling(self):
        """Stoppt HID-Polling — aufrufen solange Kontextmenü offen ist."""
        self._poll_timer.stop()

    def resume_polling(self):
        """Setzt HID-Polling fort — aufrufen wenn Kontextmenü geschlossen."""
        if self._connected:
            self._poll_timer.start()

    # ── UI → HID: Befehle ─────────────────────────────────────────────────────

    def upload_scene_now(self, scene_index: int):
        """Startet asynchrones Icon-Rendern; Upload auf Main-Thread wenn fertig."""
        self._start_render(scene_index)

    def set_brightness_now(self, value: int):
        """Helligkeit sofort setzen (Main-Thread, HID-Write)."""
        if self._connected:
            try:
                self._device.set_brightness(value)
            except Exception:
                pass

    # ── Verbindung ─────────────────────────────────────────────────────────────

    def _try_connect(self):
        if not self._running:
            return
        try:
            self._config = cfg.get()
            # ── HIDAPI-Connect auf Main-Thread (IOKit-safe!) ──
            self._device.connect()
            brightness = self._config.get("brightness", 80)
            self._device.set_brightness(brightness)
            self._connected = True
            self.connected.emit()
            self.status_message.emit("Gerät verbunden")
            # Icons rendern (Background), Upload via _tick() (Main-Thread)
            self._start_render(self._config.get("active_scene", 0))
            self._poll_timer.start()
        except Exception as e:
            self.status_message.emit(f"Verbindungsfehler: {e}")
            self.disconnected.emit()
            if self._running:
                self._reconnect_timer.start()

    # ── 10-ms-Tick (Main-Thread) ───────────────────────────────────────────────

    def _tick(self):
        """
        Läuft alle 10 ms auf dem Main-Thread.
        1. Fertig gerenderte Icons auf Gerät hochladen (HID-Writes).
        2. HID-Events lesen und emittieren.
        """
        # ── 1. Icon-Upload wenn Background-Render fertig ─────────────────────
        try:
            while True:
                gen, scene_idx, rendered = self._render_queue.get_nowait()
                if gen != self._render_gen:
                    continue   # Veraltet — neuere Render-Anfrage liegt vor
                self.status_message.emit(
                    f"Lade Szene: {self._config.get('scenes', [{}])[scene_idx].get('name', '?')}"
                    if self._config and scene_idx < len(self._config.get("scenes", []))
                    else "Lade Szene…"
                )
                try:
                    for btn_index, jpeg in rendered:
                        self._device.set_button_image(btn_index, jpeg)
                    self._device.finalize_display()
                except Exception as e:
                    self.status_message.emit(f"Upload-Fehler: {e}")
        except queue.Empty:
            pass

        # ── 2. HID-Lesen (non-blocking, gibt [] zurück wenn keine Daten) ─────
        try:
            data = self._device._dev.read(INPUT_SIZE)
            if data:
                event = _parse(bytes(data))
                if event:
                    self._dispatch_event(event)
        except Exception as e:
            self._on_hid_error(e)

    def _on_hid_error(self, exc: Exception):
        self._poll_timer.stop()
        self._connected = False
        self.status_message.emit(f"Verbindungsfehler: {exc}")
        self.disconnected.emit()
        try:
            self._device.disconnect()
        except Exception:
            pass
        if self._running:
            self._reconnect_timer.start()

    # ── Event-Dispatch ─────────────────────────────────────────────────────────

    def _dispatch_event(self, event: Event):
        if event.type == EventType.BUTTON_DOWN:
            log(f"HID ▶ BUTTON_DOWN  index={event.index}")
            self.button_pressed.emit(event.index)

        elif event.type == EventType.SCENE_DOWN:
            log(f"HID ▶ SCENE_DOWN  id={event.index!r}")
            scenes = (self._config or {}).get("scenes", [])
            n = len(scenes)
            if n > 0:
                nav_id = event.index   # "prev" | "home" | "next"
                scene = scenes[self._current_scene] if self._current_scene < len(scenes) else {}
                nav_buttons = {b["id"]: b for b in scene.get("nav_buttons", [])}
                nav_btn = nav_buttons.get(nav_id, {})
                # Konfigurierte Aktion — Fallback auf Standard-Szenennavigation
                action = nav_btn.get("action") or {"type": f"scene_{nav_id}"}
                atype  = action.get("type", f"scene_{nav_id}")
                if atype == "scene_prev":
                    self._current_scene = (self._current_scene - 1) % n
                    self._start_render(self._current_scene)
                    self.scene_changed.emit(self._current_scene)
                elif atype == "scene_home":
                    self._current_scene = 0
                    self._start_render(self._current_scene)
                    self.scene_changed.emit(self._current_scene)
                elif atype == "scene_next":
                    self._current_scene = (self._current_scene + 1) % n
                    self._start_render(self._current_scene)
                    self.scene_changed.emit(self._current_scene)
                elif atype == "open_config":
                    self.open_config_requested.emit()
                else:
                    _run_action(action)

        elif event.type == EventType.KNOB_TURN:
            log(f"HID ▶ KNOB_TURN  index={event.index}  dir={event.value:+d}")
            self.knob_turned.emit(event.index, event.value)

        elif event.type == EventType.KNOB_DOWN:
            log(f"HID ▶ KNOB_DOWN  index={event.index}")
            self.knob_pressed.emit(event.index)

    # ── Async Icon-Rendering ───────────────────────────────────────────────────

    def _start_render(self, scene_index: int):
        """
        Startet einen daemon-Thread, der Icons mit Pillow rendert (kein IOKit!).
        Das Ergebnis wird in _render_queue gelegt; _tick() führt den Upload durch.
        """
        cfg.set_active_scene(scene_index)
        self._config = cfg.get()
        scenes = self._config.get("scenes", [])
        if scene_index >= len(scenes):
            return
        self._current_scene = scene_index

        # Generationszähler: veraltete Renders werden in _tick() verworfen
        self._render_gen += 1
        gen = self._render_gen
        buttons = list(scenes[scene_index].get("buttons", []))
        render_q = self._render_queue

        def _render_worker():
            """Rein in Pillow — kein HIDAPI, kein Quartz, thread-sicher."""
            rendered = []
            for btn in buttons:
                try:
                    jpeg = _render_icon(btn)
                except Exception:
                    try:
                        jpeg = make_icon(btn.get("label", ""))
                    except Exception:
                        jpeg = b""
                rendered.append((btn["index"], jpeg))
            render_q.put((gen, scene_index, rendered))

        t = threading.Thread(target=_render_worker, daemon=True, name="IconRender")
        t.start()


# ── Icon-Rendering (nur Pillow — kein IOKit/Quartz) ───────────────────────────

# Im Bundle zeigt sys._MEIPASS auf die extrahierten Ressourcen (assets/ liegt dort).
# In der Entwicklung: zwei Ebenen hoch vom app/-Verzeichnis.
if getattr(sys, "frozen", False):
    BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _render_icon(btn: dict) -> bytes:
    icon  = btn.get("icon") or {}
    itype = icon.get("type", "text")
    label = btn.get("label", "")
    try:
        if itype == "app":
            return load_app_icon(icon["path"])
        elif itype == "file":
            path = icon["path"]
            if not os.path.isabs(path):
                path = os.path.join(BASE_DIR, path)
            return load_app_icon(path)
        elif itype == "emoji":
            return make_icon(label, icon.get("emoji", ""), tuple(icon.get("bg", [30, 30, 40])))
        else:
            return make_icon(label, bg=tuple(icon.get("bg", [30, 30, 40])))
    except Exception:
        return make_icon(label)


# ── Aktionen (werden von menu_bar.py auf dem Main-Thread ausgeführt) ──────────

def _run_action(action: dict):
    if not action:
        return
    atype = action.get("type")
    log(f"ACTION ▶ type={atype!r}  data={action}")
    if atype == "open_app":
        name = action.get("name", "")
        path = action.get("path")
        if path and os.path.exists(path):
            actions.open_app_by_path(path)
        else:
            actions.open_app(name)
    elif atype == "open_url":
        actions.open_url(action.get("url", ""))
    elif atype == "shortcut":
        actions.send_shortcut(action.get("keys", ""))
    elif atype == "shell":
        import subprocess
        subprocess.Popen(action.get("command", ""), shell=True)
    elif atype == "dante_route":
        dante_cfg = cfg.get().get("dante", {})
        # Backward-Compat: altes Single-Route-Format → routes-Liste
        if "routes" in action:
            routes = action["routes"]
        else:
            routes = [{
                "rx_device":  action.get("rx_device", ""),
                "rx_channel": action.get("rx_channel", 1),
                "tx_device":  action.get("tx_device", ""),
                "tx_channel": action.get("tx_channel", ""),
            }]
        try:
            result = actions.dante_route(
                routes=routes,
                host=dante_cfg.get("host", ""),
                api_key=dante_cfg.get("api_key", ""),
            )
            log(f"dante_route ▶ {result}")
        except Exception as e:
            log(f"dante_route ▶ FEHLER: {e}")
            print(f"[dante_route] Fehler: {e}")


def _run_knob_action(action: dict, direction: int):
    if not action:
        return
    atype = action.get("type")
    log(f"KNOB_ACTION ▶ type={atype!r}  dir={direction:+d}")
    if atype == "volume":
        actions.MediaVolumeKnob().turn(direction)
    elif atype == "brightness":
        actions.MediaBrightnessKnob().turn(direction)
    elif atype == "shortcut_turn":
        key = action.get("key_cw") if direction > 0 else action.get("key_ccw")
        if key:
            actions.send_shortcut(key)
    elif atype == "scroll":
        actions.scroll(
            direction,
            axis=action.get("axis", "vertical"),
            speed=action.get("speed", 3),
        )
